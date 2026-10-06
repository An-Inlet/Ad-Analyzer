"""Read-only provider boundary. Fixture implementations cannot be enabled as live providers."""

from datetime import date
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator

from app.goals.schemas import StrictModel


class Account(StrictModel):
    external_id: str = Field(pattern=r"^[0-9]{10}$")
    name: str = Field(min_length=1, max_length=255)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str
    manager: bool = False
    login_customer_id: str | None = Field(default=None, pattern=r"^[0-9]{10}$")

    @field_validator("time_zone")
    @classmethod
    def zone(cls, value: str) -> str:
        ZoneInfo(value)
        return value


class Grant(StrictModel):
    refresh_token: SecretStr
    accounts: list[Account] = Field(max_length=100)


class CampaignRow(StrictModel):
    external_id: str = Field(pattern=r"^[0-9]{1,32}$")
    name: str = Field(min_length=1, max_length=255)
    status: Literal["ENABLED", "PAUSED", "REMOVED"]
    channel: str = Field(max_length=64)


class MetricRow(StrictModel):
    campaign_external_id: str = Field(pattern=r"^[0-9]{1,32}$")
    day: date
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    cost_micros: int = Field(ge=0)
    conversions: str = Field(pattern=r"^[0-9]+(?:\.[0-9]{1,6})?$")
    conversion_value_micros: int = Field(ge=0)


class Page(StrictModel):
    external_account_id: str = Field(pattern=r"^[0-9]{10}$")
    campaigns: list[CampaignRow] = Field(max_length=10000)
    metrics: list[MetricRow] = Field(max_length=10000)
    next_cursor: str | None = Field(default=None, max_length=4096)


class GoogleReadTransport(Protocol):
    mode: Literal["fixture"]

    def exchange(self, code: str, redirect_uri: str) -> Grant: ...
    def page(
        self,
        refresh_token: str,
        account_id: str,
        start: date,
        end: date,
        cursor: str | None,
        login_customer_id: str | None = None,
    ) -> Page: ...


class UnavailableTransport:
    mode: Literal["fixture"] = "fixture"

    def exchange(self, code: str, redirect_uri: str) -> Grant:
        raise RuntimeError("google_customer_transport_unavailable")

    def page(
        self,
        refresh_token: str,
        account_id: str,
        start: date,
        end: date,
        cursor: str | None,
        login_customer_id: str | None = None,
    ) -> Page:
        raise RuntimeError("google_customer_transport_unavailable")


def get_transport() -> GoogleReadTransport:
    return UnavailableTransport()
