"""Real mocked HTTP receipt and terminal commerce producer feed the owned adapter."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.api.customer_outcomes import router
from app.commerce.models import CommerceMeasurementPublication, CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers.models import CustomerUser
from app.lifecycle.privacy import workspace_export_revision
from app.outcomes import owned
from app.outcomes.models import ActionOutcomeAssessment
from app.outcomes.owned_contracts import AssessmentRequest
from app.publication import coordinator as coordinator
from app.publication.service import owner
from app.settings import Settings
from app.shopify.models import ShopifyConnection
from app.shopify.privacy import process_event
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW, FakeMeasurement, source
from tests.test_customer_identity import ISSUER, ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_provider_coordinator import GoogleServer, ready
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


def evidence(
    db: Session, config: Settings, path: Path
) -> tuple[int, str, AssessmentRequest, Any, Any]:
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON"))
    server = GoogleServer()
    wid, run_id, actor, media, runtime = ready(db, config, path, server)
    claim = coordinator.claim_creation_step(db, wid, run_id, actor, media, runtime, lambda: NOW)
    assert claim is not None
    coordinator.execute_claim(db, claim, actor, media, runtime, lambda: NOW)
    native = db.scalar(select(ShopifyConnection).where(ShopifyConnection.workspace_id == wid))
    assert native is not None
    store = db.get(CommerceStore, native.commerce_store_id)
    assert store is not None
    store.last_sync_at = None
    db.commit()
    result = CommerceSyncService(db, config, FakeMeasurement(config, [([source()], None)])).page(
        wid, now=NOW
    )
    assert result["status"] == "complete"
    publication = db.scalar(
        select(CommerceMeasurementPublication).where(
            CommerceMeasurementPublication.workspace_id == wid
        )
    )
    assert publication is not None
    body = AssessmentRequest(
        attempt_id=claim.attempt_id,
        publication_id=publication.id,
        before_start=date(2026, 9, 1),
        before_end=date(2026, 9, 15),
        after_start=date(2026, 9, 15),
        after_end=date(2026, 9, 29),
    )
    return wid, actor, body, runtime, server


def test_actual_owned_assessment_idempotency_latest_receipt_and_erasure(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, body, runtime, server = evidence(db, configuration, tmp_path)

        def authorize() -> None:
            owner(db, wid, actor)

        row = owned.create(db, wid, actor, body, authorize, lambda: NOW)
        db.commit()
        value = owned.read(db, wid, row.id, actor, authorize, lambda: NOW)
        report = value["assessment"]
        assert isinstance(report, dict)
        assert report["environment"] == "contract_test"
        assert report["status"] == "insufficient"
        assert report["before"]["value"] == "90000000"
        assert report["after"]["value"] == "0"
        assert {
            "maturity_policy_unavailable",
            "activation_unverified",
            "effective_time_unknown",
        } <= set(report["reasons"])
        assert report["causal_lift"] is None and report["spending_authority"] == "none"
        assert "resource_name" not in str(report) and "access_token" not in str(report)
        assert owned.create(db, wid, actor, body, authorize, lambda: NOW).id == row.id
        assert db.scalar(select(func.count()).select_from(ActionOutcomeAssessment)) == 1
        db.commit()
        server.absent = True
        coordinator.reconcile_attempt(
            db, wid, body.attempt_id, runtime, lambda: NOW + timedelta(seconds=1)
        )
        stale = owned.read(db, wid, row.id, actor, authorize, lambda: NOW + timedelta(seconds=2))
        assert stale["current"] is False and stale["current_reasons"] == ["receipt_superseded"]
        next_row = owned.create(db, wid, actor, body, authorize, lambda: NOW + timedelta(seconds=2))
        assert next_row.id != row.id and "effect_unverified" in next_row.assessment["reasons"]
        db.commit()
        identifier = row.id
        revision = workspace_export_revision(db, wid)
        process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
        assert db.scalar(select(func.count()).select_from(ActionOutcomeAssessment)) == 0
        assert workspace_export_revision(db, wid) > revision
        with pytest.raises(HTTPException) as error:
            owned.read(db, wid, identifier, actor, authorize, lambda: NOW)
        assert error.value.status_code == 404


def test_fresh_clock_auth_and_missing_coverage(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        clock = [NOW]

        def authorize() -> None:
            owner(db, wid, actor)
            clock[0] = NOW + timedelta(days=2)

        with pytest.raises(HTTPException) as error:
            owned.create(db, wid, actor, body, authorize, lambda: clock[0])
        assert (
            error.value.status_code == 404
        )  # expires during blocking authorization; entry time unused
        assert db.scalar(select(func.count()).select_from(ActionOutcomeAssessment)) == 0
        missing = body.model_copy(
            update={"before_start": date(2025, 1, 1), "before_end": date(2025, 1, 15)}
        )
        row = owned.create(db, wid, actor, missing, lambda: owner(db, wid, actor), lambda: NOW)
        assert row.assessment["before"]["value"] is None
        assert "measurement_coverage_incomplete" in row.assessment["reasons"]
        with pytest.raises(HTTPException):
            owned.create(db, wid + 100, actor, body, lambda: None, lambda: NOW)


def test_owned_api_csrf_scope_logout(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alice, bob, _ = replicas
    alice.app.include_router(router)  # type: ignore[attr-defined]
    bob.app.include_router(router)  # type: ignore[attr-defined]
    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer, user.subject = ISSUER, "outcome-owner"
        db.commit()
    login(alice, "outcome-owner:1")
    login(bob, "outcome-other:1")
    # Freeze only the measurement clock; identity/session expiry still uses fresh real time.
    monkeypatch.setattr(owned, "create", with_clock(owned.create))
    monkeypatch.setattr(owned, "read", with_clock(owned.read))
    path = f"/api/customer/v1/workspaces/{wid}/outcome-assessments"
    assert (
        alice.post(path, json=body.model_dump(mode="json"), headers={"Origin": ORIGIN}).status_code
        == 403
    )
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies.get("__Host-inlet_csrf") or ""}
    response = alice.post(path, json=body.model_dump(mode="json"), headers=headers)
    assert response.status_code == 201, response.text
    saved = path + "/" + response.json()["assessment_id"]
    assert alice.get(saved).status_code == 200
    assert bob.get(saved).status_code == 403
    assert alice.get(saved).headers["cache-control"] == "no-store"
    assert alice.delete("/api/customer/v1/session", headers=headers).status_code == 204
    assert alice.get(saved).status_code == 401


def with_clock(function: Any) -> Any:
    def call(*args: Any, **kwargs: Any) -> Any:
        return function(*args, **kwargs, clock=lambda: NOW)

    return call


def test_owned_report_tampering_and_fresh_authorization(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    from copy import deepcopy

    from app.commerce.evidence import digest

    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        row = owned.create(db, wid, actor, body, lambda: owner(db, wid, actor), lambda: NOW)
        db.commit()
        identifier = row.id
        original = deepcopy(row.assessment)
        altered = deepcopy(original)
        altered["before"]["source"]["workspace_id"] = wid + 1
        row.assessment, row.assessment_digest = altered, digest(altered)
        db.commit()
        with pytest.raises(HTTPException) as error:
            owned.read(db, wid, identifier, actor, lambda: None, lambda: NOW)
        assert error.value.status_code == 409
        row.assessment, row.assessment_digest = original, digest(original)
        db.commit()

        def revoked() -> None:
            raise HTTPException(401, "session revoked during lock wait")

        with pytest.raises(HTTPException) as error:
            owned.read(db, wid, identifier, actor, revoked, lambda: NOW)
        assert error.value.status_code == 401
        with pytest.raises(HTTPException) as error:
            owned.create(db, wid, actor, body, revoked, lambda: NOW)
        assert error.value.status_code == 401


def test_privacy_erasure_fences_waiting_replica(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    from app.commerce.evidence import lock_workspace
    from sqlalchemy import event

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency proof")
    with Session(customer_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        row = owned.create(db, wid, actor, body, lambda: None, lambda: NOW)
        identifier = row.id
        db.commit()
    waiting = Event()

    def before_query(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if (
            current_thread().name.startswith("assessment-replica")
            and "workspaces" in statement
            and "FOR UPDATE" in statement
        ):
            waiting.set()

    def read_replica() -> int:
        with Session(customer_engine) as replica:
            try:
                owned.read(replica, wid, identifier, actor, lambda: None, lambda: NOW)
            except HTTPException as error:
                return error.status_code
            return 200

    event.listen(customer_engine, "before_cursor_execute", before_query)
    try:
        with Session(customer_engine) as eraser:
            lock_workspace(eraser, wid)
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="assessment-replica") as pool:
                pending = pool.submit(read_replica)
                try:
                    assert waiting.wait(5), "replica must reach the shared workspace fence"
                    assert not pending.done()
                    process_event(eraser, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
                    eraser.commit()
                finally:
                    eraser.rollback()  # Release the fence even if the harness assertion fails.
                assert pending.result(timeout=10) == 404
    finally:
        event.remove(customer_engine, "before_cursor_execute", before_query)
