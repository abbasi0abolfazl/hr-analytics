"""FastAPI service. All endpoints return JSON: {"data": ..., "meta": {...}} or {"error": {...}}."""
from __future__ import annotations

import re
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, metrics
from .config import DEFAULT_DB, STATIC_DIR
from .db import connect

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def _err(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "details": details or {}}}, status_code=status)


def create_app(db_path: str | Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app_: FastAPI):
        yield
        if app_.state.con is not None:
            app_.state.con.close()

    app = FastAPI(title="People Analytics API", version=__version__, lifespan=lifespan,
                  description="HR analytics over 12 months of data (DuckDB). See docs/API.md.")
    path = Path(db_path or DEFAULT_DB)
    app.state.db_path = path
    app.state.con = None
    app.state.meta = None
    if path.exists():
        try:
            app.state.con = connect(path, read_only=True)
            app.state.meta = metrics.meta(app.state.con)
        except Exception:  # noqa: BLE001  (e.g. file exists but schema missing)
            app.state.con = None

    def cursor(request: Request):
        con = request.app.state.con
        if con is None:
            raise ApiError(503, "db_not_ready", f"Database not available at {path}. Run: python scripts/import_data.py")
        return con.cursor()

    def parse_month(v: str | None, name: str, meta: dict) -> date | None:
        if v is None or v == "":
            return None
        if not MONTH_RE.match(v):
            raise ApiError(422, "invalid_month", f"{name} must be formatted YYYY-MM", {"value": v})
        if v not in meta["months"]:
            raise ApiError(422, "month_out_of_range", f"{name}={v} is outside available data",
                           {"available_from": meta["months"][0], "available_to": meta["months"][-1]})
        y, m = v.split("-")
        return date(int(y), int(m), 1)

    def filters(request: Request,
                department: list[str] = Query(default=[]), manager_id: list[str] = Query(default=[]),
                employment_type: list[str] = Query(default=[]), work_location: list[str] = Query(default=[]),
                salary_grade: list[str] = Query(default=[]),
                month_from: str | None = Query(default=None, description="YYYY-MM"),
                month_to: str | None = Query(default=None, description="YYYY-MM")) -> metrics.Filters:
        meta = request.app.state.meta
        if meta is None:
            raise ApiError(503, "db_not_ready", "Database not available. Run: python scripts/import_data.py")
        allowed = {"department": meta["departments"], "manager_id": [m["manager_id"] for m in meta["managers"]],
                   "employment_type": meta["employment_types"], "work_location": meta["work_locations"],
                   "salary_grade": meta["salary_grades"]}
        given = {"department": department, "manager_id": manager_id, "employment_type": employment_type,
                 "work_location": work_location, "salary_grade": salary_grade}
        for k, vals in given.items():
            bad = [v for v in vals if v not in allowed[k]]
            if bad:
                raise ApiError(422, "invalid_filter_value", f"Unknown {k}: {bad}", {"allowed": allowed[k]})
        mf, mt = parse_month(month_from, "month_from", meta), parse_month(month_to, "month_to", meta)
        if mf and mt and mf > mt:
            raise ApiError(422, "invalid_range", "month_from must not be after month_to")
        return metrics.Filters(tuple(department), tuple(manager_id), tuple(employment_type),
                               tuple(work_location), tuple(salary_grade), mf, mt)

    def wrap(data: dict, f: metrics.Filters | None = None, message: str | None = None):
        empty = bool(data.get("empty")) if isinstance(data, dict) else False
        meta = {"filters": f.as_dict() if f else None, "empty": empty, "version": __version__}
        if empty:
            meta["message"] = message or "No data matches the selected filters."
        return {"data": data, "meta": meta}

    # ------------------------------------------------------------------ routes
    @app.get("/api/health", tags=["system"])
    def health(request: Request):
        ok = request.app.state.con is not None
        return JSONResponse({"status": "ok" if ok else "degraded", "db": str(path), "version": __version__},
                            status_code=200 if ok else 503)

    @app.get("/api/meta", tags=["system"])
    def meta_(request: Request, con=Depends(cursor)):
        return wrap(request.app.state.meta)

    @app.get("/api/overview", tags=["analysis"])
    def overview(f: metrics.Filters = Depends(filters), con=Depends(cursor)):
        return wrap(metrics.overview(con, f), f)

    @app.get("/api/attrition/breakdown", tags=["analysis"])
    def breakdown(by: str = Query("department", description="|".join(metrics.BREAKDOWN_FIELDS)),
                  f: metrics.Filters = Depends(filters), con=Depends(cursor)):
        if by not in metrics.BREAKDOWN_FIELDS:
            raise ApiError(422, "invalid_by", f"by must be one of {list(metrics.BREAKDOWN_FIELDS)}")
        return wrap(metrics.attrition_breakdown(con, f, by), f)

    @app.get("/api/attrition/reasons", tags=["analysis"])
    def reasons(f: metrics.Filters = Depends(filters), con=Depends(cursor)):
        return wrap(metrics.exit_reasons(con, f), f)

    @app.get("/api/signals/trajectory", tags=["analysis"])
    def trajectory(f: metrics.Filters = Depends(filters), con=Depends(cursor)):
        return wrap(metrics.pre_exit_trajectory(con, f), f)

    @app.get("/api/signals/drivers", tags=["analysis"])
    def drivers(f: metrics.Filters = Depends(filters), con=Depends(cursor)):
        return wrap(metrics.risk_drivers(con, f), f)

    @app.get("/api/engagement/survey", tags=["analysis"])
    def survey(f: metrics.Filters = Depends(filters), con=Depends(cursor)):
        return wrap(metrics.engagement_survey(con, f), f)

    @app.get("/api/recruitment", tags=["analysis"])
    def recruitment(f: metrics.Filters = Depends(filters), con=Depends(cursor)):
        return wrap(metrics.recruitment(con, f), f)

    @app.get("/api/careers", tags=["analysis"])
    def careers(f: metrics.Filters = Depends(filters), con=Depends(cursor)):
        return wrap(metrics.careers(con, f), f)

    @app.get("/api/data-quality", tags=["system"])
    def dq(con=Depends(cursor)):
        return wrap(metrics.data_quality(con))

    # ------------------------------------------------------------------ errors
    @app.exception_handler(ApiError)
    async def _api_error(_, exc: ApiError):
        return _err(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_, exc: RequestValidationError):
        return _err(422, "validation_error", "Invalid request parameters",
                    {"errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_, exc: StarletteHTTPException):
        return _err(exc.status_code, "not_found" if exc.status_code == 404 else "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_, exc: Exception):
        return _err(500, "internal_error", "Unexpected server error", {"type": type(exc).__name__})

    # ------------------------------------------------------------------ dashboard
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
