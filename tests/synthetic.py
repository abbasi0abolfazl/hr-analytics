"""Tiny hand-checkable dataset (4 employees x 3 months) used by unit/API tests.

Hand-calculated facts
---------------------
person-months = 10 (Jan 3, Feb 4, Mar 3); exits = 2 (emp 2 in Feb, emp 4 in Mar)
monthly hazard = 2/10 = 0.20 ; annualised turnover = 2 / (10/3) * 12/3 = 2.4
opening headcount = 3, closing headcount (Active in Mar) = 2, hires = 1 (emp 3, Feb)
Sales: 5 person-months, 1 exit ; Technical: 5 person-months, 1 exit
"""
import pandas as pd

D = pd.Timestamp


def frames():
    emp = pd.DataFrame({
        "employee_id": [1, 2, 3, 4], "department": ["Sales", "Sales", "Technical", "Technical"],
        "manager_id": ["MGR_S01", "MGR_S01", "MGR_T01", "MGR_T01"],
        "hire_date": [D("2024-06-01"), D("2024-07-01"), D("2025-02-10"), D("2023-01-01")],
        "initial_salary_grade": ["A", "B", "A", "C"], "employment_type": ["Full-time", "Full-time", "Full-time", "Part-time"],
        "work_location": ["HQ", "Remote", "HQ", "HQ"], "date_of_birth": [D("1990-01-01")] * 4,
        "tenure_months": [7, 6, 0, 24]})
    rows = [  # month, emp, status, perf, eng, skill, msp
        ("2025-01-01", 1, "Active", 3.0, 3.0, 2.0, 10), ("2025-01-01", 2, "Active", 3.5, 3.4, 2.0, 5),
        ("2025-01-01", 4, "Active", 4.0, 3.2, 1.5, 20),
        ("2025-02-01", 1, "Active", 3.0, 3.2, 2.0, 11), ("2025-02-01", 2, "Exited", 3.5, 2.0, 2.0, 6),
        ("2025-02-01", 3, "Active", 3.8, 3.6, 1.8, 0), ("2025-02-01", 4, "Active", 4.0, 3.0, 1.5, 21),
        ("2025-03-01", 1, "Active", 3.0, 3.4, 2.0, 12), ("2025-03-01", 3, "Active", 3.8, 3.8, 1.8, 1),
        ("2025-03-01", 4, "Exited", 4.0, 2.2, 1.5, 22)]
    mo = pd.DataFrame(rows, columns=["month", "employee_id", "employment_status", "performance_rating",
                                     "engagement_score", "skills_gap_score", "months_since_last_promotion"])
    mo["month"] = pd.to_datetime(mo["month"])
    e = emp.set_index("employee_id")
    mo["department"] = mo.employee_id.map(e.department); mo["manager_id"] = mo.employee_id.map(e.manager_id)
    mo["tenure_months"] = 10; mo["salary_grade"] = mo.employee_id.map(e.initial_salary_grade)
    att = pd.DataFrame({"exit_id": ["EX1", "EX2"], "employee_id": [2, 4],
                        "exit_date": [D("2025-02-20"), D("2025-03-12")], "exit_type": ["Voluntary", "Involuntary"],
                        "exit_reason": ["Compensation", "Performance"], "eligible_for_rehire": [True, False],
                        "exit_interview_completed": [True, False]})
    sv = pd.DataFrame({"survey_id": ["Q1_1", "Q1_2", "Q1_4"], "survey_date": [D("2025-03-15")] * 3,
                       "survey_quarter": ["2025-Q1"] * 3, "employee_id": [1, 3, 4],
                       "department": ["Sales", "Technical", "Technical"],
                       "compensation_benefits": [3.0, 4.0, 2.0], "growth_opportunities": [3.0, 4.0, 2.0],
                       "work_culture": [3.0, 3.0, 3.0], "work_life_balance": [3.0, 3.0, 3.0],
                       "management_style": [3.0, 3.0, 3.0], "overall_satisfaction": [3.0, 4.0, 2.0],
                       "recommend_to_friend": [3, 5, 2], "response_status": ["Responded"] * 3})
    rv = pd.DataFrame({"review_id": ["PR1_1", "PR1_3", "PR1_4"], "review_date": [D("2025-03-20")] * 3,
                       "review_quarter": ["2025-Q1"] * 3, "employee_id": [1, 3, 4],
                       "department": ["Sales", "Technical", "Technical"], "manager_id": ["MGR_S01", "MGR_T01", "MGR_T01"],
                       "performance_rating": [3.0, 3.8, 4.5], "skills_gap_score": [2.0, 1.8, 1.5],
                       "promotion_ready": [False, False, True], "months_since_last_promotion": [12, 1, 22]})
    rc = pd.DataFrame({"recruitment_id": ["R1", "R2"], "position": ["Dev", "Rep"], "department": ["Technical", "Sales"],
                       "opening_date": [D("2025-01-05"), D("2025-01-10")], "offer_date": [D("2025-02-01"), D("2025-02-05")],
                       "hire_date": [D("2025-02-10"), pd.NaT], "employee_id": [3, pd.NA],
                       "days_to_fill": [36, 26], "offer_accepted": [True, False], "offers_made": [1, 2],
                       "cost_per_hire": [100.0, None], "quality_of_hire_90d": [None, None],
                       "manager_satisfaction_90d": [None, None]})
    rc["employee_id"] = rc["employee_id"].astype("Int64")
    return {"employees": emp, "monthly": mo, "attrition": att, "surveys": sv, "reviews": rv, "recruitment": rc}
