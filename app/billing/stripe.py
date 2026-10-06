"""Real Stripe HTTP adapter, test-mode-only; default factory remains disabled.

No requests occur at import/construction. Tests inject httpx.MockTransport. Release
configuration must explicitly select stripe_test, an API version and a test API key.
Live secret keys and live response objects are rejected independently of settings.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import SecretStr

from app.billing.contracts import CheckoutResult, CheckoutState, SubscriptionState


class BillingProviderError(RuntimeError):
    pass


def identifier(value: str, prefix: str) -> str:
    if re.fullmatch(prefix + r"_[A-Za-z0-9_]{1,128}", value) is None:
        raise BillingProviderError("billing_resource_invalid")
    return value


class StripeBilling:
    mode: Literal["stripe_test"] = "stripe_test"

    def __init__(
        self,
        key: SecretStr,
        version: str,
        *,
        http_transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not key.get_secret_value().startswith("sk_test_") or not re.fullmatch(
            r"20\d{2}-\d{2}-\d{2}(?:\.[a-z]+)?", version
        ):
            raise ValueError("test billing configuration unavailable")
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
    ) -> dict[str, Any]:
        headers = {
            "Authorization": "Bearer " + self.key.get_secret_value(),
            "Stripe-Version": self.version,
        }
        if key is not None:
            # Stripe can prune old idempotency keys. Never resubmit an unresolved
            # mutation after that safe retry window or with an unaged legacy key.
            stamp, _, nonce = key.partition("_")
            if (
                not stamp.isdigit()
                or len(nonce) != 32
                or not 0 <= self.clock().timestamp() - int(stamp) < 23 * 3600
            ):
                raise BillingProviderError("billing_attempt_requires_reconciliation")
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
                    method, "https://api.stripe.com" + path, headers=headers, data=data
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
                if not isinstance(result, dict) or result.get("livemode") is not False:
                    raise BillingProviderError("billing_live_or_invalid_response_blocked")
                return result
        except (httpx.HTTPError, ValueError, TypeError):
            raise BillingProviderError("billing_transport_or_response_unavailable") from None

    def customer(self, workspace_id: int, idempotency_key: str) -> str:
        body = self.request(
            "POST",
            "/v1/customers",
            {"metadata[inlet_workspace_id]": str(workspace_id)},
            idempotency_key,
        )
        return identifier(body["id"], "cus")

    def checkout(
        self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
    ) -> CheckoutResult:
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
            id=body["id"],
            url=body["url"],
            expires_at=datetime.fromtimestamp(body["expires_at"], UTC),
        )

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
            livemode=False,
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
            livemode=False,
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
        if body.get("customer") != customer_id:
            raise BillingProviderError("billing_portal_identity_mismatch")
        url = str(body["url"])
        from urllib.parse import urlsplit

        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "billing.stripe.com":
            raise BillingProviderError("billing_portal_location_invalid")
        return url
