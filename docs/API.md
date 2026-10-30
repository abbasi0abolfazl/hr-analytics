# API reference

Base URL `http://localhost:8000`. All responses are JSON. Success: `{"data": ..., "meta": {"filters", "empty", "version", "message?"}}`.
Error: `{"error": {"code", "message", "details"}}`. Interactive docs: `/docs`.

## Common filters (all `/api/*` analysis endpoints; repeatable where noted)
| param | values |
|---|---|
| `department`, `manager_id`, `employment_type`, `work_location`, `salary_grade` | repeatable; must exist in `/api/meta` |
| `month_from`, `month_to` | `YYYY-MM` within the data range; `month_from <= month_to` |

## Endpoints
| endpoint | returns |
|---|---|
| `GET /api/health` | status, DB path (503 if the DB is missing) |
| `GET /api/meta` | filter options, months, breakdown fields |
| `GET /api/overview` | KPIs (headcount, hires, exits, turnover, H1/H2 rate) + monthly series |
| `GET /api/attrition/breakdown?by=` | by `department|manager_id|employment_type|work_location|salary_grade|tenure_band|hire_cohort`: exits, rate, Wilson CI, H1/H2 |
| `GET /api/attrition/reasons` | exit reason × type |
| `GET /api/signals/trajectory` | engagement/performance k months before exit vs stayers |
| `GET /api/signals/drivers` | hazard by quartile of lagged predictors + logistic model (odds ratios, AUC, manager LR test) |
| `GET /api/engagement/survey` | dimensions by quarter, leavers vs stayers (Mann-Whitney), coverage, correlations |
| `GET /api/recruitment` | funnel, new-hire attrition, Kaplan–Meier, cost, reasons |
| `GET /api/careers` | promotion-ready, high performers, months-since-promotion hazard |
| `GET /api/data-quality` | data-quality register + import log |

## Errors
| status | code | when |
|---|---|---|
| 422 | `invalid_filter_value` / `invalid_month` / `month_out_of_range` / `invalid_range` / `invalid_by` / `validation_error` | bad input (details list allowed values) |
| 404 | `not_found` | unknown route |
| 503 | `db_not_ready` | database missing – run the import |
| 500 | `internal_error` | unexpected failure (no stack trace leaked) |

**No data**: filters that match nothing return **200** with `data.empty = true` and `meta.message`; the dashboard shows an empty-state banner.
The logistic model returns `{"available": false, "reason": ...}` when there are fewer than 15 exits.

Example: `GET /api/overview?department=Sales&department=Technical&month_from=2025-07`
