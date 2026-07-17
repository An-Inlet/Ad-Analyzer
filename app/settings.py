from pydantic import Field, SecretStr
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


settings = Settings()
