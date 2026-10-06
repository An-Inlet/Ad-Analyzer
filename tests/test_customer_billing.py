"""Offline billing state and retry acceptance; no Stripe access or real money."""

import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Literal

import pytest
from app.billing.contracts import (
    BillingPolicy,
    CheckoutResult,
    CheckoutState,
    SubscriptionState,
    UnavailableBilling,
)
from app.billing.models import BillingEvent, WorkspaceBilling
from app.billing.service import checkout, reconcile, require_entitlement
from app.billing.webhooks import receive
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup

POLICY = BillingPolicy(price_id="price_fixture", max_accounts=3)
SECRET = "offline-signature-test-value"


def payload(eid: str, kind: str = "customer.subscription.updated", status: str = "active") -> bytes:
    return json.dumps(
        {
            "id": eid,
            "type": kind,
            "livemode": False,
            "data": {"object": {"id": "sub_fixture", "customer": "cus_fixture", "status": status}},
        }
    ).encode()


def signature(body: bytes, now: datetime = NOW) -> str:
    stamp = str(int(now.timestamp()))
    digest = hmac.new(SECRET.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={digest}"


class FixtureBilling:
    mode: Literal["fixture"] = "fixture"

    def __init__(self) -> None:
        self.keys: list[str] = []
        self.fail = False
        self.state = SubscriptionState(
            customer_id="cus_fixture",
            subscription_id="sub_fixture",
            price_id=POLICY.price_id,
            status="active",
            period_end=NOW + timedelta(days=30),
            cancel_at_period_end=False,
            observed_at=NOW,
        )

    def customer(self, workspace_id: int, idempotency_key: str) -> str:
        self.keys.append(idempotency_key)
        return "cus_fixture"

    def checkout(
        self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
    ) -> CheckoutResult:
        self.keys.append(idempotency_key)
        if self.fail:
            raise TimeoutError("private provider detail")
        return CheckoutResult(
            id="cs_fixture",
            url="https://checkout.stripe.com/c/fixture",
            expires_at=NOW + timedelta(hours=1),
        )

    def checkout_state(self, customer_id: str, checkout_id: str, now: datetime) -> CheckoutState:
        if self.fail:
            raise TimeoutError("synthetic provider unavailable")
        return CheckoutState(
            id=checkout_id,
            customer_id=customer_id,
            status="expired" if now >= NOW + timedelta(hours=1) else "open",
            observed_at=now,
        )

    def current(self, customer_id: str, subscription_id: str, now: datetime) -> SubscriptionState:
        if self.fail:
            raise RuntimeError("private provider detail")
        return self.state.model_copy(update={"observed_at": now})


def test_checkout_uncertainty_reuses_durable_key_and_current_events(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        wid, _ = setup(db, "billing")
        other, _ = setup(db, "other")
        fixture = FixtureBilling()
        with pytest.raises(HTTPException, match="unavailable"):
            checkout(db, wid, POLICY, UnavailableBilling(), "https://inlet.example/settings", NOW)
        fixture.fail = True
        with pytest.raises(HTTPException, match="retry safely"):
            checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        key = fixture.keys[-1]
        fixture.fail = False
        result = checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        assert result["mode"] == "fixture" and fixture.keys[-1] == key
        assert checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW) == result
        before = payload("evt_new")
        assert receive(db, before, signature(before), SECRET, NOW)
        assert not receive(db, before, signature(before), SECRET, NOW)
        assert reconcile(db, wid, "evt_new", POLICY, fixture, NOW)
        assert not reconcile(db, wid, "evt_new", POLICY, fixture, NOW)
        require_entitlement(db, wid, POLICY, NOW, account_count=3)
        with pytest.raises(HTTPException):
            require_entitlement(db, wid, POLICY, NOW, account_count=4)
        with pytest.raises(HTTPException):
            require_entitlement(db, wid, POLICY, NOW + timedelta(minutes=6))
        with pytest.raises(HTTPException):
            reconcile(db, other, "evt_new", POLICY, fixture, NOW)
        # Older event says active, but provider now says canceled. Only current state counts.
        fixture.state = fixture.state.model_copy(update={"status": "canceled"})
        older = payload("evt_old", status="active")
        receive(db, older, signature(older), SECRET, NOW)
        reconcile(db, wid, "evt_old", POLICY, fixture, NOW)
        with pytest.raises(HTTPException, match="entitlement"):
            require_entitlement(db, wid, POLICY, NOW)
        assert db.get(WorkspaceBilling, wid).status == "canceled"  # type: ignore[union-attr]
        changed = payload("evt_new", status="canceled")
        with pytest.raises(HTTPException, match="conflicting"):
            receive(db, changed, signature(changed), SECRET, NOW)


def test_signature_failure_and_retryable_verification(customer_engine: Engine) -> None:
    body = payload("evt_retry")
    with Session(customer_engine) as db:
        wid, _ = setup(db, "retry")
        fixture = FixtureBilling()
        checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        for bad_body, signed in [
            (body + b" ", signature(body)),
            (body, signature(body, NOW - timedelta(minutes=6))),
        ]:
            with pytest.raises(HTTPException, match="invalid"):
                receive(db, bad_body, signed, SECRET, NOW)
        assert db.scalar(select(func.count()).select_from(BillingEvent)) == 0
        receive(db, body, signature(body), SECRET, NOW)
        fixture.fail = True
        with pytest.raises(HTTPException, match="verification unavailable"):
            reconcile(db, wid, "evt_retry", POLICY, fixture, NOW)
        row = db.get(BillingEvent, "evt_retry")
        assert row is not None and row.state == "pending"
        fixture.fail = False
        reconcile(db, wid, "evt_retry", POLICY, fixture, NOW)
        assert row.state == "processed"


def test_concurrent_receipts_are_one_event(customer_engine: Engine) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    body = payload("evt_concurrent")

    def submit() -> bool:
        with Session(customer_engine) as db:
            return receive(db, body, signature(body), SECRET, NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert sorted(results) == [False, True]


def test_paid_work_gates_import_before_provider_and_fails_closed(
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.billing.entitlements import paid_work
    from app.google_connections.contracts import UnavailableTransport
    from app.google_connections.service import tick
    from app.settings import settings

    monkeypatch.setattr(settings, "billing_required", True)
    monkeypatch.setattr(settings, "billing_price_id", POLICY.price_id)
    monkeypatch.setattr(settings, "billing_max_accounts", 3)
    with Session(customer_engine) as db:
        wid, _ = setup(db, "gate")
        with pytest.raises(HTTPException) as error:
            tick(db, wid, "absent", 1, UnavailableTransport(), NOW)
        assert error.value.status_code == 402
        fixture = FixtureBilling()
        checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        body = payload("evt_gate")
        receive(db, body, signature(body), SECRET, NOW)
        reconcile(db, wid, "evt_gate", POLICY, fixture, NOW)
        paid_work(db, wid, NOW)
        monkeypatch.setattr(settings, "billing_price_id", "")
        with pytest.raises(HTTPException) as error:
            paid_work(db, wid, NOW)
        assert error.value.status_code == 503


def test_customer_billing_route_membership_csrf_and_revocation(
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import Generator
    from unittest.mock import Mock

    from app.api import customer_billing as api
    from app.api.customer import router as auth_router
    from app.billing.contracts import get_billing_transport
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.settings import settings
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(settings, "billing_price_id", POLICY.price_id)
    clock = Mock()
    clock.now.return_value = NOW
    monkeypatch.setattr(api, "datetime", clock)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    app.dependency_overrides[get_billing_transport] = lambda: FixtureBilling()
    owner, outsider = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    uid = login(owner, "owner:1")
    login(outsider, "outsider:1")
    with Session(customer_engine) as db:
        wid, _ = setup(db, "api")
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active"))
        db.commit()
    path = f"/api/customer/v1/workspaces/{wid}/billing"
    assert outsider.get(path).status_code == 404
    assert owner.get(path).json()["status"] == "unconfigured"
    assert owner.post(path + "/checkout").status_code == 403
    headers = {"Origin": ORIGIN, "X-CSRF-Token": owner.cookies[CSRF_COOKIE]}
    assert owner.post(path + "/checkout", headers=headers).status_code == 200
    with Session(customer_engine) as db:
        membership = db.get(CustomerMembership, (uid, wid))
        assert membership is not None
        membership.status = "suspended"
        db.commit()
    assert owner.get(path).status_code == 404


def test_periodic_refresh_observes_cancellation_without_new_webhook(
    customer_engine: Engine,
) -> None:
    from app.billing.dispatcher import run
    from sqlalchemy.orm import sessionmaker

    fixture = FixtureBilling()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "refresh")
        checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        body = payload("evt_refresh_initial")
        receive(db, body, signature(body), SECRET, NOW)
        reconcile(db, wid, "evt_refresh_initial", POLICY, fixture, NOW)
    fixture.state = fixture.state.model_copy(update={"status": "canceled"})
    factory = sessionmaker(customer_engine)
    later = NOW + timedelta(minutes=3)
    assert run(factory, POLICY, fixture, later)["refreshes"] == 1
    with factory() as db, pytest.raises(HTTPException, match="entitlement"):
        require_entitlement(db, wid, POLICY, later)
    fixture.fail = True
    future = later + timedelta(minutes=3)
    assert run(factory, POLICY, fixture, future)["failed"] == 1
    assert run(factory, POLICY, fixture, future)["failed"] == 0


def test_pending_event_backoff_precedes_batch_limit(customer_engine: Engine) -> None:
    from app.billing.dispatcher import run
    from sqlalchemy.orm import sessionmaker

    fixture = FixtureBilling()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "backoff")
        checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        body = payload("evt_backoff")
        receive(db, body, signature(body), SECRET, NOW)
    fixture.fail = True
    factory = sessionmaker(customer_engine)
    assert run(factory, POLICY, fixture, NOW, limit=1)["failed"] == 1
    assert run(factory, POLICY, fixture, NOW, limit=1)["failed"] == 0
    fixture.fail = False
    assert run(factory, POLICY, fixture, NOW + timedelta(minutes=1), limit=1)["events"] == 1


def test_management_route_enforces_owner_scope_and_csrf(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Generator

    from app.api import customer_billing as api
    from app.api.customer import router as auth_router
    from app.billing.contracts import get_billing_transport
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.settings import settings
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    class ManagedFixture(FixtureBilling):
        calls: list[str] = []

        def portal(
            self, customer_id: str, configuration_id: str, return_url: str, request_key: str
        ) -> str:
            assert configuration_id == "bpc_fixture"
            assert return_url == ORIGIN + "/app/settings"
            self.calls.append(customer_id)
            return "https://billing.stripe.com/session/fixture"

    fixture = ManagedFixture()
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(settings, "billing_portal_configuration", "bpc_fixture")
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    app.dependency_overrides[get_billing_transport] = lambda: fixture
    owner = TestClient(app, base_url=ORIGIN)
    member = TestClient(app, base_url=ORIGIN)
    outsider = TestClient(app, base_url=ORIGIN)
    uid, mid = login(owner, "owner:1"), login(member, "member:1")
    login(outsider, "outsider:1")
    with Session(customer_engine) as db:
        wid, _ = setup(db, "portal")
        db.add_all(
            [
                CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active"),
                CustomerMembership(user_id=mid, workspace_id=wid, role="viewer", status="active"),
                WorkspaceBilling(
                    workspace_id=wid, customer_request_key="fixture", customer_id="cus_owned"
                ),
            ]
        )
        db.commit()
    path = f"/api/customer/v1/workspaces/{wid}/billing/management"

    def headers(client: TestClient) -> dict[str, str]:
        return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}

    assert owner.post(path).status_code == 403
    assert member.post(path, headers=headers(member)).status_code == 403
    assert outsider.post(path, headers=headers(outsider)).status_code == 404
    assert fixture.calls == []
    result = owner.post(path, headers=headers(owner))
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert fixture.calls == ["cus_owned"]
    with Session(customer_engine) as db:
        membership = db.get(CustomerMembership, (uid, wid))
        assert membership is not None
        membership.status = "suspended"
        db.commit()
    assert owner.post(path, headers=headers(owner)).status_code == 404
    assert fixture.calls == ["cus_owned"]
