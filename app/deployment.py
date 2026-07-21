from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from app.settings import Settings


class DeploymentProcess(StrEnum):
    WEB = "web"
    WORKER = "worker"
    SCHEDULER = "scheduler"
    MIGRATION = "migration"


class DeploymentCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    ok: bool
    detail: str


class DeploymentValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    process: DeploymentProcess
    ok: bool
    checks: tuple[DeploymentCheck, ...]


def _database_url_check(settings: Settings) -> DeploymentCheck:
    parsed = urlparse(settings.database_url)
    ok = (
        parsed.scheme in {"postgresql", "postgresql+psycopg"}
        and bool(parsed.hostname)
        and bool(parsed.path.strip("/"))
    )
    return DeploymentCheck(
        name="database_url",
        ok=ok,
        detail="PostgreSQL-compatible DATABASE_URL configured."
        if ok
        else "DATABASE_URL must be a PostgreSQL URL with host and database name.",
    )


def _api_token_check(settings: Settings, process: DeploymentProcess) -> DeploymentCheck:
    if settings.app_env != "production" or process is not DeploymentProcess.WEB:
        return DeploymentCheck(
            name="api_token",
            ok=True,
            detail="API token is not required for this process/environment.",
        )
    ok = settings.denticode_api_token is not None and bool(
        settings.denticode_api_token.get_secret_value()
    )
    return DeploymentCheck(
        name="api_token",
        ok=ok,
        detail="DENTICODE_API_TOKEN configured for production web process."
        if ok
        else "Production web process requires DENTICODE_API_TOKEN from an external secret.",
    )


def _write_guard_check(settings: Settings) -> DeploymentCheck:
    ok = not settings.google_ads_write_enabled and settings.google_ads_execution_kill_switch
    return DeploymentCheck(
        name="write_guards",
        ok=ok,
        detail="Google Ads writes disabled and execution kill switch enabled."
        if ok
        else "Deployment refuses enabled Google Ads writes or disabled execution kill switch.",
    )


def _allowlist_check(settings: Settings) -> DeploymentCheck:
    ok = not settings.allowed_execution_account_ids and not settings.allowed_google_ads_mutations
    return DeploymentCheck(
        name="production_allowlists",
        ok=ok,
        detail="Execution account and mutation allowlists are empty."
        if ok
        else "Production execution allowlists must remain empty for Phase 12.1.",
    )


def validate_deployment_startup(
    process: DeploymentProcess,
    settings: Settings | None = None,
) -> DeploymentValidationResult:
    resolved_settings = settings or Settings()
    checks = (
        _database_url_check(resolved_settings),
        _api_token_check(resolved_settings, process),
        _write_guard_check(resolved_settings),
        _allowlist_check(resolved_settings),
    )
    return DeploymentValidationResult(
        process=process,
        ok=all(check.ok for check in checks),
        checks=checks,
    )
