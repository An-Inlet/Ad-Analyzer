import os
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from sqlalchemy import URL, make_url

_SYNC_LOCK_FIELD = "sync_lock_key"
_SYNC_LOCK_CANONICAL = "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY"
_SYNC_LOCK_LEGACY = "AD_ANALYZER_SYNC_LOCK_KEY"
_SYNC_LOCK_KEY_NAMES = {
    _SYNC_LOCK_FIELD.lower(),
    _SYNC_LOCK_CANONICAL.lower(),
    _SYNC_LOCK_LEGACY.lower(),
}
_SYNC_LOCK_MIN = -(2**63)
_SYNC_LOCK_MAX = 2**63 - 1


class SyncAdvisoryLockConfigError(RuntimeError):
    """Fixed sanitized sync advisory-lock configuration error."""

    def __init__(self) -> None:
        super().__init__("Conflicting sync advisory lock key settings.")


class InvalidSyncAdvisoryLockConfigError(RuntimeError):
    """Fixed sanitized invalid advisory-lock key configuration error."""

    def __init__(self) -> None:
        super().__init__("Invalid sync advisory lock key setting.")


def _is_sync_lock_key_name(key: object) -> bool:
    return isinstance(key, str) and key.lower() in _SYNC_LOCK_KEY_NAMES


def _parse_lock_key(value: object) -> int:
    if isinstance(value, bool):
        raise InvalidSyncAdvisoryLockConfigError()
    text = str(value).strip()
    if text == "":
        raise InvalidSyncAdvisoryLockConfigError()
    try:
        parsed = int(text, 10)
    except ValueError:
        raise InvalidSyncAdvisoryLockConfigError() from None
    if not (_SYNC_LOCK_MIN <= parsed <= _SYNC_LOCK_MAX):
        raise InvalidSyncAdvisoryLockConfigError()
    return parsed


def _raw_environment_lock_values() -> list[object]:
    return [value for key, value in os.environ.items() if _is_sync_lock_key_name(key)]


def _dotenv_paths(env_file: object) -> list[Path]:
    if env_file is None:
        return []
    if isinstance(env_file, (str, os.PathLike)):
        return [Path(env_file)]
    if isinstance(env_file, list | tuple):
        return [Path(path) for path in env_file if path is not None]
    return []


def _raw_dotenv_lock_values(source: PydanticBaseSettingsSource) -> list[object]:
    raw_values: list[object] = []
    encoding = getattr(source, "env_file_encoding", None)
    for dotenv_path in _dotenv_paths(getattr(source, "env_file", None)):
        if not dotenv_path.exists() or not dotenv_path.is_file():
            continue
        for raw_line in dotenv_path.read_text(encoding=encoding).splitlines():
            line = raw_line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if _is_sync_lock_key_name(key.strip()):
                raw_values.append(value.strip().strip("'\""))
    return raw_values


def _resolve_lock_key_values(source_values: list[object]) -> int | None:
    if not source_values:
        return None
    parsed_values = [_parse_lock_key(value) for value in source_values]
    if len(set(parsed_values)) != 1:
        raise SyncAdvisoryLockConfigError()
    return parsed_values[0]


class _CachedSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        source: PydanticBaseSettingsSource,
        cache: dict[int, dict[str, Any]],
    ) -> None:
        super().__init__(settings_cls)
        self._source = source
        self._cache = cache

    def _source_data(self) -> dict[str, Any]:
        source_id = id(self._source)
        if source_id not in self._cache:
            self._cache[source_id] = dict(self._source())
        return self._cache[source_id]

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False


class _SanitizedSettingsSource(_CachedSettingsSource):
    def __call__(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self._source_data().items()
            if not _is_sync_lock_key_name(key)
        }


class _SyncLockKeySettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        sources: tuple[PydanticBaseSettingsSource, ...],
        cache: dict[int, dict[str, Any]],
    ) -> None:
        super().__init__(settings_cls)
        self._sources = sources
        self._cache = cache

    def _source_data(self, source: PydanticBaseSettingsSource) -> dict[str, Any]:
        source_id = id(source)
        if source_id not in self._cache:
            self._cache[source_id] = dict(source())
        return self._cache[source_id]

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def _lock_values_from_source(self, source: PydanticBaseSettingsSource) -> list[object]:
        raw_values: list[object] = []
        if hasattr(source, "env_file"):
            raw_values.extend(_raw_dotenv_lock_values(source))
        elif hasattr(source, "env_vars"):
            raw_values.extend(_raw_environment_lock_values())
        env_vars = getattr(source, "env_vars", None)
        if isinstance(env_vars, dict):
            raw_values.extend(
                value for key, value in env_vars.items() if _is_sync_lock_key_name(key)
            )
        raw_values.extend(
            value for key, value in self._source_data(source).items() if _is_sync_lock_key_name(key)
        )
        return raw_values

    def __call__(self) -> dict[str, Any]:
        raw_values: list[object] = []
        for source in self._sources:
            raw_values.extend(self._lock_values_from_source(source))
        resolved = _resolve_lock_key_values(raw_values)
        if resolved is None:
            return {}
        return {_SYNC_LOCK_FIELD: resolved}


class Settings(BaseSettings):
    candidate_assembly_manifest_path: str | None = None
    candidate_assembly_manifest_digest: str | None = None
    candidate_policy_bundle_path: str | None = None
    customer_candidate_reads_enabled: bool = False
    customer_independent_acquisition_enabled: bool = False
    independent_acquisition_profile_path: str | None = None
    independent_acquisition_environment: Literal["live", "contract_test"] = "live"
    optimization_execution_manifest_path: str | None = None
    optimization_execution_manifest_digest: str | None = None
    optimization_operating_policy_path: str | None = None
    tiktok_execution_manifest_path: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_TIKTOK_EXECUTION_MANIFEST_PATH"
    )
    tiktok_execution_manifest_digest: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_TIKTOK_EXECUTION_MANIFEST_DIGEST"
    )
    tiktok_execution_bundle_path: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_TIKTOK_EXECUTION_BUNDLE_PATH"
    )
    meta_execution_manifest_path: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_META_EXECUTION_MANIFEST_PATH"
    )
    meta_execution_manifest_digest: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_META_EXECUTION_MANIFEST_DIGEST"
    )
    meta_execution_bundle_path: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_META_EXECUTION_BUNDLE_PATH"
    )
    google_execution_manifest_path: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_GOOGLE_EXECUTION_MANIFEST_PATH"
    )
    google_execution_manifest_digest: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_GOOGLE_EXECUTION_MANIFEST_DIGEST"
    )
    budget_mandate_policy_path: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_BUDGET_MANDATE_POLICY_PATH"
    )
    budget_mandate_policy_digest: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_BUDGET_MANDATE_POLICY_DIGEST"
    )
    planning_reporting_profile_path: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_PLANNING_REPORTING_PROFILE_PATH"
    )
    planning_reporting_profile_digest: str | None = Field(
        default=None, validation_alias="AD_ANALYZER_PLANNING_REPORTING_PROFILE_DIGEST"
    )

    media_storage_mode: str = Field(default="disabled", alias="AD_ANALYZER_MEDIA_STORAGE_MODE")
    media_gcs_bucket: str = Field(default="", alias="AD_ANALYZER_MEDIA_GCS_BUCKET")
    media_local_directory: str = Field(default="", alias="AD_ANALYZER_MEDIA_LOCAL_DIRECTORY")
    klaviyo_runtime_mode: str = Field(default="disabled", alias="AD_ANALYZER_KLAVIYO_RUNTIME_MODE")
    klaviyo_client_id: str = Field(default="", alias="AD_ANALYZER_KLAVIYO_CLIENT_ID")
    klaviyo_client_secret: SecretStr | None = Field(
        default=None, alias="AD_ANALYZER_KLAVIYO_CLIENT_SECRET"
    )
    klaviyo_api_revision: str = Field(default="", alias="AD_ANALYZER_KLAVIYO_API_REVISION")
    hubspot_runtime_mode: str = Field(default="disabled", alias="AD_ANALYZER_HUBSPOT_RUNTIME_MODE")
    hubspot_client_id: str = Field(default="", alias="AD_ANALYZER_HUBSPOT_CLIENT_ID")
    hubspot_client_secret: SecretStr | None = Field(
        default=None, alias="AD_ANALYZER_HUBSPOT_CLIENT_SECRET"
    )

    omnisend_runtime_mode: str = Field(
        default="disabled", alias="AD_ANALYZER_OMNISEND_RUNTIME_MODE"
    )
    omnisend_client_id: str = Field(default="", alias="AD_ANALYZER_OMNISEND_CLIENT_ID")
    omnisend_client_secret: SecretStr | None = Field(
        default=None, alias="AD_ANALYZER_OMNISEND_CLIENT_SECRET"
    )
    omnisend_api_revision: str = Field(default="", alias="AD_ANALYZER_OMNISEND_API_REVISION")

    tiktok_runtime_mode: str = Field(default="disabled", alias="AD_ANALYZER_TIKTOK_RUNTIME_MODE")
    tiktok_app_id: str = Field(default="", alias="AD_ANALYZER_TIKTOK_APP_ID")
    tiktok_app_secret: SecretStr | None = Field(default=None, alias="AD_ANALYZER_TIKTOK_APP_SECRET")
    customer_planning_policy: Literal["v3", "v4", "v5", "v6", "v7"] = Field(
        default="v3", validation_alias="INLET_CUSTOMER_PLANNING_POLICY"
    )
    customer_google_reporting_enabled: bool = Field(
        default=False, validation_alias="INLET_CUSTOMER_GOOGLE_REPORTING_ENABLED"
    )
    customer_google_budget_observation_mode: Literal["disabled", "injected_fixture"] = Field(
        default="disabled", validation_alias="INLET_CUSTOMER_GOOGLE_BUDGET_OBSERVATION_MODE"
    )
    customer_meta_reporting_enabled: bool = Field(
        default=False, validation_alias="INLET_CUSTOMER_META_REPORTING_ENABLED"
    )
    customer_native_diagnostics_enabled: bool = Field(
        default=False, validation_alias="INLET_CUSTOMER_NATIVE_DIAGNOSTICS_ENABLED"
    )
    google_customer_runtime_mode: str = Field(
        default="disabled", alias="AD_ANALYZER_GOOGLE_CUSTOMER_RUNTIME_MODE"
    )
    google_customer_api_version: str = Field(
        default="", alias="AD_ANALYZER_GOOGLE_CUSTOMER_API_VERSION"
    )
    google_customer_client_secret: SecretStr | None = Field(
        default=None, alias="AD_ANALYZER_GOOGLE_CUSTOMER_CLIENT_SECRET"
    )
    google_customer_developer_token: SecretStr | None = Field(
        default=None, alias="AD_ANALYZER_GOOGLE_CUSTOMER_DEVELOPER_TOKEN"
    )
    billing_provider_mode: str = Field(
        default="disabled", alias="AD_ANALYZER_BILLING_PROVIDER_MODE"
    )
    billing_offer_profile: str | None = Field(
        default=None, alias="AD_ANALYZER_BILLING_OFFER_PROFILE"
    )
    billing_live_max_accounts: int | None = Field(
        default=None, ge=1, le=100, alias="AD_ANALYZER_BILLING_LIVE_MAX_ACCOUNTS"
    )
    billing_live_enabled: bool = Field(default=False, alias="AD_ANALYZER_BILLING_LIVE_ENABLED")
    billing_receipt_read_enabled: bool = Field(
        default=False, alias="AD_ANALYZER_BILLING_RECEIPT_READ_ENABLED"
    )
    billing_receipt_environment: str = Field(
        default="", alias="AD_ANALYZER_BILLING_RECEIPT_ENVIRONMENT"
    )
    billing_merchant_account_id: str = Field(
        default="", alias="AD_ANALYZER_BILLING_MERCHANT_ACCOUNT_ID"
    )
    billing_live_webhook_secret: SecretStr | None = Field(
        default=None, alias="AD_ANALYZER_BILLING_LIVE_WEBHOOK_SECRET"
    )
    billing_api_key: SecretStr | None = Field(default=None, alias="AD_ANALYZER_BILLING_API_KEY")
    billing_api_version: str = Field(default="", alias="AD_ANALYZER_BILLING_API_VERSION")
    billing_portal_configuration: str = Field(
        default="", alias="AD_ANALYZER_BILLING_PORTAL_CONFIGURATION"
    )
    customer_session_automation_enabled: bool = Field(
        default=False, alias="INLET_CUSTOMER_SESSION_AUTOMATION_ENABLED"
    )
    customer_google_scheduler_enabled: bool = Field(
        default=False, alias="AD_ANALYZER_CUSTOMER_GOOGLE_SCHEDULER_ENABLED"
    )
    customer_tiktok_scheduler_enabled: bool = Field(
        default=False, alias="AD_ANALYZER_CUSTOMER_TIKTOK_SCHEDULER_ENABLED"
    )
    customer_billing_scheduler_enabled: bool = Field(
        default=False, alias="AD_ANALYZER_CUSTOMER_BILLING_SCHEDULER_ENABLED"
    )
    customer_analysis_outbox_enabled: bool = Field(
        default=False, alias="AD_ANALYZER_CUSTOMER_ANALYSIS_OUTBOX_ENABLED"
    )
    billing_required: bool = Field(default=False, alias="AD_ANALYZER_BILLING_REQUIRED")
    billing_price_id: str = Field(default="", alias="AD_ANALYZER_BILLING_PRICE_ID")
    billing_max_accounts: int = Field(
        default=1, ge=1, le=100, alias="AD_ANALYZER_BILLING_MAX_ACCOUNTS"
    )
    billing_webhook_secret: SecretStr | None = Field(
        default=None, alias="AD_ANALYZER_BILLING_WEBHOOK_SECRET"
    )

    source_token_encryption_key: SecretStr | None = Field(
        default=None, validation_alias="AD_ANALYZER_SOURCE_TOKEN_ENCRYPTION_KEY"
    )

    google_customer_encryption_key: SecretStr | None = Field(
        default=None, validation_alias="AD_ANALYZER_GOOGLE_CUSTOMER_ENCRYPTION_KEY"
    )
    google_customer_client_id: str = Field(
        default="", validation_alias="AD_ANALYZER_GOOGLE_CUSTOMER_CLIENT_ID"
    )

    mandate_simulation_enabled: bool = Field(
        default=True, validation_alias="AD_ANALYZER_MANDATE_SIMULATION_ENABLED"
    )
    """Application settings loaded from environment variables."""

    def __init__(self, **data: Any) -> None:
        lock_values = [value for key, value in data.items() if _is_sync_lock_key_name(key)]
        resolved = _resolve_lock_key_values(lock_values)
        if resolved is not None:
            data = {key: value for key, value in data.items() if not _is_sync_lock_key_name(key)}
            data[_SYNC_LOCK_FIELD] = resolved
        super().__init__(**data)

    operational_observations_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources = (init_settings, env_settings, dotenv_settings, file_secret_settings)
        cache: dict[int, dict[str, Any]] = {}
        return (
            _SyncLockKeySettingsSource(settings_cls, sources, cache),
            *(_SanitizedSettingsSource(settings_cls, source, cache) for source in sources),
        )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    workspace_id: int = Field(
        default=1,
        ge=1,
        validation_alias="AD_ANALYZER_WORKSPACE_ID",
    )
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/ad_analyzer",
        validation_alias="DATABASE_URL",
    )
    cloud_sql_connection_name: str | None = Field(
        default=None, validation_alias="CLOUD_SQL_CONNECTION_NAME"
    )
    database_user: str | None = Field(default=None, validation_alias="DATABASE_USER")
    database_password: SecretStr | None = Field(default=None, validation_alias="DATABASE_PASSWORD")
    database_name: str | None = Field(default=None, validation_alias="DATABASE_NAME")
    database_ssl_mode: str = Field(default="prefer", validation_alias="DATABASE_SSL_MODE")
    database_pool_size: int = Field(default=5, ge=1, le=50, validation_alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(
        default=5, ge=0, le=100, validation_alias="DATABASE_MAX_OVERFLOW"
    )
    database_connect_timeout_seconds: int = Field(
        default=10, ge=1, le=120, validation_alias="DATABASE_CONNECT_TIMEOUT_SECONDS"
    )
    database_pool_recycle_seconds: int = Field(
        default=1800, ge=60, le=86400, validation_alias="DATABASE_POOL_RECYCLE_SECONDS"
    )
    api_token: SecretStr | None = Field(default=None, validation_alias="AD_ANALYZER_API_TOKEN")
    crm_webhook_secret: SecretStr | None = Field(
        default=None, validation_alias="AD_ANALYZER_CRM_WEBHOOK_SECRET"
    )
    crm_push_oidc_audience: str = Field(
        default="", validation_alias="AD_ANALYZER_CRM_PUSH_OIDC_AUDIENCE"
    )
    crm_push_service_account_email: str = Field(
        default="", validation_alias="AD_ANALYZER_CRM_PUSH_SERVICE_ACCOUNT_EMAIL"
    )
    crm_pubsub_project_id: str = Field(
        default="", validation_alias="AD_ANALYZER_CRM_PUBSUB_PROJECT_ID"
    )
    crm_pubsub_topic_id: str = Field(
        default="crm-events", validation_alias="AD_ANALYZER_CRM_PUBSUB_TOPIC_ID"
    )
    crm_pubsub_subscription_id: str = Field(
        default="", validation_alias="AD_ANALYZER_CRM_PUBSUB_SUBSCRIPTION_ID"
    )
    dashboard_allow_insecure_local_http: bool = Field(
        default=False,
        validation_alias="AD_ANALYZER_DASHBOARD_ALLOW_INSECURE_LOCAL_HTTP",
    )
    google_ads_workspace_id: int | None = Field(
        default=None, ge=1, alias="INLET_GOOGLE_ADS_WORKSPACE_ID"
    )
    google_ads_connection_id: int | None = Field(
        default=None, ge=1, alias="INLET_GOOGLE_ADS_CONNECTION_ID"
    )
    google_ads_account_id: int | None = Field(
        default=None, ge=1, alias="INLET_GOOGLE_ADS_ACCOUNT_ID"
    )
    google_ads_credentials_reference: str = Field(
        default="", alias="INLET_GOOGLE_ADS_CREDENTIALS_REFERENCE"
    )

    customer_export_enabled: bool = Field(default=False, alias="INLET_CUSTOMER_EXPORT_ENABLED")
    customer_auth_enabled: bool = Field(default=False, alias="INLET_CUSTOMER_AUTH_ENABLED")
    customer_identity_project_id: str = Field(default="", alias="INLET_IDENTITY_PROJECT_ID")
    customer_app_origin: str = Field(default="", alias="INLET_CUSTOMER_APP_ORIGIN")
    customer_browser_auth_enabled: bool = Field(
        default=False, alias="INLET_CUSTOMER_BROWSER_AUTH_ENABLED"
    )
    # Firebase web configuration is public; never put an admin/service-account key here.
    customer_identity_web_api_key: str = Field(default="", alias="INLET_IDENTITY_WEB_API_KEY")
    customer_identity_web_app_id: str = Field(default="", alias="INLET_IDENTITY_WEB_APP_ID")

    iap_audience: str = Field(
        default="",
        validation_alias="AD_ANALYZER_IAP_AUDIENCE",
    )
    platform_admin_emails_csv: str = Field(
        default="",
        validation_alias="AD_ANALYZER_PLATFORM_ADMIN_EMAILS",
    )
    github_control_token: SecretStr | None = Field(
        default=None,
        validation_alias="AD_ANALYZER_GITHUB_CONTROL_TOKEN",
    )
    meta_detail_enabled: bool = Field(
        default=False, validation_alias="AD_ANALYZER_META_DETAIL_ENABLED"
    )

    meta_customer_enabled: bool = Field(
        default=False, validation_alias="AD_ANALYZER_META_CUSTOMER_ENABLED"
    )
    meta_enabled: bool = Field(default=False, validation_alias="AD_ANALYZER_META_ENABLED")
    meta_client_id: str = Field(default="", validation_alias="META_CLIENT_ID")
    meta_client_secret: SecretStr | None = Field(
        default=None, validation_alias="META_CLIENT_SECRET"
    )
    meta_token_encryption_key: SecretStr | None = Field(
        default=None, validation_alias="META_TOKEN_ENCRYPTION_KEY"
    )
    meta_redirect_uri: str = Field(default="", validation_alias="META_REDIRECT_URI")
    meta_sync_pages: int = Field(default=3, ge=1, le=10, validation_alias="META_SYNC_PAGES")
    meta_sync_interval_minutes: int = Field(
        default=60, ge=15, le=1440, validation_alias="META_SYNC_INTERVAL_MINUTES"
    )
    shopify_measurement_enabled: bool = Field(
        default=False, validation_alias="AD_ANALYZER_SHOPIFY_MEASUREMENT_ENABLED"
    )
    shopify_customer_enabled: bool = Field(
        default=False, validation_alias="AD_ANALYZER_SHOPIFY_CUSTOMER_ENABLED"
    )
    shopify_enabled: bool = Field(default=False, validation_alias="AD_ANALYZER_SHOPIFY_ENABLED")
    shopify_client_id: str = Field(default="", validation_alias="SHOPIFY_CLIENT_ID")
    shopify_client_secret: SecretStr | None = Field(
        default=None, validation_alias="SHOPIFY_CLIENT_SECRET"
    )
    shopify_token_encryption_key: SecretStr | None = Field(
        default=None, validation_alias="SHOPIFY_TOKEN_ENCRYPTION_KEY"
    )
    shopify_identifier_hash_key: SecretStr | None = Field(
        default=None, validation_alias="SHOPIFY_IDENTIFIER_HASH_KEY"
    )
    shopify_redirect_uri: str = Field(default="", validation_alias="SHOPIFY_REDIRECT_URI")
    shopify_webhook_subscription: str = Field(
        default="", validation_alias="SHOPIFY_WEBHOOK_SUBSCRIPTION"
    )
    shopify_sync_pages: int = Field(default=10, ge=1, le=10, validation_alias="SHOPIFY_SYNC_PAGES")
    shopify_sync_interval_minutes: int = Field(
        default=60, ge=15, le=1440, validation_alias="SHOPIFY_SYNC_INTERVAL_MINUTES"
    )
    github_control_repository: str = Field(
        default="Konner-An-Inlet/Ad-Analyzer",
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        validation_alias="AD_ANALYZER_GITHUB_CONTROL_REPOSITORY",
    )
    google_ads_developer_token: str | None = Field(
        default=None, validation_alias="GOOGLE_ADS_DEVELOPER_TOKEN"
    )
    google_ads_login_customer_id: str | None = Field(
        default=None, validation_alias="GOOGLE_ADS_LOGIN_CUSTOMER_ID"
    )
    google_ads_customer_id: str | None = Field(
        default=None, validation_alias="GOOGLE_ADS_CUSTOMER_ID"
    )
    google_ads_client_id: str | None = Field(default=None, validation_alias="GOOGLE_ADS_CLIENT_ID")
    google_ads_client_secret: str | None = Field(
        default=None, validation_alias="GOOGLE_ADS_CLIENT_SECRET"
    )
    google_ads_refresh_token: str | None = Field(
        default=None, validation_alias="GOOGLE_ADS_REFRESH_TOKEN"
    )
    sync_interval_minutes: int = Field(
        default=60, ge=5, le=1440, validation_alias="AD_ANALYZER_SYNC_INTERVAL_MINUTES"
    )
    sync_run_immediately: bool = Field(
        default=True, validation_alias="AD_ANALYZER_SYNC_RUN_IMMEDIATELY"
    )
    sync_max_attempts: int = Field(
        default=3, ge=1, le=5, validation_alias="AD_ANALYZER_SYNC_MAX_ATTEMPTS"
    )
    sync_retry_base_seconds: float = Field(
        default=5, ge=1, le=300, validation_alias="AD_ANALYZER_SYNC_RETRY_BASE_SECONDS"
    )
    sync_retry_max_seconds: float = Field(
        default=60, ge=1, le=900, validation_alias="AD_ANALYZER_SYNC_RETRY_MAX_SECONDS"
    )
    sync_stale_after_minutes: int = Field(
        default=180, ge=1, le=10080, validation_alias="AD_ANALYZER_SYNC_STALE_AFTER_MINUTES"
    )
    sync_lock_key: int = Field(
        default=719_042_711,
        ge=-(2**63),
        le=2**63 - 1,
        validation_alias=AliasChoices(_SYNC_LOCK_FIELD, _SYNC_LOCK_CANONICAL, _SYNC_LOCK_LEGACY),
    )
    google_ads_write_enabled: bool = Field(
        default=False, validation_alias="AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED"
    )
    google_ads_execution_kill_switch: bool = Field(
        default=True, validation_alias="AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH"
    )
    allowed_execution_account_ids_csv: str = Field(
        default="", validation_alias="AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS"
    )
    allowed_google_ads_mutations_csv: str = Field(
        default="", validation_alias="AD_ANALYZER_ALLOWED_GOOGLE_ADS_MUTATIONS"
    )
    required_secret_names_csv: str = Field(
        default="AD_ANALYZER_API_TOKEN,DATABASE_URL",
        validation_alias="AD_ANALYZER_REQUIRED_SECRET_NAMES",
    )
    secret_reference_prefix: str = Field(
        default="", validation_alias="AD_ANALYZER_SECRET_REFERENCE_PREFIX"
    )
    web_concurrency: int = Field(
        default=2, ge=1, le=16, validation_alias="AD_ANALYZER_WEB_CONCURRENCY"
    )
    worker_concurrency: int = Field(
        default=1, ge=1, le=8, validation_alias="AD_ANALYZER_WORKER_CONCURRENCY"
    )
    scheduler_concurrency: int = Field(
        default=1, ge=1, le=1, validation_alias="AD_ANALYZER_SCHEDULER_CONCURRENCY"
    )
    web_timeout_seconds: int = Field(
        default=60, ge=5, le=600, validation_alias="AD_ANALYZER_WEB_TIMEOUT_SECONDS"
    )
    worker_timeout_seconds: int = Field(
        default=900, ge=30, le=86400, validation_alias="AD_ANALYZER_WORKER_TIMEOUT_SECONDS"
    )
    scheduler_timeout_seconds: int = Field(
        default=300, ge=30, le=3600, validation_alias="AD_ANALYZER_SCHEDULER_TIMEOUT_SECONDS"
    )
    migration_timeout_seconds: int = Field(
        default=900, ge=30, le=3600, validation_alias="AD_ANALYZER_MIGRATION_TIMEOUT_SECONDS"
    )
    graceful_shutdown_seconds: int = Field(
        default=30, ge=5, le=300, validation_alias="AD_ANALYZER_GRACEFUL_SHUTDOWN_SECONDS"
    )

    @property
    def required_secret_names(self) -> tuple[str, ...]:
        return tuple(
            item.strip() for item in self.required_secret_names_csv.split(",") if item.strip()
        )

    def secret_reference_for(self, name: str) -> str | None:
        if name == "DATABASE_URL":
            return self.database_url if self.database_url.strip() else None
        if name == "AD_ANALYZER_API_TOKEN":
            return self.api_token.get_secret_value() if self.api_token else None
        if name == "DATABASE_PASSWORD":
            return self.database_password.get_secret_value() if self.database_password else None
        return self.secret_reference_prefix or None

    @property
    def uses_cloud_sql_socket(self) -> bool:
        """Return whether Cloud SQL socket configuration has been selected."""
        password = self.database_password.get_secret_value() if self.database_password else ""
        return any(
            value and value.strip()
            for value in (
                self.cloud_sql_connection_name,
                self.database_user,
                password,
                self.database_name,
            )
        )

    @property
    def cloud_sql_configuration_complete(self) -> bool:
        """Return whether every setting needed for a Cloud SQL socket is present."""
        password = self.database_password.get_secret_value() if self.database_password else ""
        return self.uses_cloud_sql_socket and all(
            value and value.strip()
            for value in (
                self.cloud_sql_connection_name,
                self.database_user,
                password,
                self.database_name,
            )
        )

    @property
    def resolved_database_url(self) -> URL:
        """Resolve a direct URL or build a safely escaped Cloud SQL socket URL."""
        if not self.uses_cloud_sql_socket:
            return make_url(self.database_url)
        return URL.create(
            "postgresql+psycopg",
            username=self.database_user,
            password=(
                self.database_password.get_secret_value() if self.database_password else None
            ),
            database=self.database_name,
            query={"host": f"/cloudsql/{self.cloud_sql_connection_name or ''}"},
        )

    @property
    def allowed_execution_account_ids(self) -> set[int]:
        return {
            int(item.strip())
            for item in self.allowed_execution_account_ids_csv.split(",")
            if item.strip().isdigit()
        }

    @property
    def allowed_google_ads_mutations(self) -> set[str]:
        return {
            item.strip()
            for item in self.allowed_google_ads_mutations_csv.split(",")
            if item.strip()
        }

    @property
    def dashboard_allowed_emails(self) -> set[str]:
        """Return platform administrators; workspace members are stored per workspace."""
        return {
            item.strip().casefold()
            for item in self.platform_admin_emails_csv.split(",")
            if item.strip()
        }

    @model_validator(mode="after")
    def retry_bounds_are_valid(self) -> "Settings":
        if self.sync_retry_max_seconds < self.sync_retry_base_seconds:
            raise ValueError("sync retry maximum must not be lower than retry base")
        return self


settings = Settings()
