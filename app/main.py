import logging

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.api.crm import router as crm_router
from app.api.customer import router as customer_router
from app.api.customer_account_diagnostics import router as customer_account_diagnostics_router
from app.api.customer_acquisitions import router as customer_acquisitions_router
from app.api.customer_activity import router as customer_activity_router
from app.api.customer_ad_detail import router as customer_ad_detail_router
from app.api.customer_billing import router as customer_billing_router
from app.api.customer_budget_mandates import router as customer_budget_mandates_router
from app.api.customer_campaign_review import router as customer_campaign_review_router
from app.api.customer_candidates import router as customer_candidates_router
from app.api.customer_commerce import router as customer_commerce_router
from app.api.customer_descriptive import router as customer_descriptive_router
from app.api.customer_execution import router as customer_execution_router
from app.api.customer_exports import router as customer_exports_router
from app.api.customer_goals import router as customer_goals_router
from app.api.customer_google import router as customer_google_router
from app.api.customer_initial_execution import router as customer_initial_execution_router
from app.api.customer_initial_planning import router as customer_initial_planning_router
from app.api.customer_lifecycle import router as customer_lifecycle_router
from app.api.customer_mandates import router as customer_mandates_router
from app.api.customer_meta import router as customer_meta_router
from app.api.customer_optimization import router as customer_optimization_router
from app.api.customer_outcomes import router as customer_outcomes_router
from app.api.customer_plan_review import router as customer_plan_review_router
from app.api.customer_planning_budget_owners import router as customer_planning_budget_owners_router
from app.api.customer_planning_catalog import router as customer_planning_catalog_router
from app.api.customer_planning_documents import router as customer_planning_documents_router
from app.api.customer_planning_target_catalog import (
    router as customer_planning_target_catalog_router,
)
from app.api.customer_reported_feedback import router as customer_reported_feedback_router
from app.api.customer_reporting import router as customer_reporting_router
from app.api.customer_reporting_capture import router as customer_reporting_capture_router
from app.api.customer_reporting_range import router as customer_reporting_range_router
from app.api.customer_session_automation import router as customer_session_automation_router
from app.api.customer_shopify import router as customer_shopify_router
from app.api.customer_social_execution import router as customer_social_execution_router
from app.api.customer_social_review import router as customer_social_review_router
from app.api.customer_sources import router as customer_sources_router
from app.api.customer_tiktok_discovery import router as customer_tiktok_discovery_router
from app.api.customer_tiktok_linked import router as customer_tiktok_linked_router
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
from app.database.models import register_models
from app.deployment import DeploymentProcess, validate_deployment_startup
from app.initial_planning.budget_mandate_configuration import BudgetMandateConfigurationError
from app.planning_reporting.configuration import PlanningReportingConfigurationError
from app.portal.auth import customer_content_security_policy
from app.portal.auth import router as browser_auth_router
from app.portal.router import STATIC as portal_static
from app.portal.router import router as portal_router
from app.production_runtime.configuration import GoogleRuntimeConfigurationError
from app.production_runtime.meta_configuration import MetaRuntimeConfigurationError
from app.readiness import database_available, database_schema_current
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
    database_available: bool
    schema_revision_current: bool
    write_access_enabled: bool


register_models()

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
    """Require valid startup configuration and a read-only database dependency probe."""
    result = validate_deployment_startup(DeploymentProcess.WEB)
    available = result.ok and database_available()
    schema_current = available and database_schema_current()
    response.status_code = 200 if schema_current else 503
    response.headers["Cache-Control"] = "no-store"
    database_configured = any(check.name == "database_url" and check.ok for check in result.checks)
    return ReadinessResponse(
        status="ready" if schema_current else "not_ready",
        database_configured=database_configured,
        database_available=available,
        schema_revision_current=schema_current,
        write_access_enabled=False,
    )


logger = logging.getLogger(__name__)


@app.exception_handler(BudgetMandateConfigurationError)
async def budget_mandate_configuration_error(
    _request: Request, _exc: BudgetMandateConfigurationError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "budget_mandate_configuration_invalid"})


@app.exception_handler(MetaRuntimeConfigurationError)
@app.exception_handler(GoogleRuntimeConfigurationError)
async def google_runtime_configuration_error(
    _request: Request, _exc: GoogleRuntimeConfigurationError
) -> JSONResponse:
    return JSONResponse(
        status_code=503, content={"detail": "google_execution_configuration_invalid"}
    )


@app.exception_handler(PlanningReportingConfigurationError)
def planning_configuration_error(
    _request: Request, _exc: PlanningReportingConfigurationError
) -> JSONResponse:
    return JSONResponse(
        status_code=503, content={"detail": "planning_reporting_configuration_invalid"}
    )


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
app.include_router(customer_activity_router)
app.include_router(customer_descriptive_router)
app.include_router(customer_router)
app.include_router(portal_router)
app.include_router(browser_auth_router)
app.mount("/app/assets", StaticFiles(directory=portal_static), name="customer-assets")
app.include_router(customer_commerce_router)
app.include_router(customer_outcomes_router)
app.include_router(customer_goals_router)
app.include_router(customer_mandates_router)
app.include_router(customer_google_router)
app.include_router(customer_meta_router)
app.include_router(customer_campaign_review_router)
app.include_router(customer_lifecycle_router)
app.include_router(customer_exports_router)
app.include_router(customer_execution_router)
app.include_router(customer_tiktok_discovery_router)
app.include_router(customer_tiktok_linked_router)
app.include_router(customer_plan_review_router)
app.include_router(customer_initial_planning_router)
app.include_router(customer_initial_execution_router)
app.include_router(customer_budget_mandates_router)
app.include_router(customer_reported_feedback_router)
app.include_router(customer_account_diagnostics_router)
app.include_router(customer_planning_target_catalog_router)
app.include_router(customer_planning_budget_owners_router)
app.include_router(customer_session_automation_router)
app.include_router(customer_social_review_router)

app.include_router(customer_social_execution_router)
app.include_router(customer_optimization_router)
app.include_router(customer_planning_catalog_router)
app.include_router(customer_planning_documents_router)
app.include_router(customer_candidates_router)
app.include_router(customer_reporting_router)
app.include_router(customer_reporting_capture_router)
app.include_router(customer_reporting_range_router)
app.include_router(customer_ad_detail_router)
app.include_router(customer_sources_router)
app.include_router(customer_acquisitions_router)
app.include_router(customer_shopify_router)
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
        response.headers["Content-Security-Policy"] = customer_content_security_policy()
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
