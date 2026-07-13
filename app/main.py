from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict


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
