"""Real browser test: the dashboard must call the HTTP API and re-request on filter change."""
import socket
import threading
import time

import pytest

pw = pytest.importorskip("playwright.sync_api")
import uvicorn  # noqa: E402

from hr_analytics.api import create_app  # noqa: E402


@pytest.fixture(scope="module")
def server(real_db):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = uvicorn.Server(uvicorn.Config(create_app(real_db), port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True); t.start()
    for _ in range(50):
        if srv.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True; t.join(5)


def test_dashboard_sends_new_request_on_filter_change(server):
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # browser not installed
            pytest.skip(f"chromium unavailable: {exc}")
        page = b.new_page()
        reqs, errs = [], []
        page.on("request", lambda r: reqs.append(r.url) if "/api/" in r.url else None)
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(server); page.wait_for_selector(".kpi")
        assert any(u.endswith("/api/meta") for u in reqs) and any("/api/overview" in u for u in reqs)
        first = page.inner_text("#kpis")
        n = len(reqs)
        page.click('.chip[data-v="Sales"]'); page.wait_for_function("document.querySelector('#reqlog').textContent.includes('department=Sales')")
        assert any("/api/overview?department=Sales" in u for u in reqs[n:])
        assert page.inner_text("#kpis") != first                      # UI reflects the filtered response
        page.select_option("#f-month_from", "2025-07"); page.wait_for_timeout(500)
        assert any("month_from=2025-07" in u and "department=Sales" in u for u in reqs[n:])
        page.click('#tabs button[data-tab="signals"]'); page.wait_for_selector("#model table")
        assert any("/api/signals/drivers" in u for u in reqs)
        page.click("#lang"); assert page.get_attribute("html", "dir") == "ltr"
        assert errs == []
        b.close()
