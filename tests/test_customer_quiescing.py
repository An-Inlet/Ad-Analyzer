"""Atomic local closure fence and append-only late evidence; no live transports."""

import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from app.billing.dispatcher import run
from app.billing.models import BillingEvent, WorkspaceBilling
from app.billing.scope import LEGACY_TEST_SCOPE
from app.customers.access import CustomerPrincipal, customer_workspace
from app.customers.models import CustomerSession, CustomerUser
from app.google_connections.models import GoogleAuthorization, GoogleCustomerConnection
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.models import LifecycleRequest
from app.lifecycle.quiescing import preview_digest, quiesce
from app.lifecycle.service import begin, claim_inventory, finish_inventory
from app.mandates.service import workspace_lock
from app.publication import service as publication
from app.publication.models import PublicationReceiptRecord, PublicationStepRecord
from app.settings import Settings
from app.workspaces.models import Workspace
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.late_publication_retained_fixture import load_source, retained_late_publication
from tests.test_customer_billing import POLICY, FixtureBilling
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import KEY, NOW, seed
from tests.test_shopify_sales import configuration as configuration


def confirmed(
    db: Session, principal: CustomerPrincipal, wid: int, now: datetime = NOW
) -> tuple[str, str]:
    request = begin(
        db,
        principal,
        FakeProvider(),
        LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="close"),
        KEY,
        now,
    )
    db.commit()
    _, fence = claim_inventory(db, wid, request.id, 1, now)
    db.commit()
    evidence = preview_digest(db, wid)
    finish_inventory(db, wid, request.id, 1, fence, evidence, now)
    db.commit()
    return request.id, evidence


def test_quiesce_is_atomic_and_preserves_other_workspace_and_global_session(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        foreign, other = seed(db, "two")
        request, evidence = confirmed(db, principal, wid)
        with pytest.raises(HTTPException):
            quiesce(db, principal, FakeProvider(), wid, request, 1, "0" * 64, NOW)
        db.rollback()
        quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, NOW)
        db.rollback()
        assert db.get(Workspace, wid).status == "active"  # type: ignore[union-attr]
        row = quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, NOW)
        db.commit()
        assert row.state == "blocked" and row.revision == 2 and row.disposition_policy is None
        assert quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, NOW).id == request
        db.commit()
        assert principal.session.revoked_at is None and foreign.session.revoked_at is None
        assert customer_workspace(db, foreign.user.id, other)[0].status == "active"
        with pytest.raises(HTTPException):
            customer_workspace(db, principal.user.id, wid)
        with pytest.raises(HTTPException):
            workspace_lock(db, wid)


def test_stale_workspace_identity_map_cannot_reopen_product_work(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        _, wid = seed(db)
    with Session(customer_engine) as stale:
        cached = stale.get(Workspace, wid)
        assert cached is not None and cached.status == "active"
        with Session(customer_engine) as other:
            row = other.get(Workspace, wid)
            assert row is not None
            row.status = "closing"
            other.commit()
        with pytest.raises(HTTPException):
            workspace_lock(stale, wid)


def test_late_billing_notice_is_retained_without_provider_or_entitlement(
    customer_engine: Engine,
) -> None:
    class NoCalls(FixtureBilling):
        def subscription(self, customer_id: str, subscription_id: str):  # type: ignore[no-untyped-def]
            raise AssertionError("no provider calls for closing scope")

    with Session(customer_engine) as db:
        principal, wid = seed(db)
        db.add(
            WorkspaceBilling(
                workspace_id=wid,
                customer_id="cus_fixture",
                subscription_id="sub_fixture",
                customer_request_key="synthetic",
                status="active",
            )
        )
        db.commit()
        request, evidence = confirmed(db, principal, wid)
        quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, NOW)
        db.commit()
        db.add(
            BillingEvent(
                id="evt_late",
                body_hash="a" * 64,
                customer_id="cus_fixture",
                subscription_id="sub_fixture",
                event_type="customer.subscription.updated",
                state="pending",
                received_at=NOW,
            )
        )
        db.commit()
    assert run(lambda: Session(customer_engine), POLICY, NoCalls(), NOW) == {
        "events": 0,
        "refreshes": 0,
        "failed": 0,
    }
    with Session(customer_engine) as db:
        event = db.get(BillingEvent, LEGACY_TEST_SCOPE.key("evt_late"))
        assert event is not None and event.state == "closure_pending" and event.processed_at is None
        assert db.get(Workspace, wid).status == "closing"  # type: ignore[union-attr]


@pytest.mark.planning_boundary
def test_late_publication_receipt_is_strict_evidence_only(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    from app.campaign_review.storage import LocalMediaStore

    from tests.test_commerce_measurement import NOW as publication_now

    with (
        retained_late_publication(customer_engine, tmp_path / "original") as (engine, ids),
        Session(engine) as db,
    ):
        pid, wid, actor = ids.plan_id, ids.workspace_id, ids.actor_id
        bound = load_source(db, ids)
        receipt = ids.late_receipt
        authority = publication.DatabaseFixtureAuthority(
            LocalMediaStore(tmp_path / "original" / "media")
        )
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer = FakeProvider.issuer
        session = CustomerSession(
            digest=uuid4().hex * 2,
            user_id=actor,
            csrf_digest="a" * 64,
            created_at=int(time.time()),
            expires_at=int(time.time()) + 3600,
            authenticated_at=int(time.time()),
        )
        db.add(session)
        db.commit()
        principal = CustomerPrincipal(user, session)
        request, evidence = confirmed(db, principal, wid, publication_now)
        quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, publication_now)
        db.commit()
        grant = db.scalar(
            select(GoogleCustomerConnection).where(GoogleCustomerConnection.workspace_id == wid)
        )
        assert (
            grant is not None and grant.encrypted_grant is None and grant.status == "disconnected"
        )
        publication.record_receipt(db, wid, pid, receipt, publication_now)
        publication.record_receipt(db, wid, pid, receipt, publication_now)
        assert db.scalar(select(func.count()).select_from(PublicationReceiptRecord)) == 2
        step = db.get(PublicationStepRecord, (pid, bound.step.step_id))
        assert step is not None and step.state == "dispatching"  # no false settlement/restart
        with pytest.raises(HTTPException):
            publication.record_receipt(
                db, wid, pid, receipt.model_copy(update={"fence": "0" * 32}), publication_now
            )
        db.rollback()
        with pytest.raises(HTTPException, match="conflicting closure receipt"):
            publication.record_receipt(
                db,
                wid,
                pid,
                receipt.model_copy(update={"resource_id": "other-resource"}),
                publication_now,
            )
        db.rollback()
        with pytest.raises(HTTPException) as denied:
            publication.claim_next(
                db, wid, pid, "publication-one", actor, authority, publication_now
            )
        from app.advertising_capabilities import AdvertisingWritesDisabled

        assert isinstance(denied.value, AdvertisingWritesDisabled)
        assert denied.value.status_code == 409
        assert denied.value.detail == "advertising_writes_disabled_in_planning_mvp"
        closure = db.get(LifecycleRequest, request)
        assert closure is not None and closure.state == "blocked"
        assert any(b["code"] == "publication_unresolved" for b in closure.blockers)


def test_removed_authorization_cannot_restore_grant_after_exchange(customer_engine: Engine) -> None:
    from datetime import timedelta

    from app.google_connections import service as google
    from app.google_connections.security import digest

    with Session(customer_engine) as db:
        principal, wid = seed(db)
        nonce = "synthetic-nonce"
        db.add(
            GoogleAuthorization(
                digest=digest(nonce),
                workspace_id=wid,
                session_digest=principal.session.digest,
                expires_at=NOW + timedelta(hours=1),
                state="exchanging",
            )
        )
        db.commit()
        request, evidence = confirmed(db, principal, wid)
        quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, NOW)
        db.commit()
        with pytest.raises(HTTPException):
            google.authorization(db, nonce, principal.session.digest, NOW)
        assert db.scalar(select(func.count()).select_from(GoogleAuthorization)) == 0


def test_actual_exchange_return_cannot_resurrect_closed_grant(
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta
    from unittest.mock import MagicMock

    from app.google_connections import service as google
    from app.google_connections.security import digest

    with Session(customer_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
        nonce = "paused-exchange"
        db.add(
            GoogleAuthorization(
                digest=digest(nonce),
                workspace_id=wid,
                session_digest=sid,
                expires_at=NOW + timedelta(hours=1),
                state="pending",
            )
        )
        db.commit()
        request_id, evidence = confirmed(db, principal, wid)

        def exchange(*args: object) -> object:
            with Session(customer_engine) as closing:
                user, session = closing.get(CustomerUser, uid), closing.get(CustomerSession, sid)
                assert user is not None and session is not None
                quiesce(
                    closing,
                    CustomerPrincipal(user, session),
                    FakeProvider(),
                    wid,
                    request_id,
                    1,
                    evidence,
                    NOW,
                )
                closing.commit()
            return MagicMock()

        transport = MagicMock()
        transport.exchange.side_effect = exchange
        monkeypatch.setattr(google, "ready", lambda transport: None)
        monkeypatch.setattr(google, "redirect_uri", lambda: "https://inlet.example/callback")
        with pytest.raises(HTTPException):
            google.finish(db, nonce, sid, "fixture-code", NOW, transport)
        transport.exchange.assert_called_once()
        db.rollback()
        assert db.scalar(select(func.count()).select_from(GoogleAuthorization)) == 0
        assert db.get(Workspace, wid).status == "closing"  # type: ignore[union-attr]


def test_customer_api_preview_confirm_replay_status_and_session_isolation(
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import Generator

    from app.api.customer import router as customer_router
    from app.api.customer_lifecycle import router as lifecycle_router
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.settings import settings
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, login

    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(lifecycle_router)
    provider = FakeProvider()

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: provider
    client, other_client = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    uid = login(client, "owner:1")
    login(other_client, "other:1")
    with Session(customer_engine) as db:
        workspaces = []
        for slug in ["closing-workspace", "surviving-workspace"]:
            workspace = Workspace(slug=slug, name=slug, client_name=slug, status="active")
            db.add(workspace)
            db.flush()
            db.add(
                CustomerMembership(
                    user_id=uid, workspace_id=workspace.id, role="owner", status="active"
                )
            )
            workspaces.append(workspace.id)
        db.commit()
    wid, surviving = workspaces
    url = f"/api/customer/v1/workspaces/{wid}"
    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": client.cookies[CSRF_COOKIE],
        "Idempotency-Key": KEY,
    }
    assert client.post(url + "/closure-preview", json={}).status_code == 403
    preview = client.post(url + "/closure-preview", headers=headers, json={})
    assert preview.status_code == 200, preview.text
    data = preview.json()
    replay = client.post(url + "/closure-preview", headers=headers, json={})
    assert replay.status_code == 200 and replay.json()["request_id"] == data["request_id"]
    close_url = url + "/closures/" + data["request_id"]
    body = {
        "expected_revision": data["revision"],
        "inventory_digest": data["inventory_digest"],
        "confirm_workspace_id": wid,
    }
    closed = client.post(close_url + "/confirm", headers=headers, json=body)
    assert closed.status_code == 200, closed.text
    assert closed.json()["state"] == "blocked" and closed.json()["closed"] is False
    assert client.post(close_url + "/confirm", headers=headers, json=body).status_code == 200
    assert (
        client.post(close_url + "/reconcile-local", json={"expected_revision": 2}).status_code
        == 403
    )
    local = client.post(
        close_url + "/reconcile-local", headers=headers, json={"expected_revision": 2}
    )
    assert local.status_code == 200, local.text
    assert local.json()["revision"] == 3
    assert local.json()["local_work"]["local_records_drained"] is True
    assert local.json()["local_work"]["physical_workers_stopped"] is None
    assert local.json()["closed"] is False
    assert (
        client.post(
            close_url + "/reconcile-local", headers=headers, json={"expected_revision": 2}
        ).status_code
        == 409
    )
    assert client.get(close_url).json()["local_work"]["observation_kind"] == "current_only"
    assert client.get(url).status_code == 404
    assert client.get(f"/api/customer/v1/workspaces/{surviving}").status_code == 200
    assert client.get("/api/customer/v1/session").status_code == 200
    assert other_client.get(close_url).status_code == 404
    foreign_headers = {"Origin": ORIGIN, "X-CSRF-Token": other_client.cookies[CSRF_COOKIE]}
    assert (
        other_client.post(
            close_url + "/reconcile-local", headers=foreign_headers, json={"expected_revision": 3}
        ).status_code
        == 404
    )
    assert (
        client.post(
            close_url + "/reconcile-local",
            headers=headers,
            json={"expected_revision": 3, "purge": True},
        ).status_code
        == 422
    )
    assert client.delete("/api/customer/v1/session", headers=headers).status_code == 204
    assert client.get(close_url).status_code == 401
    assert (
        client.post(
            close_url + "/reconcile-local", headers=headers, json={"expected_revision": 3}
        ).status_code
        == 401
    )
