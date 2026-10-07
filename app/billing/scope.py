"""Immutable server-selected billing identity; legacy test data is never live proof."""

from typing import Literal

from pydantic import Field, model_validator

from app.goals.schemas import StrictModel


class BillingScopeV1(StrictModel):
    model_config = {"frozen": True}

    schema_version: Literal["inlet.billing-scope.v1"] = "inlet.billing-scope.v1"
    provider: Literal["stripe"] = "stripe"
    environment: Literal["test", "live"]
    merchant_account_id: str = Field(pattern=r"^(acct_[A-Za-z0-9]{1,128}|legacy_unqualified)$")

    @model_validator(mode="after")
    def live_requires_account(self) -> "BillingScopeV1":
        if self.environment == "live" and not self.qualified:
            raise ValueError("live billing requires an explicit merchant account")
        return self

    @property
    def qualified(self) -> bool:
        return self.merchant_account_id != "legacy_unqualified"

    def key(self, identity: int | str) -> tuple[int | str, str, str, str]:
        return identity, self.provider, self.environment, self.merchant_account_id

    def columns(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "environment": self.environment,
            "merchant_account_id": self.merchant_account_id,
        }


LEGACY_TEST_SCOPE = BillingScopeV1(environment="test", merchant_account_id="legacy_unqualified")


def configured_scope() -> BillingScopeV1:
    from app.settings import settings

    mode = settings.billing_provider_mode
    if mode not in {"stripe_test", "stripe_live"}:
        raise ValueError("billing scope unavailable")
    if mode == "stripe_live" and not settings.billing_live_enabled:
        raise ValueError("live billing disabled")
    scope = BillingScopeV1(
        environment="live" if mode == "stripe_live" else "test",
        merchant_account_id=settings.billing_merchant_account_id,
    )
    if not scope.qualified:
        raise ValueError("billing account qualification required")
    return scope
