"""Real HTTP contract paths with an injected transport; no provider access."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
from app.billing.contracts import UnavailableBilling, get_billing_transport
from app.billing.stripe import BillingProviderError, StripeBilling
from app.settings import settings
from pydantic import SecretStr

NOW = datetime(2026, 10, 6, tzinfo=UTC)
KEY = f"{int(NOW.timestamp())}_{'a' * 32}"


def test_customer_and_checkout_wire_contract() -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.host == "api.stripe.com"
        assert request.headers["stripe-version"] == "2025-03-31.basil"
        assert request.headers["idempotency-key"] == KEY
        body = parse_qs(request.content.decode())
        if request.url.path == "/v1/customers":
            assert body == {
                "metadata[inlet_workspace_id]": ["42"],
                "metadata[inlet_customer_request]": [KEY],
            }
            return httpx.Response(200, json={"id": "cus_test", "livemode": False})
        assert body["customer"] == ["cus_test"]
        assert body["line_items[0][price]"] == ["price_test"]
        assert body["line_items[0][quantity]"] == ["1"]
        assert body["mode"] == ["subscription"]
        return httpx.Response(
            200,
            json={
                "id": "cs_test",
                "livemode": False,
                "customer": "cus_test",
                "mode": "subscription",
                "url": None,
                "expires_at": int(NOW.timestamp()),
            },
        )

    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(respond),
        clock=lambda: NOW,
    )
    assert wire.customer(42, KEY) == "cus_test"
    result = wire.checkout("cus_test", "price_test", KEY, "https://example.test/billing")
    assert result.id == "cs_test" and result.url is None
    assert len(seen) == 2


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
def test_http_failures_are_sanitized(status: int) -> None:
    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(
            lambda _: httpx.Response(status, text="private-payload")
        ),
        clock=lambda: NOW,
    )
    with pytest.raises(BillingProviderError) as error:
        wire.customer(42, KEY)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("payload", [{"livemode": True}, {}, [], "private"])
def test_live_and_malformed_responses_rejected(payload: object) -> None:
    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        clock=lambda: NOW,
    )
    with pytest.raises(BillingProviderError):
        wire.customer(42, KEY)


def test_expired_retry_and_live_key_do_not_reach_transport() -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        pytest.fail("unsafe request reached transport")

    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(forbidden),
        clock=lambda: NOW + timedelta(hours=23),
    )
    with pytest.raises(BillingProviderError, match="requires_reconciliation"):
        wire.request("POST", "/v1/customers", key=KEY)
    with pytest.raises(ValueError):
        StripeBilling(SecretStr("sk_live_synthetic"), "2025-03-31.basil")


def test_default_runtime_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "billing_provider_mode", "disabled")
    assert isinstance(get_billing_transport(), UnavailableBilling)
    monkeypatch.setattr(settings, "billing_provider_mode", "stripe_test")
    monkeypatch.setattr(settings, "billing_api_key", SecretStr("sk_test_synthetic"))
    monkeypatch.setattr(settings, "billing_api_version", "2025-03-31.basil")
    assert isinstance(get_billing_transport(), StripeBilling)


def test_current_subscription_and_checkout_owner_validation() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/v1/subscriptions/"):
            return httpx.Response(
                200,
                json={
                    "id": "sub_test",
                    "customer": "cus_test",
                    "livemode": False,
                    "status": "active",
                    "cancel_at_period_end": False,
                    "items": {
                        "has_more": False,
                        "data": [
                            {
                                "quantity": 1,
                                "price": {"id": "price_test"},
                                "current_period_end": int(NOW.timestamp()) + 3600,
                            }
                        ],
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "cs_test",
                "customer": "cus_test",
                "livemode": False,
                "mode": "subscription",
                "status": "complete",
                "subscription": "sub_test",
            },
        )

    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(respond),
        clock=lambda: NOW,
    )
    assert wire.current("cus_test", "sub_test", NOW).status == "active"
    assert wire.checkout_state("cus_test", "cs_test", NOW).subscription_id == "sub_test"
    with pytest.raises(BillingProviderError, match="owner_mismatch"):
        wire.current("cus_other", "sub_test", NOW)
    with pytest.raises(BillingProviderError, match="identity_mismatch"):
        wire.checkout_state("cus_other", "cs_test", NOW)


@pytest.mark.parametrize("fault", ["timeout", "oversized", "invalid_json"])
def test_bounded_response_and_transport_failure(fault: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.extensions["timeout"]["connect"] == 5
        assert request.extensions["timeout"]["read"] == 15
        if fault == "timeout":
            raise httpx.ReadTimeout("private-detail", request=request)
        return httpx.Response(200, content=b"x" * (2_000_001 if fault == "oversized" else 1))

    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(respond),
        clock=lambda: NOW,
    )
    with pytest.raises(BillingProviderError) as error:
        wire.customer(42, KEY)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("fault", [None, "owner", "url", "configuration"])
def test_portal_request_and_response_scope(fault: str | None) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/billing_portal/sessions"
        form = parse_qs(request.content.decode())
        assert form["customer"] == ["cus_test"]
        assert form["configuration"] == ["bpc_test"]
        assert form["return_url"] == ["https://inlet.example/app/settings"]
        return httpx.Response(
            200,
            json={
                "livemode": False,
                "customer": "cus_other" if fault == "owner" else "cus_test",
                "configuration": "bpc_other" if fault == "configuration" else "bpc_test",
                "url": "https://other.example"
                if fault == "url"
                else "https://billing.stripe.com/session/test",
            },
        )

    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(respond),
        clock=lambda: NOW,
    )
    if fault:
        with pytest.raises(BillingProviderError):
            wire.portal("cus_test", "bpc_test", "https://inlet.example/app/settings", KEY)
    else:
        assert wire.portal(
            "cus_test", "bpc_test", "https://inlet.example/app/settings", KEY
        ).startswith("https://billing.stripe.com/")
