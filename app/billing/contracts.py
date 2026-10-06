from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

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
    url: str | None = Field(default=None, max_length=2048)
    expires_at: AwareDatetime


class CheckoutState(StrictModel):
    id: str = Field(pattern=r"^cs_[A-Za-z0-9_]{1,128}$")
    customer_id: str = Field(pattern=r"^cus_[A-Za-z0-9_]{1,128}$")
    status: Literal["open", "complete", "expired"]
    subscription_id: str | None = Field(default=None, pattern=r"^sub_[A-Za-z0-9_]{1,128}$")
    observed_at: AwareDatetime
    livemode: Literal[False] = False


class BillingTransport(Protocol):
    @property
    def mode(self) -> Literal["fixture", "stripe_test"]: ...

    def customer(self, workspace_id: int, idempotency_key: str) -> str: ...
    def checkout(
        self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
    ) -> CheckoutResult: ...
    def current(
        self, customer_id: str, subscription_id: str, now: datetime
    ) -> SubscriptionState: ...
    def checkout_state(
        self, customer_id: str, checkout_id: str, now: datetime
    ) -> CheckoutState: ...


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

    def checkout_state(self, customer_id: str, checkout_id: str, now: datetime) -> CheckoutState:
        raise RuntimeError("billing unavailable")


def get_billing_transport() -> BillingTransport:
    from app.billing.stripe import StripeBilling
    from app.settings import settings

    if settings.billing_provider_mode != "stripe_test" or settings.billing_api_key is None:
        return UnavailableBilling()
    try:
        return StripeBilling(settings.billing_api_key, settings.billing_api_version)
    except ValueError:
        return UnavailableBilling()


@runtime_checkable
class BillingManagementTransport(Protocol):
    def portal(
        self, customer_id: str, configuration_id: str, return_url: str, request_key: str
    ) -> str: ...
