from datetime import datetime
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field

from app.goals.schemas import StrictModel


class BillingPolicy(StrictModel):
    price_id: str = Field(pattern=r"^price_[A-Za-z0-9_]{1,128}$")
    max_accounts: int = Field(strict=True, ge=1, le=100)
    trial_allowed: bool = False
    max_snapshot_age_seconds: int = Field(strict=True, ge=60, le=3600, default=300)


class SubscriptionState(StrictModel):
    customer_id: str = Field(pattern=r"^cus_[A-Za-z0-9_]{1,128}$")
    subscription_id: str = Field(pattern=r"^sub_[A-Za-z0-9_]{1,128}$")
    price_id: str = Field(pattern=r"^price_[A-Za-z0-9_]{1,128}$")
    status: Literal[
        "active",
        "trialing",
        "past_due",
        "canceled",
        "unpaid",
        "paused",
        "incomplete",
        "incomplete_expired",
    ]
    period_end: AwareDatetime
    cancel_at_period_end: bool
    observed_at: AwareDatetime
    livemode: Literal[False] = False


class CheckoutResult(StrictModel):
    id: str = Field(pattern=r"^cs_[A-Za-z0-9_]{1,128}$")
    url: str = Field(max_length=2048)
    expires_at: AwareDatetime


class BillingTransport(Protocol):
    mode: Literal["fixture"]

    def customer(self, workspace_id: int, idempotency_key: str) -> str: ...
    def checkout(
        self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
    ) -> CheckoutResult: ...
    def current(
        self, customer_id: str, subscription_id: str, now: datetime
    ) -> SubscriptionState: ...


class UnavailableBilling:
    mode: Literal["fixture"] = "fixture"

    def customer(self, workspace_id: int, idempotency_key: str) -> str:
        raise RuntimeError("billing unavailable")

    def checkout(
        self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
    ) -> CheckoutResult:
        raise RuntimeError("billing unavailable")

    def current(self, customer_id: str, subscription_id: str, now: datetime) -> SubscriptionState:
        raise RuntimeError("billing unavailable")


def get_billing_transport() -> BillingTransport:
    return UnavailableBilling()
