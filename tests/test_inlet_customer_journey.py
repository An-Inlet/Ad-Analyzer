"""One assembled-application journey; all provider seams are injected offline.

Shopify connection installation remains an explicit fixture boundary until the
customer-authenticated Shopify onboarding routes are available. This does not
claim self-serve Shopify onboarding, account closure, or a live purchase.
"""

from collections.abc import Generator
from datetime import datetime, tzinfo
from typing import Self
from urllib.parse import parse_qs, urlsplit

import pytest
from app.api import customer_billing, customer_goals, customer_google
from app.billing.contracts import get_billing_transport
from app.billing.dispatcher import run as reconcile_billing
from app.billing.models import BillingEvent
from app.commerce import reporting
from app.commerce.ledger import MEASUREMENT_SCOPES, apply_order, bind_store, retention_floor
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.database.session import get_db
from app.goals import service as goals
from app.google_connections import service as google
from app.google_connections.contracts import get_transport
from app.google_connections.models import GoogleCustomerConnection
from app.imports.native import bind_shopify
from app.main import app
from app.settings import Settings, settings
from app.shopify.models import ShopifyConnection
from app.shopify.security import Vault
from app.shopify.service import credentials
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_commerce_measurement import NOW, agreement, source
from tests.test_customer_billing import POLICY, SECRET, FixtureBilling, payload, signature
from tests.test_customer_goals import definition
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_provisioning import signup
from tests.test_google_customer_connections import FixtureTransport
from tests.test_google_customer_connections import configured as configured
from tests.test_shopify_sales import configuration as configuration


class JourneyClock(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> Self:
        return cls.fromtimestamp(NOW.timestamp(), tz or NOW.tzinfo)


def install_fixture_baseline(
    db: Session,
    wid: int,
    configuration: Settings,
    *,
    shop: str = "journey-fixture.myshopify.com",
    shop_id: str = "123",
) -> str:
    """Explicit fixture installation, then the real binding/ledger code path."""
    configuration.shopify_measurement_enabled = True
    bundle = credentials(
        {
            "access_token": "offline-journey",
            "refresh_token": "offline-refresh",
            "expires_in": 3600,
            "scope": ",".join(sorted(MEASUREMENT_SCOPES)),
        },
        NOW,
    )
    row = ShopifyConnection(
        workspace_id=wid,
        shop_domain=shop,
        shop_name="Journey Fixture",
        currency_code="USD",
        time_zone="UTC",
        connected_at=NOW,
        encrypted_credentials=Vault(configuration).seal(wid, shop, bundle),
    )
    db.add(row)
    db.flush()
    bind_shopify(db, row)
    store = bind_store(db, row, f"gid://shopify/Shop/{shop_id}", configuration, NOW)
    store.covered_from, store.last_sync_at = retention_floor(NOW), NOW
    apply_order(db, store, row, source(), [agreement()], configuration, NOW)
    db.commit()
    return store.id


def test_customer_journey_through_assembled_app(
    customer_engine: Engine,
    configuration: Settings,
    configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for module in (customer_billing, customer_goals, customer_google, goals, reporting):
        monkeypatch.setattr(module, "datetime", JourneyClock)
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(settings, "billing_price_id", POLICY.price_id)
    monkeypatch.setattr(settings, "billing_required", True)
    monkeypatch.setattr(settings, "billing_webhook_secret", SecretStr(SECRET))
    identity, ads, billing = FakeProvider(), FixtureTransport(), FixtureBilling()
    factory = sessionmaker(customer_engine)

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    # Use the actual assembled app and routers, not a test-specific router subset.
    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: identity,
            get_transport: lambda: ads,
            get_billing_transport: lambda: billing,
        },
    )
    owner, outsider = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    login(owner, "journey-owner:1")
    login(outsider, "journey-outsider:1")
    created = signup(owner, "journey-workspace-1", "journey-brand")
    assert created.status_code == 201
    wid = created.json()["id"]
    assert created.json()["role"] == "owner"
    assert signup(owner, "journey-workspace-1", "journey-brand").json()["id"] == wid
    root = f"/api/customer/v1/workspaces/{wid}"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": owner.cookies[CSRF_COOKIE]}
    assert outsider.get(root).status_code == 404
    authorization = owner.post(root + "/google/authorize", headers=headers)
    assert authorization.status_code == 200
    state = parse_qs(urlsplit(authorization.json()["authorization_url"]).query)["state"][0]
    assert (
        owner.post(
            "/api/customer/v1/google/callback",
            headers=headers,
            json={"state": state, "code": "offline-fixture"},
        ).status_code
        == 200
    )
    selected = owner.post(
        root + "/google/select",
        headers=headers,
        json={"state": state, "external_account_id": "1234567890"},
    )
    assert selected.status_code == 200 and selected.json()["live_verified"] is False
    cid = selected.json()["id"]
    with factory() as db:
        row = db.get(GoogleCustomerConnection, cid)
        assert row is not None
        generation = row.generation
        calls = ads.calls
        with pytest.raises(HTTPException) as denied:
            google.tick(db, wid, cid, generation, ads, NOW)
        assert denied.value.status_code == 402 and ads.calls == calls
        db.rollback()
        store_id = install_fixture_baseline(db, wid, configuration)
    stores = owner.get(root + "/commerce/stores")
    assert stores.status_code == 200 and stores.json()[0]["id"] == store_id
    create_headers = {**headers, "Idempotency-Key": "journey-goal-1"}
    body = {"definition": definition(store_id).model_dump(mode="json")}
    draft = owner.post(root + "/goals", json=body, headers=create_headers)
    assert draft.status_code == 201
    gid = draft.json()["id"]
    assert owner.post(root + "/goals", json=body, headers=create_headers).json()["id"] == gid
    path = root + "/goals/" + gid
    preview = owner.post(path + "/preview", json={"expected_revision": 1}, headers=headers)
    assert preview.status_code == 200
    snapshot = owner.get(root + "/commerce/snapshots/" + preview.json()["snapshot_id"])
    assert snapshot.status_code == 200 and snapshot.json()["quality"] == "complete"
    assert snapshot.json()["net_sales_micros"] == 90_000_000
    assert (
        outsider.get(root + "/commerce/snapshots/" + preview.json()["snapshot_id"]).status_code
        == 404
    )
    confirmed = owner.post(
        path + "/confirm",
        headers=headers,
        json={
            "expected_revision": 1,
            "preview_id": preview.json()["preview_id"],
            "idempotency_key": "journey-confirm-1",
        },
    )
    assert confirmed.status_code == 200 and confirmed.json()["assessment"] == "confirmed"
    assert confirmed.json()["spending_authorized"] is False
    assert owner.post(root + "/billing/checkout", headers=headers).status_code == 200
    assert owner.get(root + "/billing").json()["status"] != "active"
    event = payload("evt_journey_active")
    response = owner.post(
        "/api/billing/stripe/events", content=event, headers={"Stripe-Signature": signature(event)}
    )
    assert response.status_code == 200 and response.json()["received"] is True
    assert reconcile_billing(factory, POLICY, billing, NOW)["events"] == 1
    assert owner.get(root + "/billing").json()["status"] == "active"
    with factory() as db:
        # Entitlement now permits the real import service with the fixture transport.
        google.tick(db, wid, cid, generation, ads, NOW)
        assert ads.calls == calls + 1
        assert db.scalar(select(func.count()).select_from(BillingEvent)) == 1
    billing.state = billing.state.model_copy(update={"status": "canceled"})
    event = payload("evt_journey_canceled", status="canceled")
    assert (
        owner.post(
            "/api/billing/stripe/events",
            content=event,
            headers={"Stripe-Signature": signature(event)},
        ).status_code
        == 200
    )
    assert reconcile_billing(factory, POLICY, billing, NOW)["events"] == 1
    assert owner.get(root + "/billing").json()["status"] == "canceled"
    with factory() as db, pytest.raises(HTTPException) as denied:
        google.tick(db, wid, cid, generation, ads, NOW)
    assert denied.value.status_code == 402
    disconnected = owner.delete(root + "/google/connections/" + cid, headers=headers)
    assert disconnected.status_code == 200 and disconnected.json()["status"] == "disconnected"
    with factory() as db:
        row = db.get(GoogleCustomerConnection, cid)
        assert row is not None and row.encrypted_grant is None
    assert owner.delete("/api/customer/v1/session", headers=headers).status_code == 204
    assert owner.get(root + "/goals").status_code == 401
