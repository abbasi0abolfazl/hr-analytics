import math
from datetime import date

import pytest

from hr_analytics import metrics as M

F = M.Filters()


def test_overview_hand_calculated(synth_con):
    k = M.overview(synth_con, F)["kpi"]
    assert (k["opening_headcount"], k["closing_headcount"], k["hires"], k["exits"]) == (3, 2, 1, 2)
    assert k["voluntary_exits"] == 1 and k["involuntary_exits"] == 1
    assert k["annualized_turnover"] == pytest.approx(2.4, abs=1e-3)
    # identity: opening + hires - exits = closing
    assert k["opening_headcount"] + k["hires"] - k["exits"] == k["closing_headcount"]


def test_monthly_series(synth_con):
    mon = M.overview(synth_con, F)["monthly"]
    assert [(m["headcount"], m["exits"], m["hires"]) for m in mon] == [(3, 0, 0), (4, 1, 1), (3, 1, 0)]
    assert mon[1]["monthly_hazard"] == pytest.approx(0.25)


def test_breakdown_by_department(synth_con):
    rows = {r["group"]: r for r in M.attrition_breakdown(synth_con, F, "department")["rows"]}
    assert rows["Sales"]["person_months"] == 5 and rows["Sales"]["exits"] == 1
    assert rows["Sales"]["monthly_hazard"] == pytest.approx(0.2)
    assert sum(r["exits"] for r in rows.values()) == 2


def test_breakdown_rejects_unknown_field(synth_con):
    with pytest.raises(ValueError):
        M.attrition_breakdown(synth_con, F, "date_of_birth")      # age must never be a breakdown


def test_filter_changes_result_and_empty_state(synth_con):
    assert M.overview(synth_con, M.Filters(departments=("Sales",)))["kpi"]["exits"] == 1
    assert M.overview(synth_con, M.Filters(month_from=date(2025, 3, 1)))["kpi"]["exits"] == 1
    assert M.overview(synth_con, M.Filters(departments=("Sales",), manager_ids=("MGR_T01",))) == {"empty": True}


def test_lag_features_do_not_leak_exit_month(synth_con):
    df = M.get_fact(synth_con, F)
    r = df[(df.employee_id == 2) & (df.exited)].iloc[0]      # emp 2 exits in Feb with eng 2.0
    assert r["eng_prev"] == pytest.approx(3.4)              # January value, not the exit month's 2.0
    assert math.isnan(df[(df.employee_id == 1) & (df.month == "2025-01-01")].iloc[0]["eng_prev"])


def test_pre_exit_trajectory(synth_con):
    t = M.pre_exit_trajectory(synth_con, F)
    k0 = [r for r in t["rows"] if r["months_before_exit"] == 0][0]
    assert k0["n"] == 2 and k0["engagement"] == pytest.approx((2.0 + 2.2) / 2)
    stay = [3.0, 3.2, 3.4, 3.6, 3.8]                        # emps 1 and 3 never leave
    assert t["stayers_baseline"]["engagement"] == pytest.approx(sum(stay) / 5)


def test_wilson_interval():
    lo, hi = M.wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert M.wilson(0, 0) == (None, None)
    assert M.wilson(0, 10)[0] == 0.0


def test_kaplan_meier_with_censoring():
    km = M.kaplan_meier([5, 10, 10, 20], [1, 1, 0, 1], [5, 10, 20])
    assert [round(x["survival"], 4) for x in km] == [0.75, 0.5, 0.0]


def test_logit_refuses_tiny_samples_and_works_on_real(synth_con, real_con):
    m = M.risk_drivers(synth_con, F)["model"]
    assert m["available"] is False and "too few" in m["reason"]
    real = M.risk_drivers(real_con, F)["model"]
    eng = real["terms"][0]
    assert eng["term"].startswith("engagement") and eng["odds_ratio"] < 0.4 and eng["p_value"] < 0.001
    perf = [t for t in real["terms"] if t["term"].startswith("performance")][0]
    assert perf["p_value"] > 0.05                           # performance is NOT a significant predictor


def test_recruitment_separates_declined_and_never_zero_fills(synth_con):
    r = M.recruitment(synth_con, F)
    assert r["funnel"]["requisitions"] == 2 and r["funnel"]["accepted"] == 1 and r["funnel"]["declined"] == 1
    assert r["funnel"]["days_to_fill_hired"] == 36 and r["funnel"]["days_to_fill_declined_to_offer"] == 26
    assert r["funnel"]["avg_cost_per_hire"] == 100.0        # declined offer's missing cost ignored, not 0
    assert r["funnel"]["avg_quality_90d"] is None           # all missing -> None, not 0
    assert r["summary"]["hires"] == 1 and r["summary"]["left_in_year"] == 0
    assert M.recruitment(synth_con, M.Filters(month_from=date(2025, 3, 1)))["empty"] is True   # no offers after Feb


def test_survey_gap_and_scale(synth_con):
    s = M.engagement_survey(synth_con, F)
    g = {x["dimension"]: x for x in s["gap"]}
    assert g["compensation_benefits"]["leavers"] == pytest.approx(2.0)    # emp 4 left
    assert g["compensation_benefits"]["stayers"] == pytest.approx(3.5)
    assert s["coverage"][0]["recommend_favourable_pct"] == pytest.approx(1 / 3, abs=1e-3)   # only the "5" is favourable


def test_careers_reports_no_promotions(synth_con):
    c = M.careers(synth_con, F)
    assert c["promotion_events_observed"] == 0
    assert c["promotion_ready"]["employees"] == 1 and c["promotion_ready"]["left"] == 1


def test_clean_makes_json_safe():
    import json
    import numpy as np
    out = M.clean({"a": float("nan"), "b": np.int64(3), "c": [np.float64(1.23456789)], "d": np.bool_(True)})
    assert json.dumps(out) == '{"a": null, "b": 3, "c": [1.2346], "d": true}'


def test_real_data_known_totals(real_con):
    k = M.overview(real_con, F)["kpi"]
    assert (k["opening_headcount"], k["closing_headcount"], k["hires"], k["exits"]) == (280, 208, 80, 152)
    assert k["hazard_h2"] > 2.5 * k["hazard_h1"]
