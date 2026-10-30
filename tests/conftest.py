import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from hr_analytics import db  # noqa: E402
import synthetic  # noqa: E402

XLSX = ROOT / "data" / "PA_Task.xlsx"


@pytest.fixture()
def synth_db(tmp_path):
    path = tmp_path / "synth.duckdb"
    con = db.connect(path)
    db.import_frames(con, synthetic.frames())
    con.close()
    return path


@pytest.fixture()
def synth_con(synth_db):
    con = db.connect(synth_db, read_only=True)
    yield con
    con.close()


@pytest.fixture(scope="session")
def real_db(tmp_path_factory):
    if not XLSX.exists():
        pytest.skip("PA_Task.xlsx not available")
    path = tmp_path_factory.mktemp("real") / "real.duckdb"
    db.import_workbook(path, XLSX)
    return path


@pytest.fixture()
def real_con(real_db):
    con = db.connect(real_db, read_only=True)
    yield con
    con.close()
