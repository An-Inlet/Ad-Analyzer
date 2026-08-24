from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import ArgumentError

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


class RuntimeProcessConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    process: DeploymentProcess
    command: tuple[str, ...]
    concurrency: int
    timeout_seconds: int
    graceful_shutdown_seconds: int
    restart_policy: str
    run_migrations_before_start: bool = False


POSTGRESQL_SCHEMES = {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}
PLACEHOLDER_FRAGMENTS = ("placeholder", "replace-with", "changeme", "example", "dummy")


def _is_placeholder(value: str | None) -> bool:
    return (
        value is None
        or not value.strip()
        or any(fragment in value.lower() for fragment in PLACEHOLDER_FRAGMENTS)
    )


def _database_url_check(settings: Settings) -> DeploymentCheck:
    try:
        parsed = settings.resolved_database_url
    except ArgumentError:
        return DeploymentCheck(
            name="database_url",
            ok=False,
            detail="Database configuration must contain a valid SQLAlchemy PostgreSQL URL.",
        )
    socket_configured = settings.cloud_sql_configuration_complete
    location_valid = socket_configured if settings.uses_cloud_sql_socket else bool(parsed.host)
    password = parsed.password
    ok = parsed.drivername in POSTGRESQL_SCHEMES and location_valid and bool(parsed.database)
    if settings.app_env == "production":
        ok = ok and not _is_placeholder(password)
    return DeploymentCheck(
        name="database_url",
        ok=ok,
        detail="PostgreSQL-compatible DATABASE_URL configured."
        if ok
        else (
            "Database configuration must be PostgreSQL with a TCP host or complete Cloud SQL "
            "socket settings, a database name, and a non-placeholder production secret."
        ),
    )


def _tls_check(settings: Settings) -> DeploymentCheck:
    if settings.cloud_sql_configuration_complete:
        return DeploymentCheck(
            name="database_tls",
            ok=True,
            detail="Cloud SQL Unix socket security is managed by the Cloud Run integration.",
        )
    try:
        raw_sslmode = settings.resolved_database_url.query.get("sslmode")
    except ArgumentError:
        raw_sslmode = None
    url_sslmode = raw_sslmode[-1] if isinstance(raw_sslmode, tuple) else raw_sslmode
    sslmode = (url_sslmode or settings.database_ssl_mode).lower()
    production_modes = {"require", "verify-ca", "verify-full"}
    ok = (
        sslmode in production_modes
        if settings.app_env == "production"
        else sslmode in production_modes | {"prefer", "disable", "allow"}
    )
    return DeploymentCheck(
        name="database_tls",
        ok=ok,
        detail="PostgreSQL TLS mode is configured without exposing credentials."
        if ok
        else "Production PostgreSQL requires sslmode=require, verify-ca, or verify-full.",
    )


def _pool_check(settings: Settings) -> DeploymentCheck:
    ok = (
        settings.database_pool_size >= 1
        and settings.database_max_overflow >= 0
        and settings.database_connect_timeout_seconds >= 1
        and settings.database_pool_recycle_seconds >= 60
    )
    return DeploymentCheck(
        name="database_pooling",
        ok=ok,
        detail="Connection pool, timeout, and recycle settings are bounded."
        if ok
        else "Database pool and timeout settings must be positive bounded values.",
    )


def _api_token_check(settings: Settings, process: DeploymentProcess) -> DeploymentCheck:
    if settings.app_env != "production" or process is not DeploymentProcess.WEB:
        return DeploymentCheck(
            name="api_token",
            ok=True,
            detail="API token is not required for this process/environment.",
        )
    secret = (
        settings.api_token.get_secret_value() if settings.api_token else None
    )
    ok = not _is_placeholder(secret)
    return DeploymentCheck(
        name="api_token",
        ok=ok,
        detail="AD_ANALYZER_API_TOKEN configured for production web process."
        if ok
        else (
            "Production web process requires a non-placeholder external secret "
            "for AD_ANALYZER_API_TOKEN."
        ),
    )


def _required_secrets_check(settings: Settings) -> DeploymentCheck:
    if settings.app_env != "production":
        return DeploymentCheck(
            name="required_secrets",
            ok=True,
            detail="Production-only secret validation skipped outside production.",
        )
    missing = []
    required_names = tuple(
        "DATABASE_PASSWORD" if name == "DATABASE_URL" and settings.uses_cloud_sql_socket else name
        for name in settings.required_secret_names
    )
    for name in required_names:
        value = settings.secret_reference_for(name)
        if name == "DATABASE_URL":
            try:
                password = settings.resolved_database_url.password
            except (ArgumentError, ValueError):
                password = None
            if not value or _is_placeholder(password):
                missing.append(name)
        elif _is_placeholder(value):
            missing.append(name)
    return DeploymentCheck(
        name="required_secrets",
        ok=not missing,
        detail="Required production secrets are referenced externally."
        if not missing
        else "One or more required production secrets are missing or placeholder values.",
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
        else "Production execution allowlists must remain empty for Phase 12.2.",
    )


def runtime_process_config(process: DeploymentProcess, settings: Settings) -> RuntimeProcessConfig:
    commands = {
        DeploymentProcess.WEB: ("uvicorn", "app.main:app"),
        DeploymentProcess.WORKER: ("python", "-m", "app.jobs.google_ads_sync_once"),
        DeploymentProcess.SCHEDULER: ("python", "-m", "app.jobs.google_ads_scheduler"),
        DeploymentProcess.MIGRATION: ("alembic", "upgrade", "head"),
    }
    concurrency = {
        DeploymentProcess.WEB: settings.web_concurrency,
        DeploymentProcess.WORKER: settings.worker_concurrency,
        DeploymentProcess.SCHEDULER: settings.scheduler_concurrency,
        DeploymentProcess.MIGRATION: 1,
    }[process]
    timeout = {
        DeploymentProcess.WEB: settings.web_timeout_seconds,
        DeploymentProcess.WORKER: settings.worker_timeout_seconds,
        DeploymentProcess.SCHEDULER: settings.scheduler_timeout_seconds,
        DeploymentProcess.MIGRATION: settings.migration_timeout_seconds,
    }[process]
    restart = (
        "on-failure" if process in {DeploymentProcess.WEB, DeploymentProcess.SCHEDULER} else "no"
    )
    return RuntimeProcessConfig(
        process=process,
        command=commands[process],
        concurrency=concurrency,
        timeout_seconds=timeout,
        graceful_shutdown_seconds=settings.graceful_shutdown_seconds,
        restart_policy=restart,
        run_migrations_before_start=process is not DeploymentProcess.MIGRATION,
    )


def validate_deployment_startup(
    process: DeploymentProcess, settings: Settings | None = None
) -> DeploymentValidationResult:
    resolved_settings = settings or Settings()
    checks = (
        _database_url_check(resolved_settings),
        _tls_check(resolved_settings),
        _pool_check(resolved_settings),
        _api_token_check(resolved_settings, process),
        _required_secrets_check(resolved_settings),
        _write_guard_check(resolved_settings),
        _allowlist_check(resolved_settings),
    )
    return DeploymentValidationResult(
        process=process, ok=all(check.ok for check in checks), checks=checks
    )
