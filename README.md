# People Analytics – HR dashboard (DuckDB + FastAPI)

Analysis of 12 months (2025) of HR data: import → DuckDB → Python metrics → JSON API → interactive dashboard
(Persian/English, RTL/LTR) → 10-slide PDF report.

```
data/PA_Task.xlsx        input workbook (6 sheets)
hr_analytics/db.py       schema + idempotent import + data-quality register
hr_analytics/metrics.py  ALL calculations (usable without API/dashboard)
hr_analytics/api.py      FastAPI service (+ serves the dashboard)
hr_analytics/static/     dashboard (HTML/JS/Chart.js, fonts bundled – works offline)
scripts/import_data.py   CLI import      scripts/build_report.py  CLI PDF build
tests/                   unit, API, integration and browser tests
docs/METRICS.md          metric definitions, joins, data-quality decisions
docs/API.md              endpoint reference
report/                  People_Analytics_Report.pdf (+ slides.html)
```

## Quick start (Python 3.10+)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium        # only needed for the browser test / PDF build

python scripts/import_data.py                # creates data/hr.duckdb (safe to re-run: no duplicates)
uvicorn hr_analytics.api:app --port 8000     # API + dashboard
```
Open <http://localhost:8000> (dashboard) or <http://localhost:8000/docs> (interactive OpenAPI).
Custom paths: `python scripts/import_data.py --xlsx path/to/file.xlsx --db path/to/hr.duckdb`;
the API reads `HR_DB_PATH` (default `data/hr.duckdb`).

> DuckDB allows one writer **or** many read-only readers. The API opens the DB read-only, so run the import
> while the API is stopped (or restart the API afterwards).

## Tests
```bash
pytest -q          # 46 tests; the browser test is skipped automatically if Chromium is not installed
```
* `test_import.py` – idempotent re-import, upsert in place, duplicate handling, rollback, validation, real-file counts.
* `test_metrics.py` – hand-calculated values on a 4-employee fixture (headcount identity, turnover, lag/no-leakage,
  Kaplan–Meier with censoring, Wilson CI, declined-offer/missing handling) + regression checks on the real data.
* `test_api.py` – JSON envelope, 422 on invalid input, 200 + `empty` on no data, 404/503 JSON errors, and an
  **integration test** (DuckDB → API → filter changes the payload).
* `test_dashboard_e2e.py` – real browser: the dashboard calls `/api/*`, and changing a filter sends a new request and updates the UI.

## Rebuild the PDF
`python scripts/build_report.py` → `report/People_Analytics_Report.pdf` (numbers come from the same `metrics.py`).

## Design decisions (short)
* **DuckDB** – analytical SQL (window functions for lagged predictors); API opens it read-only.
* **Idempotent import** – primary keys + `INSERT OR REPLACE` in one transaction; run it as often as you like.
* **No leakage** – predictors are last month's values; age is never used (Date of Birth is implausible for ~54% of staff).
* **Missing ≠ 0** – declined offers and immature 90-day metrics stay NULL; *Days to Fill* is reported separately for hires vs declined offers.
* **1–5 scales** are never rescaled to 0–10; *Recommend to Friend* is shown as "% favourable (4–5)", not eNPS.
* Correlation vs causation is stated on every analytical view; see `docs/METRICS.md`.
