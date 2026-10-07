"""Scoped Stripe HTTP adapter; qualified test/live runtimes are disabled by default.

No IO at construction. Every qualified call first verifies the authenticated account;
response livemode and key family must match the immutable configured scope.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import SecretStr

from app.billing.contracts import CheckoutResult, CheckoutState, SubscriptionState
from app.billing.offers import BoundOfferV1, OfferProfileV1
from app.billing.scope import LEGACY_TEST_SCOPE, BillingScopeV1


class BillingProviderError(RuntimeError):
    pass


class BillingReconciliationRequired(BillingProviderError):
    """An uncertain attempt must never be blindly recreated."""


def attempt_stamp(key: str) -> int:
    match = re.fullmatch(r"([0-9]{10,12})_([a-f0-9]{32})", key)
    if match is None:
        raise BillingReconciliationRequired("billing_attempt_requires_reconciliation")
    return int(match[1])


def identifier(value: str, prefix: str) -> str:
    if re.fullmatch(prefix + r"_[A-Za-z0-9_]{1,128}", value) is None:
        raise BillingProviderError("billing_resource_invalid")
    return value


class StripeBilling:
    mode: Literal["stripe_test", "stripe_live"] = "stripe_test"

    def __init__(
        self,
        key: SecretStr,
        version: str,
        *,
        scope: BillingScopeV1 = LEGACY_TEST_SCOPE,
        http_transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.scope = scope
        self.mode = "stripe_live" if scope.environment == "live" else "stripe_test"
        if not key.get_secret_value().startswith(
            "sk_" + scope.environment + "_"
        ) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}(?:\.[a-z]+)?", version):
            raise ValueError("billing configuration unavailable")
        self.key, self.version, self.http_transport, self.clock = (
            key,
            version,
            http_transport,
            clock,
        )

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
        if path != "/v1/account" and self.scope.qualified:
            account = self.request("GET", "/v1/account")
            if (
                account.get("object") != "account"
                or account.get("id") != self.scope.merchant_account_id
            ):
                raise BillingProviderError("billing_merchant_mismatch")
        headers = {
            "Authorization": "Bearer " + self.key.get_secret_value(),
            "Stripe-Version": self.version,
        }
        if key is not None:
            # Stripe can prune old idempotency keys. Never resubmit an unresolved
            # mutation after that safe retry window or with an unaged legacy key.
            if not 0 <= self.clock().timestamp() - attempt_stamp(key) < 23 * 3600:
                raise BillingReconciliationRequired("billing_attempt_requires_reconciliation")
            headers["Idempotency-Key"] = key
        try:
            with (
                httpx.Client(
                    transport=self.http_transport,
                    timeout=httpx.Timeout(15, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(
                    method,
                    "https://api.stripe.com" + path,
                    headers=headers,
                    data=data,
                    params=params,
                ) as response,
            ):
                if response.status_code in {401, 403}:
                    raise BillingProviderError("billing_authorization_unavailable")
                if response.status_code == 429:
                    raise BillingProviderError("billing_rate_limited")
                if not 200 <= response.status_code < 300:
                    raise BillingProviderError("billing_request_unconfirmed")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        raise BillingProviderError("billing_response_too_large")
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise BillingProviderError("billing_response_invalid")
                if path == "/v1/account" and method == "GET":
                    pass
                elif collection is None:
                    if result.get("livemode") is not (self.scope.environment == "live"):
                        raise BillingProviderError("billing_live_or_invalid_response_blocked")
                else:
                    rows = result.get("data")
                    if (
                        result.get("object") not in {"list", "search_result"}
                        or type(result.get("has_more")) is not bool
                        or not isinstance(rows, list)
                        or len(rows) > 100
                    ):
                        raise BillingProviderError("billing_collection_invalid")
                    for row in rows:
                        if not isinstance(row, dict):
                            raise BillingProviderError("billing_collection_invalid")
                        checked = row.get("price") if collection == "line_items" else row
                        if not isinstance(checked, dict) or checked.get("livemode") is not (
                            self.scope.environment == "live"
                        ):
                            raise BillingProviderError("billing_live_or_invalid_response_blocked")
                return result
        except (httpx.HTTPError, ValueError, TypeError):
            raise BillingProviderError("billing_transport_or_response_unavailable") from None

    def customer(self, workspace_id: int, idempotency_key: str) -> str:
        if self.expired_attempt(idempotency_key):
            return self.recover_customer(workspace_id, idempotency_key)
        body = self.request(
            "POST",
            "/v1/customers",
            {
                "metadata[inlet_workspace_id]": str(workspace_id),
                "metadata[inlet_customer_request]": idempotency_key,
            },
            idempotency_key,
        )
        return identifier(body["id"], "cus")

    def checkout(
        self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
    ) -> CheckoutResult:
        if self.expired_attempt(idempotency_key):
            body = self.recover_checkout(customer_id, price_id, idempotency_key)
        else:
            body = self.request(
                "POST",
                "/v1/checkout/sessions",
                {
                    "customer": identifier(customer_id, "cus"),
                    "mode": "subscription",
                    "line_items[0][price]": identifier(price_id, "price"),
                    "line_items[0][quantity]": "1",
                    "success_url": return_url,
                    "cancel_url": return_url,
                    "metadata[inlet_checkout_request]": idempotency_key,
                },
                idempotency_key,
            )
        if body.get("customer") != customer_id or body.get("mode") != "subscription":
            raise BillingProviderError("billing_checkout_identity_mismatch")
        return CheckoutResult(
            scope=self.scope,
            livemode=self.scope.environment == "live",
            id=body["id"],
            url=body["url"],
            expires_at=datetime.fromtimestamp(body["expires_at"], UTC),
        )

    def expired_attempt(self, key: str) -> bool:
        age = self.clock().timestamp() - attempt_stamp(key)
        if age < 0:
            raise BillingReconciliationRequired("billing_attempt_requires_reconciliation")
        return age >= 23 * 3600

    def recover_customer(self, workspace_id: int, key: str) -> str:
        # Search is eventually consistent: an empty result is never proof that
        # creation failed and NEVER authorizes another POST or a fresh key.
        query = (
            f"metadata['inlet_workspace_id']:'{workspace_id}' AND "
            f"metadata['inlet_customer_request']:'{key}'"
        )
        result = self.request(
            "GET",
            "/v1/customers/search",
            params={"query": query, "limit": "2"},
            collection="resources",
        )
        rows = result["data"]
        if result["has_more"] or len(rows) != 1:
            raise BillingReconciliationRequired("billing_customer_reconciliation_unresolved")
        body = self.request("GET", "/v1/customers/" + identifier(rows[0]["id"], "cus"))
        metadata = body.get("metadata", {})
        if (
            body.get("id") != rows[0]["id"]
            or not isinstance(metadata, dict)
            or metadata.get("inlet_workspace_id") != str(workspace_id)
            or metadata.get("inlet_customer_request") != key
        ):
            raise BillingReconciliationRequired("billing_customer_reconciliation_mismatch")
        return identifier(body["id"], "cus")

    def recover_checkout(self, customer: str, price: str, key: str) -> dict[str, Any]:
        customer, price = identifier(customer, "cus"), identifier(price, "price")
        params = {
            "customer": customer,
            "limit": "100",
            "created[gte]": str(max(0, attempt_stamp(key) - 60)),
            "created[lte]": str(int(self.clock().timestamp())),
        }
        matches: set[str] = set()
        seen: set[str] = set()
        for _ in range(100):
            page = self.request(
                "GET", "/v1/checkout/sessions", params=params, collection="resources"
            )
            rows = page["data"]
            for row in rows:
                cid = identifier(row["id"], "cs")
                if row.get("customer") != customer or cid in seen:
                    raise BillingReconciliationRequired("billing_checkout_reconciliation_mismatch")
                seen.add(cid)
                metadata = row.get("metadata", {})
                if not isinstance(metadata, dict):
                    raise BillingReconciliationRequired("billing_checkout_reconciliation_mismatch")
                if metadata.get("inlet_checkout_request") == key:
                    matches.add(cid)
            if not page["has_more"]:
                break
            if not rows:
                raise BillingReconciliationRequired("billing_checkout_reconciliation_unresolved")
            params["starting_after"] = rows[-1]["id"]
        else:
            raise BillingReconciliationRequired("billing_checkout_reconciliation_unresolved")
        if len(matches) != 1:
            raise BillingReconciliationRequired("billing_checkout_reconciliation_unresolved")
        cid = matches.pop()
        body = self.request("GET", "/v1/checkout/sessions/" + cid)
        metadata = body.get("metadata")
        if (
            body.get("id") != cid
            or body.get("customer") != customer
            or body.get("mode") != "subscription"
            or not isinstance(metadata, dict)
            or metadata.get("inlet_checkout_request") != key
        ):
            raise BillingReconciliationRequired("billing_checkout_reconciliation_mismatch")
        items = self.request(
            "GET",
            "/v1/checkout/sessions/" + cid + "/line_items",
            params={"limit": "2"},
            collection="line_items",
        )
        if (
            items["has_more"]
            or len(items["data"]) != 1
            or type(items["data"][0].get("quantity")) is not int
            or items["data"][0]["quantity"] != 1
            or items["data"][0]["price"].get("id") != price
        ):
            raise BillingReconciliationRequired("billing_checkout_price_mismatch")
        return body

    def checkout_state(self, customer_id: str, checkout_id: str, now: datetime) -> CheckoutState:
        body = self.request("GET", "/v1/checkout/sessions/" + identifier(checkout_id, "cs"))
        if (
            body.get("id") != checkout_id
            or body.get("customer") != customer_id
            or body.get("mode") != "subscription"
        ):
            raise BillingProviderError("billing_checkout_identity_mismatch")
        return CheckoutState(
            id=body["id"],
            customer_id=body["customer"],
            status=body["status"],
            subscription_id=body.get("subscription"),
            observed_at=now,
            scope=self.scope,
            livemode=self.scope.environment == "live",
        )

    def current(self, customer_id: str, subscription_id: str, now: datetime) -> SubscriptionState:
        body = self.request("GET", "/v1/subscriptions/" + identifier(subscription_id, "sub"))
        items = body.get("items", {})
        rows = items.get("data", [])
        if (
            body.get("id") != subscription_id
            or body.get("customer") != customer_id
            or items.get("has_more") is not False
            or len(rows) != 1
            or rows[0].get("quantity") != 1
        ):
            raise BillingProviderError("billing_subscription_shape_or_owner_mismatch")
        period_end = rows[0].get("current_period_end", body.get("current_period_end"))
        return SubscriptionState(
            customer_id=customer_id,
            subscription_id=subscription_id,
            price_id=rows[0]["price"]["id"],
            status=body["status"],
            period_end=datetime.fromtimestamp(period_end, UTC),
            cancel_at_period_end=body["cancel_at_period_end"],
            observed_at=now,
            scope=self.scope,
            livemode=self.scope.environment == "live",
        )

    def portal(
        self, customer_id: str, configuration_id: str, return_url: str, request_key: str
    ) -> str:
        body = self.request(
            "POST",
            "/v1/billing_portal/sessions",
            {
                "customer": identifier(customer_id, "cus"),
                "configuration": identifier(configuration_id, "bpc"),
                "return_url": return_url,
            },
            request_key,
        )
        if body.get("customer") != customer_id or body.get("configuration") != configuration_id:
            raise BillingProviderError("billing_portal_identity_mismatch")
        url = str(body["url"])
        from urllib.parse import urlsplit

        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "billing.stripe.com":
            raise BillingProviderError("billing_portal_location_invalid")
        return url

    def qualify_offer(self, profile: OfferProfileV1) -> None:
        from app.billing.offer_stripe import portal_configuration, price

        price(self, profile)
        portal_configuration(self, profile)

    def checkout_bound(
        self, bound: BoundOfferV1, customer: str, return_url: str, *, recover_only: bool = False
    ) -> CheckoutResult:
        from app.billing.offer_stripe import checkout

        return checkout(self, bound, customer, return_url, recover_only=recover_only)

    def checkout_state_bound(
        self, bound: BoundOfferV1, customer: str, cid: str, now: datetime
    ) -> CheckoutState:
        from app.billing.offer_stripe import checkout_state

        return checkout_state(self, bound, customer, cid, now)

    def current_bound(
        self, bound: BoundOfferV1, customer: str, sid: str, now: datetime
    ) -> SubscriptionState:
        from app.billing.offer_stripe import current

        return current(self, bound, customer, sid, now)

    def portal_bound(self, bound: BoundOfferV1, customer: str, return_url: str, key: str) -> str:
        from app.billing.offer_stripe import portal

        return portal(self, bound, customer, return_url, key)
