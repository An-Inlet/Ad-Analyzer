"""Strict server-owned commercial profile and immutable original-request bindings."""

import hashlib
import json
from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.billing.scope import BillingScopeV1
from app.goals.schemas import StrictModel

STRIPE_OFFER_VERSION = "2025-06-30.basil"
MAX_OFFER_BYTES = 16_384


def digest(value: StrictModel) -> str:
    encoded = json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    if len(encoded.encode()) > MAX_OFFER_BYTES:
        raise ValueError("billing offer document too large")
    return hashlib.sha256(encoded.encode()).hexdigest()


class PortalOfferV1(StrictModel):
    model_config = {"frozen": True}
    configuration_id: str = Field(pattern=r"^bpc_[A-Za-z0-9_]{1,128}$")
    cancellation_mode: Literal["at_period_end"]
    cancellation_proration: Literal["none"]
    subscription_update: Literal[False]
    customer_update: Literal[False]
    payment_method_update: bool = Field(strict=True)
    invoice_history: bool = Field(strict=True)

    @field_validator("subscription_update", "customer_update", mode="before")
    @classmethod
    def exact_false(cls, value: Any) -> Any:
        if value is not False:
            raise ValueError("unsupported portal policy")
        return value


class OfferProfileV1(StrictModel):
    model_config = {"frozen": True}
    schema_version: Literal["inlet.billing-offer.v1"] = "inlet.billing-offer.v1"
    scope: BillingScopeV1
    api_version: Literal["2025-06-30.basil"]
    price_id: str = Field(pattern=r"^price_[A-Za-z0-9_]{1,128}$")
    product_id: str = Field(pattern=r"^prod_[A-Za-z0-9_]{1,128}$")
    currency: str = Field(pattern=r"^[a-z]{3}$")
    unit_amount: int = Field(strict=True, gt=0, le=99_999_999)
    interval: Literal["day", "week", "month", "year"]
    interval_count: int = Field(strict=True, ge=1, le=366)
    quantity: Literal[1]
    billing_scheme: Literal["per_unit"]
    usage_type: Literal["licensed"]
    tax_policy: Literal["disabled_no_rates"]
    price_tax_behavior: Literal["inclusive", "exclusive"]
    trial_policy: Literal["none"]
    discount_policy: Literal["none"]
    promotion_codes: Literal[False]
    credit_policy: Literal["none"]
    entitlement_payment_policy: Literal["paid_latest_invoice"]
    portal: PortalOfferV1
    max_advertising_accounts: int = Field(strict=True, ge=1, le=100)
    operator_review_reference: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")

    @field_validator("quantity", mode="before")
    @classmethod
    def fixed_quantity(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise ValueError("fixed integer quantity required")
        return value

    @field_validator("promotion_codes", mode="before")
    @classmethod
    def no_promotions(cls, value: Any) -> Any:
        if value is not False:
            raise ValueError("unsupported promotion policy")
        return value

    @model_validator(mode="after")
    def qualified(self) -> "OfferProfileV1":
        if not self.scope.qualified:
            raise ValueError("offer requires qualified scope")
        return self


class BoundOfferV1(StrictModel):
    model_config = {"frozen": True}
    schema_version: Literal["inlet.bound-billing-offer.v1"] = "inlet.bound-billing-offer.v1"
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    workspace_id: int = Field(strict=True, gt=0)
    checkout_key: str = Field(pattern=r"^[0-9]{10,12}_[a-f0-9]{32}$")
    profile: OfferProfileV1
    created_at: AwareDatetime


class OfferQualificationV1(StrictModel):
    model_config = {"frozen": True}
    schema_version: Literal["inlet.billing-offer-qualification.v1"] = (
        "inlet.billing-offer-qualification.v1"
    )
    binding_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    binding_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    scope: BillingScopeV1
    customer_id: str = Field(pattern=r"^cus_[A-Za-z0-9_]{1,128}$")
    subscription_id: str = Field(pattern=r"^sub_[A-Za-z0-9_]{1,128}$")
    price_id: str = Field(pattern=r"^price_[A-Za-z0-9_]{1,128}$")
    product_id: str = Field(pattern=r"^prod_[A-Za-z0-9_]{1,128}$")
    invoice_id: str = Field(pattern=r"^in_[A-Za-z0-9_]{1,128}$")
    payment_id: str = Field(pattern=r"^inpay_[A-Za-z0-9_]{1,128}$")
    payment_intent_id: str = Field(pattern=r"^pi_[A-Za-z0-9_]{1,128}$")
    charge_id: str = Field(pattern=r"^ch_[A-Za-z0-9_]{1,128}$")
    currency: str = Field(pattern=r"^[a-z]{3}$")
    amount_paid: int = Field(strict=True, gt=0)
    period_start: AwareDatetime
    period_end: AwareDatetime
    status: Literal["active"]
    cancel_at_period_end: bool = Field(strict=True)
    observed_at: AwareDatetime
    projection_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def paid_period(self) -> "OfferQualificationV1":
        if not self.period_start <= self.observed_at < self.period_end:
            raise ValueError("qualification outside paid period")
        projection = {
            "binding": self.binding_digest,
            "invoice": self.invoice_id,
            "payment": self.payment_id,
            "intent": self.payment_intent_id,
            "charge": self.charge_id,
            "amount": self.amount_paid,
            "currency": self.currency,
            "start": int(self.period_start.timestamp()),
            "end": int(self.period_end.timestamp()),
            "status": self.status,
            "cancel": self.cancel_at_period_end,
        }
        expected = hashlib.sha256(
            json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if expected != self.projection_digest:
            raise ValueError("qualification projection mismatch")
        return self


def configured_offer() -> OfferProfileV1:
    from app.billing.scope import configured_scope
    from app.settings import settings

    raw = settings.billing_offer_profile
    if raw is None or len(raw.encode()) > MAX_OFFER_BYTES:
        raise ValueError("commercial offer unavailable")
    profile = OfferProfileV1.model_validate_json(raw)
    if profile.scope != configured_scope() or profile.api_version != settings.billing_api_version:
        raise ValueError("commercial offer scope unavailable")
    return profile
