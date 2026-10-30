"""CLI: python scripts/import_data.py [--xlsx data/PA_Task.xlsx] [--db data/hr.duckdb]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hr_analytics.config import DEFAULT_DB, DEFAULT_XLSX
from hr_analytics.db import import_workbook

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Idempotent import of the HR workbook into DuckDB")
    ap.add_argument("--xlsx", default=str(DEFAULT_XLSX))
    ap.add_argument("--db", default=str(DEFAULT_DB))
    a = ap.parse_args()
    print(json.dumps(import_workbook(a.db, a.xlsx), indent=2))
