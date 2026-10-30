import pytest
from fastapi.testclient import TestClient

from hr_analytics.api import create_app


@pytest.fixture()
def client(synth_db):
    with TestClient(create_app(synth_db)) as c:
        yield c


@pytest.fixture()
def real_client(real_db):
    with TestClient(create_app(real_db)) as c:
        yield c


ENDPOINTS = ["/api/overview", "/api/attrition/breakdown?by=manager_id", "/api/attrition/reasons", "/api/signals/trajectory",
             "/api/signals/drivers", "/api/engagement/survey", "/api/recruitment", "/api/careers", "/api/data-quality", "/api/meta"]


@pytest.mark.parametrize("url", ENDPOINTS)
def test_endpoints_return_enveloped_json(client, url):
    r = client.get(url)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    j = r.json()
    assert set(j) == {"data", "meta"} and "empty" in j["meta"]


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    m = client.get("/api/meta").json()["data"]
    assert m["departments"] == ["Sales", "Technical"] and m["months"] == ["2025-01", "2025-02", "2025-03"]


@pytest.mark.parametrize("url,code", [
    ("/api/overview?department=Nope", "invalid_filter_value"),
    ("/api/overview?manager_id=XXX", "invalid_filter_value"),
    ("/api/overview?month_from=2025-13", "invalid_month"),
    ("/api/overview?month_from=banana", "invalid_month"),
    ("/api/overview?month_from=2024-01", "month_out_of_range"),
    ("/api/overview?month_from=2025-03&month_to=2025-01", "invalid_range"),
    ("/api/attrition/breakdown?by=date_of_birth", "invalid_by"),
])
def test_invalid_input_returns_422_error_envelope(client, url, code):
    r = client.get(url)
    assert r.status_code == 422
    e = r.json()["error"]
    assert e["code"] == code and e["message"] and isinstance(e["details"], dict)


def test_no_data_is_200_with_empty_flag(client):
    r = client.get("/api/overview?department=Sales&manager_id=MGR_T01")
    assert r.status_code == 200
    j = r.json()
    assert j["meta"]["empty"] is True and j["data"]["empty"] is True and "message" in j["meta"]


def test_unknown_route_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_database_missing_gives_503(tmp_path):
    with TestClient(create_app(tmp_path / "missing.duckdb")) as c:
        assert c.get("/api/health").status_code == 503
        r = c.get("/api/overview")
        assert r.status_code == 503 and r.json()["error"]["code"] == "db_not_ready"


def test_filter_changes_api_result_end_to_end(client):
    """Integration: DuckDB -> metrics -> API; changing the filter changes the payload."""
    allr = client.get("/api/overview").json()["data"]["kpi"]
    sales = client.get("/api/overview?department=Sales").json()["data"]["kpi"]
    late = client.get("/api/overview?month_from=2025-03").json()["data"]["kpi"]
    assert (allr["exits"], sales["exits"], late["exits"]) == (2, 1, 1)
    assert client.get("/api/overview?department=Sales").json()["meta"]["filters"]["department"] == ["Sales"]
    br = client.get("/api/attrition/breakdown?by=department&department=Sales").json()["data"]["rows"]
    assert [r["group"] for r in br] == ["Sales"]


def test_real_data_through_api(real_client):
    k = real_client.get("/api/overview").json()["data"]["kpi"]
    assert k["exits"] == 152 and k["hires"] == 80
    tech = real_client.get("/api/overview?department=Technical").json()["data"]["kpi"]
    assert 0 < tech["exits"] < 152
    d = real_client.get("/api/signals/drivers").json()["data"]
    assert d["model"]["available"] and d["bands"]["engagement"][0]["monthly_hazard"] > 5 * d["bands"]["engagement"][3]["monthly_hazard"]
    assert real_client.get("/api/recruitment").json()["data"]["summary"]["left_in_year"] == 41
