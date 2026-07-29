import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.api.crm import router as crm_router
from app.api.pubsub import router as pubsub_router
from app.api.v1 import router as api_v1_router
from app.dashboard.router import router as dashboard_router
from app.deployment import DeploymentProcess, validate_deployment_startup


class RootResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: str
    write_access_enabled: bool


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    database_configured: bool
    write_access_enabled: bool


app = FastAPI(
    title="Denticode Ads Optimizer",
    summary="Controlled optimization service for Google Ads and Meta Ads.",
    version="0.1.0",
)


@app.get("/", response_model=RootResponse)
def read_root() -> RootResponse:
    """Return basic service metadata without contacting external services."""
    return RootResponse(
        name="denticode-ads-optimizer",
        status="ready",
        write_access_enabled=False,
    )


@app.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Return an in-process health check."""
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadinessResponse)
def read_ready() -> ReadinessResponse:
    """Return startup readiness without contacting external services."""
    result = validate_deployment_startup(DeploymentProcess.WEB)
    database_configured = any(check.name == "database_url" and check.ok for check in result.checks)
    return ReadinessResponse(
        status="ready" if result.ok else "not_ready",
        database_configured=database_configured,
        write_access_enabled=False,
    )


logger = logging.getLogger(__name__)


@app.exception_handler(SQLAlchemyError)
def database_error_handler(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.warning("database operation failed for read-only API: %s", exc.__class__.__name__)
    return JSONResponse(status_code=503, content={"detail": "database temporarily unavailable"})


@app.exception_handler(RequestValidationError)
def validation_error_handler(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    """Return a stable, sanitized error envelope documented by the API schema."""
    return JSONResponse(status_code=422, content={"detail": "invalid request parameters"})


app.include_router(api_v1_router)
app.include_router(crm_router)
app.include_router(pubsub_router)
app.include_router(dashboard_router)
app.mount(
    "/dashboard/assets", StaticFiles(directory="app/dashboard/static"), name="dashboard-assets"
)


@app.middleware("http")
async def dashboard_security_headers(request: Request, call_next: object) -> object:
    response = await call_next(request)  # type: ignore[operator]
    if request.url.path.startswith("/dashboard"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'none'; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not request.url.path.startswith("/dashboard/assets"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        session_id = getattr(request.state, "dashboard_new_session", None)
        if session_id is not None:
            response.set_cookie(
                "denticode_dashboard_session",
                session_id,
                max_age=8 * 60 * 60,
                httponly=True,
                samesite="strict",
                secure=request.state.dashboard_cookie_secure,
                path="/dashboard",
            )
    return response
