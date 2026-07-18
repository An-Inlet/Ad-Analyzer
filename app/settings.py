import os
from typing import Any

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

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

    @model_validator(mode="before")
    @classmethod
    def sync_lock_aliases_do_not_conflict(cls, data: Any) -> Any:
        env_canonical = os.environ.get("DENTICODE_SYNC_ADVISORY_LOCK_KEY")
        env_legacy = os.environ.get("DENTICODE_SYNC_LOCK_KEY")
        data_canonical = (
            data.get("DENTICODE_SYNC_ADVISORY_LOCK_KEY")
            if isinstance(data, dict)
            else None
        )
        data_legacy = (
            data.get("DENTICODE_SYNC_LOCK_KEY") if isinstance(data, dict) else None
        )
        canonical = data_canonical if data_canonical is not None else env_canonical
        legacy = data_legacy if data_legacy is not None else env_legacy
        if canonical is not None and legacy is not None and str(canonical) != str(legacy):
            raise ValueError("conflicting sync advisory lock key settings")
        return data

    @model_validator(mode="after")
    def retry_bounds_are_valid(self) -> "Settings":
        if self.sync_retry_max_seconds < self.sync_retry_base_seconds:
            raise ValueError("sync retry maximum must not be lower than retry base")
        return self


settings = Settings()
