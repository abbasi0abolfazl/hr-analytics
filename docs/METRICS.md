# Metric definitions, joins and data-quality decisions

## Grain and joins
* `v_fact_month` = `monthly ⨝ employees` on `employee_id` (1 row = employee × month). Department/manager are taken from `employees`
  (they are identical to the monthly columns – verified). `manager_id` is a manager key, never an employee id.
* Surveys / reviews join on `employee_id` **and** their own date (survey month = month of `survey_date`); recruitment joins to employees
  only through `employee_id` of *hired* rows (declined offers have none).
* Exits are counted from the monthly `Exited` flag (fully consistent with Attrition Events: 0 mismatches).

## Definitions
| metric | definition |
|---|---|
| headcount(month) | employees with a row that month (the exit month is included) |
| monthly attrition rate (hazard) | exits ÷ person-months |
| annualised turnover | exits ÷ mean monthly headcount × 12 ÷ months in range |
| opening / closing headcount | headcount(first month) − hires(first month) / Active in last month; opening + hires − exits = closing |
| lagged predictors | previous-month engagement, performance, skills gap, months since promotion (avoids leakage from the exit month) |
| new hire | `hire_date` ≥ first data month (80 people = Recruitment hires) |
| high performer | latest Performance Review rating ≥ 4.0 (Promotion Ready ⇔ rating > 4 in the data) |
| survival (new hires) | Kaplan–Meier, censored at 2025-12-31 |
| Recommend favourable | share of 4–5 on a 1–5 scale (not eNPS) |
| CI | Wilson 95% for rates; Wald 95% for odds ratios |

## Models
Person-month logistic regression: `exit ~ engagement_prev + performance_prev + skills_gap_prev + months_since_promo_prev/12 + new_hire + H2`.
Manager effect = likelihood-ratio test adding manager dummies. Associations only – **no causal claim**.
Refused when < 15 exits.

## Data-quality decisions (also at `/api/data-quality`)
1. Date of Birth implies age < 18 at hire for ~54% of staff → age not used.
2. One exit before hire date → kept in counts, excluded from survival.
3. Months Since Last Promotion never resets → "no promotions recorded" (needs HRIS confirmation).
4. Missing Hire Date/EmployeeID/Cost = declined offers; missing d90 = hired < 90 days before year end → NULL, never zero.
5. Days to Fill ends at hire date (hires) or offer date (declined) → reported separately.
6. Quality of Hire 90d exists for 21 people who left before day 90 → descriptive only.
7. Survey contains only respondents still employed (survivorship bias); non-response is not recorded.
