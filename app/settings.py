import os
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_dotenv_lock_values() -> tuple[str | None, str | None]:
    dotenv_path = Path(".env")
    if not dotenv_path.exists():
        return None, None
    canonical: str | None = None
    legacy: str | None = None
    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key == "DENTICODE_SYNC_ADVISORY_LOCK_KEY":
            canonical = value
        elif key == "DENTICODE_SYNC_LOCK_KEY":
            legacy = value
    return canonical, legacy


class SyncAdvisoryLockConfigError(RuntimeError):
    """Fixed sanitized sync advisory-lock configuration error."""

    def __init__(self) -> None:
        super().__init__("Conflicting sync advisory lock key settings.")


class InvalidSyncAdvisoryLockConfigError(RuntimeError):
    """Fixed sanitized invalid advisory-lock key configuration error."""

    def __init__(self) -> None:
        super().__init__("Invalid sync advisory lock key setting.")


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
    if not (-(2**63) <= parsed <= 2**63 - 1):
        raise InvalidSyncAdvisoryLockConfigError()
    return parsed


def _resolve_lock_key_override(
    data: dict[str, Any], dotenv_canonical: str | None, dotenv_legacy: str | None
) -> int | None:
    canonical_values = [
        value
        for value in (
            os.environ.get("DENTICODE_SYNC_ADVISORY_LOCK_KEY"),
            dotenv_canonical,
            data.get("DENTICODE_SYNC_ADVISORY_LOCK_KEY"),
        )
        if value is not None
    ]
    legacy_values = [
        value
        for value in (
            os.environ.get("DENTICODE_SYNC_LOCK_KEY"),
            dotenv_legacy,
            data.get("DENTICODE_SYNC_LOCK_KEY"),
        )
        if value is not None
    ]
    canonical_keys = [_parse_lock_key(value) for value in canonical_values]
    legacy_keys = [_parse_lock_key(value) for value in legacy_values]
    if canonical_keys and legacy_keys and set(canonical_keys) != set(legacy_keys):
        raise SyncAdvisoryLockConfigError()
    resolved_values = canonical_keys or legacy_keys
    if not resolved_values:
        return None
    if len(set(resolved_values)) != 1:
        raise SyncAdvisoryLockConfigError()
    return resolved_values[0]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    def __init__(self, **data: Any) -> None:
        lock_key = _resolve_lock_key_override(data, *_read_dotenv_lock_values())
        if lock_key is not None:
            data = {**data, "DENTICODE_SYNC_ADVISORY_LOCK_KEY": lock_key}
            data.pop("DENTICODE_SYNC_LOCK_KEY", None)
        super().__init__(**data)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/denticode_ads_optimizer",
        validation_alias="DATABASE_URL",
    )
    denticode_api_token: SecretStr | None = Field(
        default=None, validation_alias="DENTICODE_API_TOKEN"
    )
    denticode_dashboard_allow_insecure_local_http: bool = Field(
        default=False, validation_alias="DENTICODE_DASHBOARD_ALLOW_INSECURE_LOCAL_HTTP"
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
        default=60, ge=5, le=1440, validation_alias="DENTICODE_SYNC_INTERVAL_MINUTES"
    )
    sync_run_immediately: bool = Field(
        default=True, validation_alias="DENTICODE_SYNC_RUN_IMMEDIATELY"
    )
    sync_max_attempts: int = Field(
        default=3, ge=1, le=5, validation_alias="DENTICODE_SYNC_MAX_ATTEMPTS"
    )
    sync_retry_base_seconds: float = Field(
        default=5, ge=1, le=300, validation_alias="DENTICODE_SYNC_RETRY_BASE_SECONDS"
    )
    sync_retry_max_seconds: float = Field(
        default=60, ge=1, le=900, validation_alias="DENTICODE_SYNC_RETRY_MAX_SECONDS"
    )
    sync_stale_after_minutes: int = Field(
        default=180, ge=1, le=10080, validation_alias="DENTICODE_SYNC_STALE_AFTER_MINUTES"
    )
    sync_lock_key: int = Field(
        default=719_042_711,
        ge=-(2**63),
        le=2**63 - 1,
        validation_alias=AliasChoices(
            "DENTICODE_SYNC_ADVISORY_LOCK_KEY", "DENTICODE_SYNC_LOCK_KEY"
        ),
    )


    @model_validator(mode="after")
    def retry_bounds_are_valid(self) -> "Settings":
        if self.sync_retry_max_seconds < self.sync_retry_base_seconds:
            raise ValueError("sync retry maximum must not be lower than retry base")
        return self


settings = Settings()
