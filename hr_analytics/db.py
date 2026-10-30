"""Schema + idempotent import of PA_Task.xlsx into DuckDB.

Idempotency: every table has a primary key and rows are written with
``INSERT OR REPLACE`` inside one transaction, so re-running the import never
creates duplicates (it refreshes rows in place).
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

# table -> (sheet name, [(column, sql type)], primary key)
TABLES: dict[str, tuple[str, list[tuple[str, str]], list[str]]] = {
    "employees": ("Employees", [
        ("employee_id", "INTEGER"), ("department", "VARCHAR"), ("manager_id", "VARCHAR"),
        ("hire_date", "DATE"), ("initial_salary_grade", "VARCHAR"), ("employment_type", "VARCHAR"),
        ("work_location", "VARCHAR"), ("date_of_birth", "DATE"), ("tenure_months", "INTEGER")],
        ["employee_id"]),
    "monthly": ("Monthly Employee Data", [
        ("month", "DATE"), ("employee_id", "INTEGER"), ("department", "VARCHAR"),
        ("manager_id", "VARCHAR"), ("employment_status", "VARCHAR"), ("tenure_months", "INTEGER"),
        ("performance_rating", "DOUBLE"), ("engagement_score", "DOUBLE"),
        ("skills_gap_score", "DOUBLE"), ("salary_grade", "VARCHAR"),
        ("months_since_last_promotion", "INTEGER")],
        ["month", "employee_id"]),
    "attrition": ("Attrition Events", [
        ("exit_id", "VARCHAR"), ("employee_id", "INTEGER"), ("exit_date", "DATE"),
        ("exit_type", "VARCHAR"), ("exit_reason", "VARCHAR"), ("eligible_for_rehire", "BOOLEAN"),
        ("exit_interview_completed", "BOOLEAN")],
        ["exit_id"]),
    "surveys": ("Engagement Surveys", [
        ("survey_id", "VARCHAR"), ("survey_date", "DATE"), ("survey_quarter", "VARCHAR"),
        ("employee_id", "INTEGER"), ("department", "VARCHAR"), ("compensation_benefits", "DOUBLE"),
        ("growth_opportunities", "DOUBLE"), ("work_culture", "DOUBLE"),
        ("work_life_balance", "DOUBLE"), ("management_style", "DOUBLE"),
        ("overall_satisfaction", "DOUBLE"), ("recommend_to_friend", "DOUBLE"),
        ("response_status", "VARCHAR")],
        ["survey_id"]),
    "reviews": ("Performance Reviews", [
        ("review_id", "VARCHAR"), ("review_date", "DATE"), ("review_quarter", "VARCHAR"),
        ("employee_id", "INTEGER"), ("department", "VARCHAR"), ("manager_id", "VARCHAR"),
        ("performance_rating", "DOUBLE"), ("skills_gap_score", "DOUBLE"),
        ("promotion_ready", "BOOLEAN"), ("months_since_last_promotion", "INTEGER")],
        ["review_id"]),
    "recruitment": ("Recruitment", [
        ("recruitment_id", "VARCHAR"), ("position", "VARCHAR"), ("department", "VARCHAR"),
        ("opening_date", "DATE"), ("offer_date", "DATE"), ("hire_date", "DATE"),
        ("employee_id", "INTEGER"), ("days_to_fill", "INTEGER"), ("offer_accepted", "BOOLEAN"),
        ("offers_made", "INTEGER"), ("cost_per_hire", "DOUBLE"), ("quality_of_hire_90d", "DOUBLE"),
        ("manager_satisfaction_90d", "DOUBLE")],
        ["recruitment_id"]),
}

VIEW_SQL = """
CREATE OR REPLACE VIEW v_fact_month AS
SELECT m.month, m.employee_id,
       e.department, e.manager_id, e.employment_type, e.work_location,
       m.salary_grade, e.hire_date,
       (e.hire_date >= (SELECT min(month) FROM monthly)) AS is_new_hire,
       (m.employment_status = 'Exited') AS exited,
       m.tenure_months, m.performance_rating, m.engagement_score, m.skills_gap_score,
       m.months_since_last_promotion,
       lag(m.engagement_score) OVER w AS eng_prev,
       lag(m.performance_rating) OVER w AS perf_prev,
       lag(m.skills_gap_score) OVER w AS skill_prev,
       lag(m.months_since_last_promotion) OVER w AS promo_prev
FROM monthly m JOIN employees e USING (employee_id)
WINDOW w AS (PARTITION BY m.employee_id ORDER BY m.month)
"""


class ImportValidationError(ValueError):
    """Raised when the workbook does not look like the expected dataset."""


_ALIASES = {"employeeid": "employee_id", "managerid": "manager_id", "surveyid": "survey_id",
            "reviewid": "review_id", "recruitmentid": "recruitment_id", "exitid": "exit_id"}


def _norm(c: str) -> str:
    n = str(c).strip().lower().replace(" ", "_")
    return _ALIASES.get(n, n)


def load_workbook(path: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input workbook not found: {path}")
    raw = pd.read_excel(path, sheet_name=None)
    frames = {}
    for table, (sheet, cols, _) in TABLES.items():
        if sheet not in raw:
            raise ImportValidationError(f"Missing sheet '{sheet}' (have: {list(raw)})")
        df = raw[sheet].copy()
        df.columns = [_norm(c) for c in df.columns]
        missing = [c for c, _ in cols if c not in df.columns]
        if missing:
            raise ImportValidationError(f"Sheet '{sheet}' lacks columns {missing}")
        frames[table] = df
    return frames


def connect(path: str | Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = Path(path)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def init_schema(con) -> None:
    for table, (_, cols, pk) in TABLES.items():
        body = ", ".join(f"{c} {t}" for c, t in cols)
        con.execute(f"CREATE TABLE IF NOT EXISTS {table} ({body}, PRIMARY KEY ({', '.join(pk)}))")
    con.execute("""CREATE TABLE IF NOT EXISTS dq_issues(
        check_id VARCHAR PRIMARY KEY, severity VARCHAR, table_name VARCHAR, n_rows INTEGER,
        description_en VARCHAR, description_fa VARCHAR, decision_en VARCHAR, decision_fa VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS import_log(
        run_at TIMESTAMP, table_name VARCHAR, rows_in INTEGER, dupes_dropped INTEGER, rows_in_db INTEGER)""")
    con.execute(VIEW_SQL)


def import_frames(con, frames: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Upsert all tables in one transaction. Returns per-table stats."""
    init_schema(con)
    stats: dict[str, dict] = {}
    con.execute("BEGIN")
    try:
        for table, (_, cols, pk) in TABLES.items():
            df = frames[table][[c for c, _ in cols]].copy()
            n_in = len(df)
            df = df.drop_duplicates(subset=pk, keep="last")
            con.register("src", df)
            sel = ", ".join(f"TRY_CAST({c} AS {t}) AS {c}" for c, t in cols)
            con.execute(f"INSERT OR REPLACE INTO {table} SELECT {sel} FROM src")
            con.unregister("src")
            n_db = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            stats[table] = {"rows_in": n_in, "dupes_dropped": n_in - len(df), "rows_in_db": n_db}
            con.execute("INSERT INTO import_log VALUES (now(), ?, ?, ?, ?)",
                        [table, n_in, n_in - len(df), n_db])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    rebuild_dq(con)
    return stats


def import_workbook(db_path: str | Path, xlsx_path: str | Path) -> dict[str, dict]:
    frames = load_workbook(xlsx_path)
    con = connect(db_path)
    try:
        return import_frames(con, frames)
    finally:
        con.close()


def rebuild_dq(con) -> None:
    """Re-derive the data-quality register from the loaded tables."""
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    checks = [
        ("dob_implausible", "high", "employees",
         q("SELECT count(*) FROM employees WHERE date_diff('year', date_of_birth, hire_date) < 18"),
         "Date of Birth implies age < 18 at hire date for many employees.",
         "تاریخ تولد برای بسیاری از کارکنان سن زیر ۱۸ سال در زمان استخدام نشان می‌دهد.",
         "Age is NOT used in any analysis.", "متغیر سن در هیچ تحلیلی استفاده نشده است."),
        ("exit_before_hire", "medium", "attrition",
         q("SELECT count(*) FROM attrition a JOIN employees e USING(employee_id) WHERE a.exit_date < e.hire_date"),
         "Exit Date precedes Hire Date.", "تاریخ خروج پیش از تاریخ استخدام است.",
         "Kept in counts; excluded from time-to-exit (survival) analysis.",
         "در شمارش خروج‌ها نگه داشته شد؛ از تحلیل زمان تا خروج حذف شد."),
        ("tenure_mismatch", "low", "employees",
         q("""SELECT count(*) FROM employees WHERE abs(tenure_months -
              date_diff('month', hire_date, (SELECT min(month) FROM monthly))) > 2
              AND hire_date < (SELECT min(month) FROM monthly)"""),
         "Tenure Months differs by more than 2 months from the value implied by Hire Date.",
         "Tenure Months بیش از ۲ ماه با مقدار محاسبه‌شده از Hire Date اختلاف دارد.",
         "Hire Date is used for cohorts; monthly Tenure Months is used for tenure bands.",
         "برای کوهورت‌ها از Hire Date و برای گروه‌های سابقه از Tenure Months ماهانه استفاده شد."),
        ("monthly_vs_events", "info", "monthly",
         q("""SELECT count(*) FROM monthly m LEFT JOIN attrition a USING(employee_id)
              WHERE m.employment_status='Exited' AND (a.exit_id IS NULL
                    OR date_trunc('month', a.exit_date) <> m.month)"""),
         "Exited rows in monthly data that do not match an Attrition Event month (0 = fully consistent).",
         "ردیف‌های Exited ماهانه که با ماه رویداد خروج همخوان نیستند (۰ یعنی کاملاً سازگار).",
         "Exits are counted from the monthly Exited flag.", "خروج‌ها از پرچم Exited ماهانه شمرده می‌شوند."),
        ("promotion_events_zero", "high", "monthly",
         q("""SELECT count(*) FROM (SELECT months_since_last_promotion - lag(months_since_last_promotion)
              OVER (PARTITION BY employee_id ORDER BY month) AS d FROM monthly) WHERE d < 0"""),
         "Months Since Last Promotion never resets (count of resets shown): no promotion is observable in the whole year.",
         "Months Since Last Promotion در هیچ موردی کاهش نمی‌یابد (تعداد ریست‌ها نمایش داده شده): در کل سال هیچ ارتقایی قابل مشاهده نیست.",
         "Reported as 'no recorded promotions'; must be confirmed with HRIS (real freeze vs. untracked).",
         "به‌عنوان «ارتقای ثبت‌نشده» گزارش شد؛ باید با HRIS تأیید شود (فریز واقعی یا ثبت‌نشدن)."),
        ("recruitment_missing_declined", "info", "recruitment",
         q("SELECT count(*) FROM recruitment WHERE hire_date IS NULL AND offer_accepted = false"),
         "Missing Hire Date / EmployeeID / Cost occur for declined offers.",
         "نبود Hire Date / EmployeeID / Cost مربوط به Offerهای ردشده است.",
         "Declined offers are excluded from hire metrics; never imputed as zero.",
         "Offerهای ردشده از شاخص‌های استخدام حذف شدند؛ هیچ‌گاه صفر فرض نشدند."),
        ("d90_not_matured", "info", "recruitment",
         q("SELECT count(*) FROM recruitment WHERE hire_date IS NOT NULL AND quality_of_hire_90d IS NULL"),
         "Hires without 90-day metrics (fewer than 90 days observed by year end).",
         "استخدام‌هایی که شاخص ۹۰ روزه ندارند (تا پایان سال ۹۰ روز نگذشته).",
         "Treated as missing (not zero); excluded from d90 averages.",
         "به‌صورت Missing در نظر گرفته شد؛ از میانگین d90 حذف شد."),
        ("d90_after_early_exit", "medium", "recruitment",
         q("""SELECT count(*) FROM recruitment r JOIN attrition a USING(employee_id)
              WHERE date_diff('day', r.hire_date, a.exit_date) < 90 AND r.quality_of_hire_90d IS NOT NULL"""),
         "Quality/satisfaction at 90 days is populated for hires who left before day 90 - the measurement point is ambiguous.",
         "شاخص‌های ۹۰ روزه برای افرادی که پیش از روز ۹۰ خارج شده‌اند هم پر شده است؛ نقطه اندازه‌گیری مبهم است.",
         "Quality of Hire is used descriptively only, never as a predictor of exit.",
         "Quality of Hire فقط توصیفی استفاده شد و به‌عنوان پیش‌بینی‌کننده خروج به کار نرفت."),
        ("days_to_fill_semantics", "info", "recruitment",
         q("SELECT count(*) FROM recruitment WHERE hire_date IS NULL"),
         "Days to Fill ends at Hire Date for hires but at Offer Date for declined offers.",
         "Days to Fill برای استخدام‌ها تا Hire Date و برای Offer ردشده تا Offer Date است.",
         "Reported separately for the two groups.", "برای این دو گروه جداگانه گزارش می‌شود."),
        ("survey_survivorship", "medium", "surveys",
         q("SELECT count(*) FROM surveys WHERE response_status <> 'Responded'"),
         "Only respondents still employed appear; non-responses are not recorded (count shown = non-responses).",
         "فقط پاسخ‌دهندگانِ شاغل در داده‌اند و پاسخ‌نداده ثبت نشده است (عدد نمایش‌داده‌شده = تعداد پاسخ‌نداده).",
         "Survey results are interpreted with survivorship bias in mind; coverage is reported.",
         "نتایج Survey با لحاظ survivorship bias تفسیر می‌شود و پوشش گزارش می‌شود."),
        ("eng_scale", "info", "surveys", 0,
         "Recommend to Friend is on a 1-5 scale, not 0-10.",
         "Recommend to Friend در مقیاس ۱ تا ۵ است، نه ۰ تا ۱۰.",
         "Reported as % favourable (4-5); never labelled eNPS.",
         "به‌صورت درصد مطلوب (۴ و ۵) گزارش می‌شود و eNPS نامیده نمی‌شود."),
    ]
    con.execute("DELETE FROM dq_issues")
    con.executemany("INSERT INTO dq_issues VALUES (?,?,?,?,?,?,?,?)",
                    [(a, b, c, int(d), e, f, g, h) for a, b, c, d, e, f, g, h in checks])
