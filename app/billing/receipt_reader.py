"""Original-offer evidence reader: no purchase interface and pre-HTTP GET-only IO."""

from datetime import datetime
from typing import Any, Literal, Protocol

import httpx
from pydantic import SecretStr

from app.billing.contracts import CheckoutState, SubscriptionState
from app.billing.offers import BoundOfferV1
from app.billing.scope import BillingScopeV1
from app.billing.stripe import BillingProviderError, StripeBilling
from app.settings import settings


class BillingReceiptReader(Protocol):
    scope: BillingScopeV1

    def current_bound(
        self, bound: BoundOfferV1, customer: str, sid: str, now: datetime
    ) -> SubscriptionState: ...

    def checkout_state_bound(
        self, bound: BoundOfferV1, customer: str, cid: str, now: datetime
    ) -> CheckoutState: ...


class _GetOnlyStripe(StripeBilling):
    def request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        data: dict[str, str] | None = None,
        key: str | None = None,
        *,
        params: dict[str, str] | None = None,
        collection: Literal["resources", "line_items"] | None = None,
    ) -> dict[str, Any]:
        if method != "GET" or data is not None or key is not None:
            raise BillingProviderError("receipt_reader_get_only")
        return super().request(method, path, params=params, collection=collection)


class StripeReceiptReader:
    def __init__(
        self,
        scope: BillingScopeV1,
        key: SecretStr,
        *,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not scope.qualified or not key.get_secret_value().startswith(
            "sk_" + scope.environment + "_"
        ):
            raise ValueError("receipt reader identity unavailable")
        self.scope, self._key, self._http = scope, key, http_transport

    def _wire(self, bound: BoundOfferV1) -> _GetOnlyStripe:
        if bound.profile.scope != self.scope:
            raise BillingProviderError("receipt reader binding mismatch")
        return _GetOnlyStripe(
            self._key, bound.profile.api_version, scope=self.scope, http_transport=self._http
        )

    def current_bound(
        self, bound: BoundOfferV1, customer: str, sid: str, now: datetime
    ) -> SubscriptionState:
        return self._wire(bound).current_bound(bound, customer, sid, now)

    def checkout_state_bound(
        self, bound: BoundOfferV1, customer: str, cid: str, now: datetime
    ) -> CheckoutState:
        return self._wire(bound).checkout_state_bound(bound, customer, cid, now)


def get_billing_receipt_reader() -> BillingReceiptReader:
    if not settings.billing_receipt_read_enabled or settings.billing_api_key is None:
        raise ValueError("billing receipt reads unavailable")
    environment = settings.billing_receipt_environment
    if environment not in {"test", "live"} or (
        settings.app_env == "production" and environment != "live"
    ):
        raise ValueError("billing receipt environment unavailable")
    scope = BillingScopeV1(
        environment="live" if environment == "live" else "test",
        merchant_account_id=settings.billing_merchant_account_id,
    )
    return StripeReceiptReader(scope, settings.billing_api_key)
