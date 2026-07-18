from typing import Any

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_SYNC_LOCK_FIELD = "sync_lock_key"
_SYNC_LOCK_CANONICAL = "DENTICODE_SYNC_ADVISORY_LOCK_KEY"
_SYNC_LOCK_LEGACY = "DENTICODE_SYNC_LOCK_KEY"
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
    """Application settings loaded from environment variables."""

    def __init__(self, **data: Any) -> None:
        lock_values = [value for key, value in data.items() if _is_sync_lock_key_name(key)]
        resolved = _resolve_lock_key_values(lock_values)
        if resolved is not None:
            data = {
                key: value for key, value in data.items() if not _is_sync_lock_key_name(key)
            }
            data[_SYNC_LOCK_FIELD] = resolved
        super().__init__(**data)

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
            _SYNC_LOCK_FIELD, _SYNC_LOCK_CANONICAL, _SYNC_LOCK_LEGACY
        ),
    )


    @model_validator(mode="after")
    def retry_bounds_are_valid(self) -> "Settings":
        if self.sync_retry_max_seconds < self.sync_retry_base_seconds:
            raise ValueError("sync retry maximum must not be lower than retry base")
        return self


settings = Settings()
