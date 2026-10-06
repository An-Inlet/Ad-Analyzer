import logging

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.api.crm import router as crm_router
from app.api.customer import router as customer_router
from app.api.customer_ad_detail import router as customer_ad_detail_router
from app.api.customer_billing import router as customer_billing_router
from app.api.customer_commerce import router as customer_commerce_router
from app.api.customer_goals import router as customer_goals_router
from app.api.customer_google import router as customer_google_router
from app.api.customer_mandates import router as customer_mandates_router
from app.api.customer_sources import router as customer_sources_router
from app.api.intelligence import router as intelligence_api_router
from app.api.meta import router as meta_api_router
from app.api.pubsub import router as pubsub_router
from app.api.shopify import router as shopify_api_router
from app.api.v1 import router as api_v1_router
from app.dashboard.auth import COOKIE_NAME
from app.dashboard.intelligence import router as intelligence_dashboard_router
from app.dashboard.meta import router as meta_dashboard_router
from app.dashboard.router import router as dashboard_router
from app.dashboard.shopify import router as shopify_dashboard_router
from app.deployment import DeploymentProcess, validate_deployment_startup
from app.portal.router import STATIC as portal_static
from app.portal.router import router as portal_router
from app.shopify.logging import install_access_filter


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
    title="Ad Analyzer",
    summary="Account-scoped advertising analysis and controlled optimization platform.",
    version="0.1.0",
)


@app.get("/", response_model=RootResponse)
def read_root() -> RootResponse:
    """Return basic service metadata without contacting external services."""
    return RootResponse(
        name="ad-analyzer",
        status="ready",
        write_access_enabled=False,
    )


@app.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Return an in-process health check."""
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadinessResponse)
def read_ready(response: Response) -> ReadinessResponse:
    """Return startup readiness without contacting external services."""
    result = validate_deployment_startup(DeploymentProcess.WEB)
    response.status_code = 200 if result.ok else 503
    response.headers["Cache-Control"] = "no-store"
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


install_access_filter()
app.include_router(shopify_api_router)
app.include_router(meta_api_router)
app.include_router(shopify_dashboard_router)
app.include_router(meta_dashboard_router)
app.include_router(api_v1_router)
app.include_router(intelligence_api_router)
app.include_router(crm_router)
app.include_router(customer_router)
app.include_router(portal_router)
app.mount("/app/assets", StaticFiles(directory=portal_static), name="customer-assets")
app.include_router(customer_commerce_router)
app.include_router(customer_goals_router)
app.include_router(customer_mandates_router)
app.include_router(customer_google_router)
app.include_router(customer_ad_detail_router)
app.include_router(customer_sources_router)
app.include_router(customer_billing_router)
app.include_router(pubsub_router)
app.include_router(dashboard_router)
app.include_router(intelligence_dashboard_router)
app.mount(
    "/dashboard/assets", StaticFiles(directory="app/dashboard/static"), name="dashboard-assets"
)


@app.middleware("http")
async def dashboard_security_headers(request: Request, call_next: object) -> object:
    response = await call_next(request)  # type: ignore[operator]
    if request.url.path.startswith("/api/customer/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path == "/app" or request.url.path.startswith("/app/"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
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
                COOKIE_NAME,
                session_id,
                max_age=8 * 60 * 60,
                httponly=True,
                samesite="strict",
                secure=request.state.dashboard_cookie_secure,
                path="/dashboard",
            )
    return response
