import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import router as api_v1_router


class RootResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: str
    write_access_enabled: bool


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str


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
