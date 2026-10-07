"""Offline test/live collisions, ownership and mandatory production entitlement."""

import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.billing import repository
from app.billing.contracts import UnavailableBilling, get_billing_transport
from app.billing.entitlements import live_paid_work
from app.billing.models import BillingEvent
from app.billing.scope import LEGACY_TEST_SCOPE, BillingScopeV1
from app.billing.service import owned, require_entitlement
from app.billing.stripe import BillingProviderError, StripeBilling
from app.billing.webhooks import receive
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.inventory import predicate
from app.settings import settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_billing import POLICY, SECRET, payload, signature
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup

TEST = BillingScopeV1(environment="test", merchant_account_id="acct_fixture")
LIVE = BillingScopeV1(environment="live", merchant_account_id="acct_fixture")
OTHER = BillingScopeV1(environment="live", merchant_account_id="acct_other")


def event_body(scope: BillingScopeV1) -> bytes:
    body = json.loads(payload("evt_identical"))
    body["livemode"] = scope.environment == "live"
    return json.dumps(body).encode()


def test_same_resource_ids_are_isolated_and_export_is_owned(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        wid, _ = setup(db, "billing")
        other, _ = setup(db, "other")
        for scope, workspace in ((TEST, wid), (LIVE, other), (OTHER, other)):
            row = owned(db, workspace, NOW, scope=scope)
            row.customer_id, row.subscription_id = "cus_fixture", "sub_fixture"
            db.commit()
            body = event_body(scope)
            assert receive(db, body, signature(body), SECRET, NOW, scope=scope)
            assert not receive(db, body, signature(body), SECRET, NOW, scope=scope)
        assert repository.billing(db, wid, LIVE) is None
        assert repository.billing(db, wid, LEGACY_TEST_SCOPE) is None
        rows = list(
            db.scalars(
                select(BillingEvent).where(
                    predicate("customer_billing_events", LifecycleScopeV1(workspace_id=wid))
                )
            )
        )
        assert len(rows) == 1 and rows[0].environment == "test"
        assert len(list(db.scalars(select(BillingEvent)))) == 3
        existing = repository.billing(db, wid, TEST)
        assert existing is not None
        existing.environment = "live"
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()


def test_webhook_cannot_cross_mode(customer_engine: Engine) -> None:
    body = event_body(TEST)
    with Session(customer_engine) as db:
        with pytest.raises(HTTPException, match="invalid billing event"):
            receive(db, body, signature(body), SECRET, NOW, scope=LIVE)
        assert db.scalar(select(BillingEvent)) is None


def test_live_gate_ignores_rollout_bypass_and_test_snapshot(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "billing_required", False)
    monkeypatch.setattr(settings, "billing_provider_mode", "stripe_live")
    monkeypatch.setattr(settings, "billing_live_enabled", True)
    monkeypatch.setattr(settings, "billing_live_max_accounts", 3)
    monkeypatch.setattr(settings, "billing_merchant_account_id", LIVE.merchant_account_id)
    monkeypatch.setattr(settings, "billing_price_id", POLICY.price_id)
    with Session(customer_engine) as db:
        wid, _ = setup(db, "billing")
        row = owned(db, wid, NOW, scope=TEST)
        row.status, row.price_id = "active", POLICY.price_id
        row.verified_at, row.period_end = NOW, NOW + timedelta(days=30)
        db.commit()
        with pytest.raises(HTTPException, match="qualified paid offer unavailable"):
            require_entitlement(db, wid, POLICY, NOW, scope=TEST)
        with pytest.raises(HTTPException):
            live_paid_work(db, wid, NOW)
        db.rollback()
        monkeypatch.setattr(settings, "billing_provider_mode", "stripe_test")
        with pytest.raises(HTTPException, match="live billing qualification"):
            live_paid_work(db, wid, NOW)


def test_live_factory_defaults_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "billing_provider_mode", "stripe_live")
    monkeypatch.setattr(settings, "billing_live_enabled", False)
    assert isinstance(get_billing_transport(), UnavailableBilling)


@pytest.mark.parametrize("scope", [TEST, LIVE])
def test_stripe_checks_merchant_and_mode_before_accepting_customer(scope: BillingScopeV1) -> None:
    requests: list[tuple[str, str]] = []
    account: dict[str, Any] = {"object": "account", "id": scope.merchant_account_id}
    response: dict[str, Any] = {"id": "cus_fixture", "livemode": scope.environment == "live"}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        return httpx.Response(200, json=account if request.url.path == "/v1/account" else response)

    transport = StripeBilling(
        SecretStr("sk_" + scope.environment + "_offline_fixture"),
        "2025-06-30.basil",
        scope=scope,
        http_transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )
    key = f"{int(NOW.timestamp())}_" + "a" * 32
    assert transport.customer(1, key) == "cus_fixture"
    assert requests == [("GET", "/v1/account"), ("POST", "/v1/customers")]
    requests.clear()
    account["id"] = "acct_wrong"
    with pytest.raises(BillingProviderError, match="merchant_mismatch"):
        transport.customer(1, key)
    assert requests == [("GET", "/v1/account")]
    account["id"] = scope.merchant_account_id
    response["livemode"] = scope.environment != "live"
    with pytest.raises(BillingProviderError, match="invalid_response"):
        transport.customer(1, key)


def test_mock_http_checkout_dispatch_and_cancel_remain_in_live_scope(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Live transport now requires a fully reviewed offer and paid-invoice proof;
    # reuse the complete HTTP fixture while retaining the cross-environment assertions.
    from tests.test_billing_offers import qualified_journey

    qualified_journey(customer_engine, monkeypatch)


def test_closure_receipt_lane_does_not_cross_environment(customer_engine: Engine) -> None:
    from app.lifecycle.billing_receipts import retain_pending
    from app.lifecycle.quiescing import quiesce

    from tests.test_customer_identity import FakeProvider
    from tests.test_customer_lifecycle import seed
    from tests.test_customer_quiescing import confirmed

    with Session(customer_engine) as db:
        principal, wid = seed(db)
        _, other = seed(db, "other")
        for scope, target in ((LIVE, wid), (TEST, other)):
            row = owned(db, target, NOW, scope=scope)
            row.customer_id, row.subscription_id = "cus_fixture", "sub_fixture"
            db.commit()
        request_id, evidence = confirmed(db, principal, wid)
        quiesce(db, principal, FakeProvider(), wid, request_id, 1, evidence, NOW)
        db.commit()
        for scope in (TEST, LIVE):
            body = event_body(scope)
            receive(db, body, signature(body), SECRET, NOW, scope=scope)
    assert retain_pending(lambda: Session(customer_engine)) == 1
    with Session(customer_engine) as db:
        assert repository.event(db, "evt_identical", LIVE).state == "closure_pending"  # type: ignore[union-attr]
        assert repository.event(db, "evt_identical", TEST).state == "pending"  # type: ignore[union-attr]


def test_live_signed_endpoint_rejects_test_body_and_legacy_route_rejects_live(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Generator
    from unittest.mock import Mock

    from app.api import customer_billing as api
    from app.database.session import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    clock = Mock()
    clock.now.return_value = NOW
    monkeypatch.setattr(api, "datetime", clock)
    monkeypatch.setattr(settings, "billing_provider_mode", "stripe_live")
    monkeypatch.setattr(settings, "billing_live_enabled", True)
    monkeypatch.setattr(settings, "billing_merchant_account_id", LIVE.merchant_account_id)
    monkeypatch.setattr(settings, "billing_live_webhook_secret", SecretStr(SECRET))
    monkeypatch.setattr(settings, "billing_webhook_secret", SecretStr(SECRET))
    app = FastAPI()
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    client = TestClient(app)
    live, test = event_body(LIVE), event_body(TEST)
    assert client.post(
        "/api/billing/stripe/live/events",
        content=live,
        headers={"Stripe-Signature": signature(live)},
    ).json() == {"received": True}
    assert (
        client.post(
            "/api/billing/stripe/live/events",
            content=test,
            headers={"Stripe-Signature": signature(test)},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/billing/stripe/events",
            content=live,
            headers={"Stripe-Signature": signature(live)},
        ).status_code
        == 400
    )
    monkeypatch.setattr(settings, "billing_live_enabled", False)
    assert client.post(
        "/api/billing/stripe/live/events",
        content=live,
        headers={"Stripe-Signature": signature(live)},
    ).json() == {"received": False}
