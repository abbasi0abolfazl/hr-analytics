"""Core HR analytics (independent of the API / dashboard).

Conventions (also documented in docs/METRICS.md)
------------------------------------------------
* One row of ``v_fact_month`` = one employee employed during one month.
  The exit month is flagged ``exited`` and the employee has no later rows.
* headcount(month)      = rows in that month (employed at any point of the month).
* monthly_hazard        = exits / person-months (the "monthly attrition rate").
* annualized_turnover   = exits / mean monthly headcount * 12 / n_months.
* opening headcount     = headcount(first month) - hires(first month);
  closing headcount     = employees still Active in the last month.
* Lagged predictors (``*_prev``) use the previous month so that the exit
  month's own (already deteriorated) values do not leak into the prediction.
* 1-5 scales are never rescaled to 0-10; Recommend to Friend is reported as
  "% favourable (4-5)", not as eNPS.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import stats

MIN_EVENTS_FOR_MODEL = 15
TENURE_BINS = [-1, 6, 12, 24, 36, 60, 10_000]
TENURE_LABELS = ["0-6", "7-12", "13-24", "25-36", "37-60", "60+"]
DIMENSIONS = ["compensation_benefits", "growth_opportunities", "work_culture",
              "work_life_balance", "management_style", "overall_satisfaction"]
BREAKDOWN_FIELDS = ("department", "manager_id", "employment_type", "work_location",
                    "salary_grade", "tenure_band", "hire_cohort")


# --------------------------------------------------------------------------- filters
@dataclass(frozen=True)
class Filters:
    departments: tuple[str, ...] = ()
    manager_ids: tuple[str, ...] = ()
    employment_types: tuple[str, ...] = ()
    work_locations: tuple[str, ...] = ()
    salary_grades: tuple[str, ...] = ()
    month_from: date | None = None
    month_to: date | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "department": list(self.departments), "manager_id": list(self.manager_ids),
            "employment_type": list(self.employment_types), "work_location": list(self.work_locations),
            "salary_grade": list(self.salary_grades),
            "month_from": self.month_from.isoformat()[:7] if self.month_from else None,
            "month_to": self.month_to.isoformat()[:7] if self.month_to else None,
        }


def _clause(f: Filters, col: dict[str, str] | None = None, with_dates: str | None = "month"):
    """Build a parameterised WHERE clause for the employee-level + month filters."""
    c = {"department": "department", "manager_id": "manager_id", "employment_type": "employment_type",
         "work_location": "work_location", "salary_grade": "salary_grade"}
    c.update(col or {})
    parts, params = [], []
    for field_, values in (("department", f.departments), ("manager_id", f.manager_ids),
                           ("employment_type", f.employment_types), ("work_location", f.work_locations),
                           ("salary_grade", f.salary_grades)):
        if values and c.get(field_):
            parts.append(f"{c[field_]} IN ({','.join('?' * len(values))})")
            params += list(values)
    if with_dates:
        if f.month_from:
            parts.append(f"{with_dates} >= ?")
            params.append(f.month_from)
        if f.month_to:
            parts.append(f"{with_dates} <= ?")
            params.append(f.month_to)
    return (" WHERE " + " AND ".join(parts)) if parts else "", params


# --------------------------------------------------------------------------- helpers
def clean(o: Any) -> Any:
    """Make nested structures JSON-safe (NaN -> None, numpy -> python, dates -> iso)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (o is None or math.isnan(o) or math.isinf(o)) else round(float(o), 4)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, date)):
        return o.isoformat()[:10]
    if o is pd.NaT or o is pd.NA:
        return None
    return o


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def get_fact(con, f: Filters) -> pd.DataFrame:
    where, params = _clause(f)
    df = con.execute(f"SELECT * FROM v_fact_month{where} ORDER BY employee_id, month", params).df()
    df["month"] = pd.to_datetime(df["month"])
    df["tenure_band"] = pd.cut(df["tenure_months"], TENURE_BINS, labels=TENURE_LABELS).astype(str)
    df["hire_cohort"] = np.where(df["is_new_hire"], "new_hire_2025", "existing")
    return df


def get_employees(con, f: Filters) -> pd.DataFrame:
    """Employees passing the employee-level filters (no date filter)."""
    where, params = _clause(f, {"salary_grade": "initial_salary_grade"}, with_dates=None)
    return con.execute(f"SELECT * FROM employees{where}", params).df()


def _end_of_data(con) -> pd.Timestamp:
    return pd.Timestamp(con.execute("SELECT max(month) FROM monthly").fetchone()[0]) + pd.offsets.MonthEnd(0)


def _range(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp, int]:
    lo, hi = df["month"].min(), df["month"].max()
    return lo, hi, (hi.year - lo.year) * 12 + hi.month - lo.month + 1


def _empty(df: pd.DataFrame) -> bool:
    return df.empty


def _rate_block(g: pd.DataFrame, n_months: int) -> dict:
    pm, ex = len(g), int(g["exited"].sum())
    lo, hi = wilson(ex, pm)
    hc = g.groupby("month").size().mean() if pm else float("nan")
    return {"person_months": pm, "exits": ex, "monthly_hazard": ex / pm if pm else None,
            "hazard_ci_low": lo, "hazard_ci_high": hi,
            "annualized_turnover": ex / hc * 12 / max(n_months, 1) if pm else None,
            "avg_headcount": hc}


# --------------------------------------------------------------------------- overview
def overview(con, f: Filters) -> dict:
    fact = get_fact(con, f)
    if _empty(fact):
        return {"empty": True}
    lo, hi, n_months = _range(fact)
    emp = get_employees(con, f)
    hires = emp[(emp["hire_date"] >= lo) & (emp["hire_date"] <= hi + pd.offsets.MonthEnd(0))]
    att = con.execute("SELECT employee_id, exit_type, exit_reason FROM attrition").df()
    ex = fact[fact["exited"]].merge(att, on="employee_id", how="left")
    hires_first = int((hires["hire_date"].dt.to_period("M") == lo.to_period("M")).sum())
    opening = int((fact["month"] == lo).sum()) - hires_first
    closing = int(((fact["month"] == hi) & (~fact["exited"])).sum())
    monthly = []
    for m, g in fact.groupby("month"):
        h = int(((hires["hire_date"].dt.to_period("M")) == m.to_period("M")).sum())
        e = int(g["exited"].sum())
        monthly.append({"month": m.strftime("%Y-%m"), "headcount": len(g), "exits": e, "hires": h,
                        "voluntary_exits": int((ex[ex["month"] == m]["exit_type"] == "Voluntary").sum()),
                        "monthly_hazard": e / len(g), "avg_engagement": g["engagement_score"].mean(),
                        "avg_performance": g["performance_rating"].mean(),
                        "active_end": int((~g["exited"]).sum())})
    half = fact["month"].dt.month >= 7
    h1, h2 = fact[~half], fact[half]
    kpi = {
        "n_employees": int(fact["employee_id"].nunique()),
        "opening_headcount": opening, "closing_headcount": closing,
        "net_change_pct": (closing - opening) / opening if opening else None,
        "hires": int(len(hires)), "exits": int(fact["exited"].sum()),
        "voluntary_exits": int((ex["exit_type"] == "Voluntary").sum()),
        "involuntary_exits": int((ex["exit_type"] == "Involuntary").sum()),
        "annualized_turnover": fact["exited"].sum() / fact.groupby("month").size().mean() * 12 / n_months,
        "avg_engagement": fact["engagement_score"].mean(),
        "avg_performance": fact["performance_rating"].mean(),
        "avg_skills_gap": fact["skills_gap_score"].mean(),
        "hazard_h1": h1["exited"].mean() if len(h1) else None,
        "hazard_h2": h2["exited"].mean() if len(h2) else None,
        "n_months": n_months, "period_from": lo.strftime("%Y-%m"), "period_to": hi.strftime("%Y-%m"),
    }
    return clean({"empty": False, "kpi": kpi, "monthly": monthly})


# --------------------------------------------------------------------------- breakdown
def attrition_breakdown(con, f: Filters, by: str) -> dict:
    if by not in BREAKDOWN_FIELDS:
        raise ValueError(f"by must be one of {BREAKDOWN_FIELDS}")
    fact = get_fact(con, f)
    if _empty(fact):
        return {"empty": True, "by": by, "rows": []}
    _, _, n_months = _range(fact)
    fact["_h2"] = fact["month"].dt.month >= 7
    rows = []
    for key, g in fact.groupby(by, observed=True):
        r = {"group": key, **_rate_block(g, n_months),
             "avg_engagement": g["engagement_score"].mean(),
             "avg_performance": g["performance_rating"].mean(),
             "hazard_h1": g.loc[~g["_h2"], "exited"].mean() if (~g["_h2"]).any() else None,
             "hazard_h2": g.loc[g["_h2"], "exited"].mean() if g["_h2"].any() else None,
             "n_employees": int(g["employee_id"].nunique())}
        rows.append(r)
    order = {l: i for i, l in enumerate(TENURE_LABELS)} if by == "tenure_band" else None
    rows.sort(key=(lambda r: order.get(r["group"], 99)) if order else (lambda r: -(r["annualized_turnover"] or 0)))
    return clean({"empty": False, "by": by, "rows": rows})


def exit_reasons(con, f: Filters) -> dict:
    fact = get_fact(con, f)
    if _empty(fact):
        return {"empty": True, "rows": []}
    att = con.execute("SELECT employee_id, exit_type, exit_reason, eligible_for_rehire FROM attrition").df()
    ex = fact[fact["exited"]].merge(att, on="employee_id", how="left")
    if ex.empty:
        return {"empty": True, "rows": []}
    ex["half"] = np.where(ex["month"].dt.month >= 7, "h2", "h1")
    rows = []
    for (reason, typ), g in ex.groupby(["exit_reason", "exit_type"]):
        rows.append({"reason": reason, "exit_type": typ, "exits": len(g),
                     "share": len(g) / len(ex), "h1": int((g["half"] == "h1").sum()),
                     "h2": int((g["half"] == "h2").sum()),
                     "rehire_eligible_share": g["eligible_for_rehire"].mean(),
                     "avg_engagement_at_exit": g["engagement_score"].mean()})
    rows.sort(key=lambda r: -r["exits"])
    return clean({"empty": False, "total_exits": len(ex), "rows": rows})


# --------------------------------------------------------------------------- engagement signal
def pre_exit_trajectory(con, f: Filters, max_k: int = 8) -> dict:
    """Event study: mean metrics k months before exit vs. never-exiting employees."""
    fact = get_fact(con, f)
    if _empty(fact) or not fact["exited"].any():
        return {"empty": True, "rows": []}
    exm = fact[fact["exited"]][["employee_id", "month"]].rename(columns={"month": "exit_month"})
    d = fact.merge(exm, on="employee_id", how="left")
    leavers = d[d["exit_month"].notna()].copy()
    leavers["k"] = (leavers["exit_month"].dt.year - leavers["month"].dt.year) * 12 + \
                   leavers["exit_month"].dt.month - leavers["month"].dt.month
    stay = d[d["exit_month"].isna()]
    rows = []
    for k, g in leavers[leavers["k"] <= max_k].groupby("k"):
        rows.append({"months_before_exit": int(k), "n": len(g),
                     "engagement": g["engagement_score"].mean(), "performance": g["performance_rating"].mean(),
                     "skills_gap": g["skills_gap_score"].mean()})
    rows.sort(key=lambda r: -r["months_before_exit"])
    base = {"engagement": stay["engagement_score"].mean(), "performance": stay["performance_rating"].mean(),
            "skills_gap": stay["skills_gap_score"].mean(), "n_stayers": int(stay["employee_id"].nunique())}
    return clean({"empty": False, "rows": rows, "stayers_baseline": base})


def _auc(score: pd.Series, y: pd.Series) -> float | None:
    """Mann-Whitney AUC of `score` for y==1 (higher score = more likely exit)."""
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    r = stats.rankdata(pd.concat([pos, neg]))
    return float((r[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def fit_logit(d: pd.DataFrame) -> dict:
    """Person-month logit: exit ~ lagged engagement, performance, skills gap, promo lag, new hire, H2."""
    import statsmodels.api as sm
    from statsmodels.tools.sm_exceptions import PerfectSeparationError

    d = d.dropna(subset=["eng_prev", "perf_prev", "skill_prev", "promo_prev"])
    n_ex = int(d["exited"].sum())
    if len(d) == 0 or n_ex < MIN_EVENTS_FOR_MODEL:
        return {"available": False, "reason": f"too few exits for a stable model (n={n_ex}, need >= {MIN_EVENTS_FOR_MODEL})"}
    X = pd.DataFrame({
        "engagement_prev (per +1 pt)": d["eng_prev"], "performance_prev (per +1 pt)": d["perf_prev"],
        "skills_gap_prev (per +1 pt)": d["skill_prev"], "months_since_promo_prev (per +12 m)": d["promo_prev"] / 12,
        "new_hire_2025 (yes vs no)": d["is_new_hire"].astype(float),
        "second_half_year (H2 vs H1)": (d["month"].dt.month >= 7).astype(float)})
    X = X.loc[:, X.std() > 0]
    y = d["exited"].astype(int)
    try:
        res = sm.Logit(y, sm.add_constant(X)).fit(disp=0, maxiter=200)
    except (PerfectSeparationError, np.linalg.LinAlgError, Exception) as exc:  # noqa: BLE001
        return {"available": False, "reason": f"model did not converge: {exc}"}
    ci = res.conf_int()
    terms = [{"term": t, "odds_ratio": math.exp(res.params[t]), "ci_low": math.exp(ci.loc[t, 0]),
              "ci_high": math.exp(ci.loc[t, 1]), "p_value": res.pvalues[t]} for t in X.columns]
    out = {"available": True, "n_person_months": len(d), "n_exits": n_ex, "terms": terms,
           "auc_engagement_only": _auc(-d["eng_prev"], y), "manager_effect": None}
    mgrs = d["manager_id"].nunique()
    if mgrs >= 2:
        try:
            dm = pd.get_dummies(d["manager_id"], drop_first=True, dtype=float)
            r2 = sm.Logit(y, sm.add_constant(pd.concat([X, dm], axis=1))).fit(disp=0, maxiter=200)
            lr = 2 * (r2.llf - res.llf)
            out["manager_effect"] = {"lr_chi2": lr, "df": dm.shape[1],
                                     "p_value": float(stats.chi2.sf(lr, dm.shape[1]))}
        except Exception:  # noqa: BLE001
            out["manager_effect"] = None
    return out


def risk_drivers(con, f: Filters) -> dict:
    fact = get_fact(con, f)
    if _empty(fact):
        return {"empty": True, "bands": {}, "model": {"available": False, "reason": "no data"}}
    d = fact.dropna(subset=["eng_prev"]).copy()
    bands: dict[str, list] = {}
    specs = {"engagement": "eng_prev", "performance": "perf_prev", "skills_gap": "skill_prev",
             "months_since_promotion": "promo_prev"}
    for name, col in specs.items():
        s = d[col].dropna()
        if s.nunique() < 4:
            continue
        q = pd.qcut(d[col], 4, duplicates="drop")
        rows = []
        for i, (iv, g) in enumerate(d.groupby(q, observed=True)):
            lo_, hi_ = wilson(int(g["exited"].sum()), len(g))
            rows.append({"quartile": f"Q{i + 1}", "range": f"{iv.left:.2f}–{iv.right:.2f}",
                         "person_months": len(g), "exits": int(g["exited"].sum()),
                         "monthly_hazard": g["exited"].mean(), "ci_low": lo_, "ci_high": hi_})
        bands[name] = rows
    return clean({"empty": False, "bands": bands, "model": fit_logit(fact)})


# --------------------------------------------------------------------------- surveys
def _surveys(con, f: Filters) -> pd.DataFrame:
    """Survey responses joined to employee attributes (salary grade = grade in the survey month)."""
    cols = {"department": "e.department", "manager_id": "e.manager_id", "employment_type": "e.employment_type",
            "work_location": "e.work_location", "salary_grade": "m.salary_grade"}
    where, params = _clause(f, cols, with_dates="s.survey_date")
    s = con.execute(f"""SELECT s.*, e.manager_id, e.employment_type, e.work_location, e.hire_date
                        FROM surveys s JOIN employees e USING (employee_id)
                        LEFT JOIN monthly m ON m.employee_id = s.employee_id
                             AND m.month = date_trunc('month', s.survey_date){where}""", params).df()
    s["survey_date"] = pd.to_datetime(s["survey_date"])
    return s


def engagement_survey(con, f: Filters) -> dict:
    s = _surveys(con, f)
    if s.empty:
        return {"empty": True}
    fact = get_fact(con, Filters(f.departments, f.manager_ids, f.employment_types, f.work_locations,
                                 f.salary_grades))
    leaver_ids = set(fact.loc[fact["exited"], "employee_id"])
    s["leaver"] = s["employee_id"].isin(leaver_ids)
    by_q = s.groupby("survey_quarter")[DIMENSIONS + ["recommend_to_friend"]].mean().reset_index()
    # coverage: responses / employees active (not exiting) in the survey month
    cov = []
    for q, g in s.groupby("survey_quarter"):
        m = pd.Timestamp(g["survey_date"].iloc[0]).to_period("M").to_timestamp()
        act = fact[fact["month"] == m]      # everyone employed in the survey month
        cov.append({"quarter": q, "responses": len(g), "employed_in_month": len(act),
                    "coverage": len(g) / len(act) if len(act) else None,
                    "recommend_favourable_pct": float((g["recommend_to_friend"] >= 4).mean())})
    gap = []
    for dim in DIMENSIONS:
        a, b = s.loc[s["leaver"], dim].dropna(), s.loc[~s["leaver"], dim].dropna()
        p = float(stats.mannwhitneyu(a, b).pvalue) if len(a) > 5 and len(b) > 5 else None
        gap.append({"dimension": dim, "leavers": a.mean(), "stayers": b.mean(),
                    "gap": a.mean() - b.mean(), "p_value": p, "n_leavers": len(a), "n_stayers": len(b)})
    sm_ = s.assign(month=s["survey_date"].dt.to_period("M").dt.to_timestamp()).merge(
        fact[["employee_id", "month", "engagement_score"]], on=["employee_id", "month"], how="left")
    corr = {dim: sm_[dim].corr(sm_["engagement_score"]) for dim in DIMENSIONS + ["recommend_to_friend"]}
    return clean({"empty": False, "by_quarter": by_q.to_dict("records"), "coverage": cov, "gap": gap,
                  "corr_with_engagement": corr, "n_responses": len(s)})


# --------------------------------------------------------------------------- recruitment
def kaplan_meier(durations: Iterable[float], events: Iterable[int], grid: list[int]) -> list[dict]:
    """Kaplan-Meier survival S(t) at the requested day grid (handles censoring)."""
    d = pd.DataFrame({"t": list(durations), "e": list(events)}).sort_values("t")
    n = len(d)
    out, s = [], 1.0
    times = sorted(d.loc[d["e"] == 1, "t"].unique())
    for g in grid:
        s = 1.0
        for t in times:
            if t > g:
                break
            at_risk = int((d["t"] >= t).sum())
            dead = int(((d["t"] == t) & (d["e"] == 1)).sum())
            s *= 1 - dead / at_risk
        out.append({"day": g, "survival": s if n else None, "at_risk": int((d["t"] >= g).sum())})
    return out


def recruitment(con, f: Filters) -> dict:
    where, params = _clause(f, {"manager_id": None, "employment_type": None, "work_location": None,
                                "salary_grade": None}, with_dates="offer_date")
    r = con.execute(f"SELECT * FROM recruitment{where}", params).df()
    if r.empty:
        return {"empty": True}
    for c in ("opening_date", "offer_date", "hire_date"):
        r[c] = pd.to_datetime(r[c])
    end = _end_of_data(con)
    att = con.execute("""SELECT a.employee_id, a.exit_date, a.exit_reason, a.exit_type FROM attrition a""").df()
    att["exit_date"] = pd.to_datetime(att["exit_date"])
    emp_ids = set(get_employees(con, f)["employee_id"])
    hired = r[r["hire_date"].notna()].merge(att, on="employee_id", how="left")
    hired = hired[hired["employee_id"].isin(emp_ids)] if f.employment_types or f.work_locations or \
        f.manager_ids or f.salary_grades else hired
    hired["left"] = hired["exit_date"].notna()
    hired["days_to_exit"] = (hired["exit_date"] - hired["hire_date"]).dt.days
    valid = hired[~(hired["days_to_exit"] < 0)].copy()      # drop exit-before-hire from survival only
    valid["dur"] = np.where(valid["left"], valid["days_to_exit"], (end - valid["hire_date"]).dt.days)
    declined = r[r["offer_accepted"] == False]  # noqa: E712
    d90_cut = end - pd.Timedelta(days=90)
    funnel = {"requisitions": len(r), "offers_made": int(r["offers_made"].sum()),
              "accepted": int((r["offer_accepted"] == True).sum()), "declined": len(declined),  # noqa: E712
              "acceptance_rate": float((r["offer_accepted"] == True).mean()),  # noqa: E712
              "offers_per_hire": float(r.loc[r["hire_date"].notna(), "offers_made"].mean()),
              "days_to_fill_hired": r.loc[r["hire_date"].notna(), "days_to_fill"].mean(),
              "days_to_fill_declined_to_offer": declined["days_to_fill"].mean(),
              "avg_cost_per_hire": r["cost_per_hire"].mean(), "total_hiring_cost": r["cost_per_hire"].sum(),
              "hires_d90_not_matured": int((r["hire_date"] > d90_cut).sum()),
              "avg_quality_90d": r["quality_of_hire_90d"].mean(),
              "avg_manager_satisfaction_90d": r["manager_satisfaction_90d"].mean()}
    by_dept = []
    for dep, g in r.groupby("department"):
        h = hired[hired["department"] == dep]
        by_dept.append({"department": dep, "requisitions": len(g), "acceptance_rate": float((g["offer_accepted"] == True).mean()),  # noqa: E712
                        "hires": len(h), "left_in_year": int(h["left"].sum()),
                        "left_share": h["left"].mean() if len(h) else None,
                        "days_to_fill_hired": g.loc[g["hire_date"].notna(), "days_to_fill"].mean(),
                        "avg_cost_per_hire": g["cost_per_hire"].mean(), "avg_quality_90d": g["quality_of_hire_90d"].mean()})
    grid = [30, 60, 90, 120, 180, 240, 300]
    km = kaplan_meier(valid["dur"], valid["left"].astype(int), grid) if len(valid) else []
    km_dept = {dep: kaplan_meier(g["dur"], g["left"].astype(int), grid)
               for dep, g in valid.groupby("department") if len(g) >= 5}
    qh = hired.dropna(subset=["quality_of_hire_90d"])
    q_rows = []     # NB: hires made later have shorter follow-up, so this is descriptive only
    if len(qh) >= 8:
        qh = qh.assign(qb=pd.cut(qh["quality_of_hire_90d"], [0, 2.99, 3.99, 5], labels=["<3", "3-3.99", "4-5"]))
        for b, g in qh.groupby("qb", observed=True):
            q_rows.append({"quality_band": str(b), "hires": len(g), "left_share": g["left"].mean()})
    hm = []
    for m, g in hired.groupby(hired["hire_date"].dt.to_period("M")):
        hm.append({"month": str(m), "hires": len(g), "left_later": int(g["left"].sum())})
    reasons = hired[hired["left"]].groupby("exit_reason").size().sort_values(ascending=False)
    hired_left = hired[hired["left"]]
    sunk = float(hired_left["cost_per_hire"].sum())
    summary = {"hires": len(hired), "left_in_year": int(hired["left"].sum()),
               "left_share": hired["left"].mean() if len(hired) else None,
               "median_days_to_exit": hired_left["days_to_exit"].median(),
               "left_within_90d": int((hired["days_to_exit"].between(0, 90)).sum()),
               "sunk_cost_of_leavers": sunk,
               "sunk_cost_share": sunk / hired["cost_per_hire"].sum() if hired["cost_per_hire"].sum() else None}
    return clean({"empty": False, "funnel": funnel, "summary": summary, "by_department": by_dept,
                  "survival_km": km, "survival_km_by_department": km_dept,
                  "quality_vs_exit": q_rows, "hires_by_month": hm,
                  "newhire_exit_reasons": [{"reason": k, "exits": int(v)} for k, v in reasons.items()]})


# --------------------------------------------------------------------------- careers
def careers(con, f: Filters) -> dict:
    fact = get_fact(con, f)
    if _empty(fact):
        return {"empty": True}
    ids = set(fact["employee_id"])
    rv = con.execute("SELECT * FROM reviews").df()
    rv["review_date"] = pd.to_datetime(rv["review_date"])
    lo, hi, _ = _range(fact)
    rv = rv[rv["employee_id"].isin(ids) & (rv["review_date"] >= lo) & (rv["review_date"] <= hi + pd.offsets.MonthEnd(0))]
    last = rv.sort_values("review_date").groupby("employee_id").tail(1)
    left_ids = set(fact.loc[fact["exited"], "employee_id"])
    last = last.assign(left=last["employee_id"].isin(left_ids), high_performer=last["performance_rating"] >= 4.0)
    att = con.execute("SELECT employee_id, exit_reason, eligible_for_rehire FROM attrition").df()
    prom_events = int(((fact.sort_values(["employee_id", "month"]).groupby("employee_id")["months_since_last_promotion"]
                        .diff()) < 0).sum())

    def grp(g):
        return {"employees": len(g), "left": int(g["left"].sum()), "left_share": g["left"].mean() if len(g) else None,
                "avg_months_since_promotion": g["months_since_last_promotion"].mean()}

    hp = last[last["high_performer"]]
    p_hp = None
    if len(hp) and (~last["high_performer"]).any():
        tab = [[int(hp["left"].sum()), int((~hp["left"]).sum())],
               [int(last.loc[~last["high_performer"], "left"].sum()), int((~last.loc[~last["high_performer"], "left"]).sum())]]
        p_hp = float(stats.fisher_exact(tab)[1])
    hp_left = hp[hp["left"]].merge(att, on="employee_id", how="left")
    reasons = fact[fact["exited"]].merge(att, on="employee_id", how="left")["exit_reason"].value_counts()
    tot = int(reasons.sum())
    comp_career = int(reasons.get("Compensation", 0) + reasons.get("Career Development", 0))
    msp_bands = []
    d = fact.dropna(subset=["promo_prev"])
    if len(d):
        b = pd.cut(d["promo_prev"], [-1, 12, 24, 36, 100], labels=["0-12", "13-24", "25-36", "37+"])
        for lab, g in d.groupby(b, observed=True):
            msp_bands.append({"band": str(lab), "person_months": len(g), "exits": int(g["exited"].sum()),
                              "monthly_hazard": g["exited"].mean()})
    by_dept = []
    for dep, g in last.groupby("department"):
        by_dept.append({"department": dep, "promotion_ready": int(g["promotion_ready"].sum()),
                        "high_performers": int(g["high_performer"].sum()),
                        "avg_months_since_promotion": g.loc[g["promotion_ready"], "months_since_last_promotion"].mean()})
    s = _surveys(con, f)
    growth = None
    if not s.empty:
        growth = {"growth_opportunities": s["growth_opportunities"].mean(),
                  "compensation_benefits": s["compensation_benefits"].mean(),
                  "all_dimensions_mean": s[DIMENSIONS].mean().mean()}
    return clean({
        "empty": False, "promotion_events_observed": prom_events,
        "reviewed_employees": len(last), "promotion_ready": grp(last[last["promotion_ready"]]),
        "not_promotion_ready": grp(last[~last["promotion_ready"]]),
        "high_performers": grp(hp), "high_vs_other_fisher_p": p_hp, "other_performers": grp(last[~last["high_performer"]]),
        "high_performer_leavers_rehire_eligible_share": hp_left["eligible_for_rehire"].mean() if len(hp_left) else None,
        "exit_reason_compensation_career_share": comp_career / tot if tot else None,
        "months_since_promotion_bands": msp_bands, "by_department": by_dept, "survey_growth": growth})


# --------------------------------------------------------------------------- data quality / meta
def data_quality(con) -> dict:
    rows = con.execute("SELECT * FROM dq_issues ORDER BY severity, check_id").df().to_dict("records")
    log = con.execute("""SELECT table_name, max(run_at) AS last_import, any_value(rows_in_db) AS rows_in_db
                         FROM import_log GROUP BY table_name ORDER BY table_name""").df().to_dict("records")
    return clean({"issues": rows, "tables": log})


def meta(con) -> dict:
    def vals(col, table="employees"):
        return [r[0] for r in con.execute(f"SELECT DISTINCT {col} FROM {table} ORDER BY 1").fetchall()]
    months = [r[0].strftime("%Y-%m") for r in con.execute("SELECT DISTINCT month FROM monthly ORDER BY 1").fetchall()]
    mg = con.execute("SELECT DISTINCT manager_id, department FROM employees ORDER BY 1").fetchall()
    return {"departments": vals("department"), "managers": [{"manager_id": a, "department": b} for a, b in mg],
            "employment_types": vals("employment_type"), "work_locations": vals("work_location"),
            "salary_grades": vals("salary_grade", "monthly"), "months": months,
            "breakdown_fields": list(BREAKDOWN_FIELDS)}
