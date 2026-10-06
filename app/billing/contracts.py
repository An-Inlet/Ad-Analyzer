from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import AwareDatetime, Field, model_validator

from app.billing.offers import BoundOfferV1, OfferProfileV1, OfferQualificationV1
from app.billing.scope import LEGACY_TEST_SCOPE, BillingScopeV1
from app.goals.schemas import StrictModel


class BillingPolicy(StrictModel):
    price_id: str = Field(pattern=r"^price_[A-Za-z0-9_]{1,128}$")
    max_accounts: int = Field(strict=True, ge=1, le=100)
    trial_allowed: bool = False
    max_snapshot_age_seconds: int = Field(strict=True, ge=60, le=3600, default=300)


class ScopedBillingResult(StrictModel):
    binding_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    scope: BillingScopeV1 = LEGACY_TEST_SCOPE
    livemode: bool = Field(strict=True, default=False)

    @model_validator(mode="after")
    def exact_mode(self) -> "ScopedBillingResult":
        if self.livemode != (self.scope.environment == "live"):
            raise ValueError("billing response environment mismatch")
        return self


class SubscriptionState(ScopedBillingResult):
    qualification: OfferQualificationV1 | None = None
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


class CheckoutResult(ScopedBillingResult):
    id: str = Field(pattern=r"^cs_[A-Za-z0-9_]{1,128}$")
    url: str | None = Field(default=None, max_length=2048)
    expires_at: AwareDatetime


class CheckoutState(ScopedBillingResult):
    id: str = Field(pattern=r"^cs_[A-Za-z0-9_]{1,128}$")
    customer_id: str = Field(pattern=r"^cus_[A-Za-z0-9_]{1,128}$")
    status: Literal["open", "complete", "expired"]
    subscription_id: str | None = Field(default=None, pattern=r"^sub_[A-Za-z0-9_]{1,128}$")
    observed_at: AwareDatetime


class BillingTransport(Protocol):
    @property
    def mode(self) -> Literal["fixture", "stripe_test", "stripe_live"]: ...

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
    scope = LEGACY_TEST_SCOPE
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

    if (
        settings.billing_provider_mode not in {"stripe_test", "stripe_live"}
        or settings.billing_api_key is None
    ):
        return UnavailableBilling()
    try:
        from app.billing.scope import configured_scope

        scope = configured_scope()
        from app.billing.offers import configured_offer

        configured_offer()
        return StripeBilling(settings.billing_api_key, settings.billing_api_version, scope=scope)
    except ValueError:
        return UnavailableBilling()


@runtime_checkable
class BillingManagementTransport(Protocol):
    def portal(
        self, customer_id: str, configuration_id: str, return_url: str, request_key: str
    ) -> str: ...


@runtime_checkable
class BoundBillingTransport(Protocol):
    def qualify_offer(self, profile: OfferProfileV1) -> None: ...
    def checkout_bound(
        self, bound: BoundOfferV1, customer: str, return_url: str, *, recover_only: bool = False
    ) -> CheckoutResult: ...
    def checkout_state_bound(
        self, bound: BoundOfferV1, customer: str, cid: str, now: datetime
    ) -> CheckoutState: ...
    def current_bound(
        self, bound: BoundOfferV1, customer: str, sid: str, now: datetime
    ) -> SubscriptionState: ...
    def portal_bound(
        self, bound: BoundOfferV1, customer: str, return_url: str, key: str
    ) -> str: ...
