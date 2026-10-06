from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, SecretStr, field_validator

from app.goals.schemas import StrictModel

ProviderName = Literal["tiktok_ads", "klaviyo", "hubspot", "omnisend"]


class SourceAccount(StrictModel):
    external_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    name: str = Field(min_length=1, max_length=255)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    time_zone: str | None = None

    @field_validator("time_zone")
    @classmethod
    def zone(cls, value: str | None) -> str | None:
        if value is not None:
            ZoneInfo(value)
        return value


class SourceGrant(StrictModel):
    access_token: SecretStr
    refresh_token: SecretStr | None = None
    expires_at: AwareDatetime | None = None
    accounts: list[SourceAccount] = Field(min_length=1, max_length=100)


class SourceTransport(Protocol):
    @property
    def mode(self) -> Literal["fixture", "provider_read"]: ...

    def authorize_url(self, state: str, redirect_uri: str) -> str: ...
    def exchange(self, code: str, redirect_uri: str) -> SourceGrant: ...
    def read(
        self, account: str, token: str, start: date, end: date, cursor: str | None
    ) -> dict[str, Any]: ...


@runtime_checkable
class GuardedSourceExchange(Protocol):
    """Per-call actor checkpoint between exchange requests; no shared mutable guard."""

    def exchange_guarded(
        self, code: str, redirect_uri: str, checkpoint: Callable[[], None]
    ) -> SourceGrant: ...


@runtime_checkable
class PKCESourceTransport(Protocol):
    """Optional explicit per-attempt capability; adapters hold no verifier state."""

    def authorize_url_pkce(self, state: str, redirect_uri: str, code_challenge: str) -> str: ...
    def exchange_pkce(self, code: str, redirect_uri: str, code_verifier: str) -> SourceGrant: ...


class UnavailableSource:
    mode: Literal["fixture"] = "fixture"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        raise RuntimeError("source transport unavailable")

    def exchange(self, code: str, redirect_uri: str) -> SourceGrant:
        raise RuntimeError("source transport unavailable")

    def read(
        self, account: str, token: str, start: date, end: date, cursor: str | None
    ) -> dict[str, Any]:
        raise RuntimeError("source transport unavailable")


def get_source_transport(provider: ProviderName) -> SourceTransport:
    from app.settings import settings
    from app.tiktok.http import TikTokHTTPRead

    if (
        provider == "tiktok_ads"
        and settings.tiktok_runtime_mode == "provider_read"
        and settings.tiktok_app_secret
    ):
        try:
            return TikTokHTTPRead(settings.tiktok_app_id, settings.tiktok_app_secret)
        except ValueError:
            pass
    if provider in {"klaviyo", "hubspot", "omnisend"}:
        from app.customer_context.factory import crm_transport

        return crm_transport(provider)
    return UnavailableSource()


class SourceCampaign(StrictModel):
    id: str = Field(pattern=r"^[0-9]{1,32}$")
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(max_length=64)
    objective: str = Field(max_length=64)


class SourceGroup(StrictModel):
    id: str = Field(pattern=r"^[0-9]{1,32}$")
    campaign_id: str = Field(pattern=r"^[0-9]{1,32}$")
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(max_length=64)


class SourceAd(StrictModel):
    id: str = Field(pattern=r"^[0-9]{1,32}$")
    group_id: str = Field(pattern=r"^[0-9]{1,32}$")
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(max_length=64)


class SourceMetric(StrictModel):
    level: Literal["campaign", "ad_group", "ad"]
    id: str = Field(pattern=r"^[0-9]{1,32}$")
    day: date
    impressions: int = Field(strict=True, ge=0)
    clicks: int = Field(strict=True, ge=0)
    cost_micros: int = Field(strict=True, ge=0)
    conversions: Decimal = Field(ge=0, allow_inf_nan=False)
    conversion_value_micros: int = Field(strict=True, ge=0)


class AdvertisingPage(StrictModel):
    account_id: str = Field(pattern=r"^[0-9]{1,32}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    campaigns: list[SourceCampaign] = Field(default_factory=list, max_length=1000)
    groups: list[SourceGroup] = Field(default_factory=list, max_length=1000)
    ads: list[SourceAd] = Field(default_factory=list, max_length=1000)
    metrics: list[SourceMetric] = Field(default_factory=list, max_length=1000)
    next_cursor: str | None = Field(default=None, max_length=4096)
