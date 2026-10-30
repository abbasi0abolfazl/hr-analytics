import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XLSX = Path(os.environ.get("HR_XLSX_PATH", ROOT / "data" / "PA_Task.xlsx"))
DEFAULT_DB = Path(os.environ.get("HR_DB_PATH", ROOT / "data" / "hr.duckdb"))
STATIC_DIR = Path(__file__).resolve().parent / "static"
