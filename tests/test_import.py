import copy

import pandas as pd
import pytest

from hr_analytics import db
import synthetic


def counts(con):
    return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in db.TABLES}


def test_import_is_idempotent(tmp_path):
    con = db.connect(tmp_path / "x.duckdb")
    db.import_frames(con, synthetic.frames())
    first = counts(con)
    db.import_frames(con, synthetic.frames())
    db.import_frames(con, synthetic.frames())
    assert counts(con) == first == {"employees": 4, "monthly": 10, "attrition": 2, "surveys": 3, "reviews": 3, "recruitment": 2}
    assert con.execute("SELECT count(*) FROM (SELECT month, employee_id FROM monthly GROUP BY ALL HAVING count(*)>1)").fetchone()[0] == 0


def test_reimport_updates_in_place(tmp_path):
    con = db.connect(tmp_path / "x.duckdb")
    fr = synthetic.frames()
    db.import_frames(con, fr)
    fr2 = copy.deepcopy(fr)
    fr2["employees"].loc[0, "department"] = "Finance"
    db.import_frames(con, fr2)
    assert con.execute("SELECT department FROM employees WHERE employee_id=1").fetchone()[0] == "Finance"
    assert counts(con)["employees"] == 4


def test_duplicate_source_rows_are_dropped_and_reported(tmp_path):
    con = db.connect(tmp_path / "x.duckdb")
    fr = synthetic.frames()
    fr["employees"] = pd.concat([fr["employees"], fr["employees"].iloc[[0]]], ignore_index=True)
    stats = db.import_frames(con, fr)
    assert stats["employees"]["dupes_dropped"] == 1 and stats["employees"]["rows_in_db"] == 4


def test_missing_sheet_or_column_or_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        db.load_workbook(tmp_path / "nope.xlsx")
    bad = tmp_path / "bad.xlsx"
    with pd.ExcelWriter(bad) as w:
        pd.DataFrame({"a": [1]}).to_excel(w, sheet_name="Employees", index=False)
    with pytest.raises(db.ImportValidationError):
        db.load_workbook(bad)


def test_failed_import_rolls_back(tmp_path):
    con = db.connect(tmp_path / "x.duckdb")
    db.import_frames(con, synthetic.frames())
    fr = synthetic.frames()
    fr["monthly"] = fr["monthly"].drop(columns=["engagement_score"])
    with pytest.raises(Exception):
        db.import_frames(con, fr)
    assert counts(con)["monthly"] == 10


def test_dq_register_and_types(synth_con):
    ids = {r[0]: r[1] for r in synth_con.execute("SELECT check_id, n_rows FROM dq_issues").fetchall()}
    assert ids["monthly_vs_events"] == 0
    assert ids["recruitment_missing_declined"] == 1
    assert ids["promotion_events_zero"] == 0          # synthetic msp only increases
    assert synth_con.execute("SELECT typeof(month) FROM monthly LIMIT 1").fetchone()[0] == "DATE"


def test_real_workbook_counts(real_con):
    assert counts(real_con) == {"employees": 360, "monthly": 3378, "attrition": 152, "surveys": 1058, "reviews": 1051, "recruitment": 108}
