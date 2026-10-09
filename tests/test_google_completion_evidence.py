"""Actual original HTTP capture, durable scope, lifecycle and shared-byte compatibility."""

import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from app.lifecycle.export_serializers import serialize
from app.lifecycle.registry import TABLES
from app.publication import optimization as o
from app.publication.execution_models import GoogleOriginalCompletion, ProviderExposureReservation
from app.publication.google_completion import read_owned
from app.publication.google_completion_contracts import GoogleCapturedResponse
from app.publication.optimization_contracts import OptimizationResponse
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_google_optimization_http import setup
from tests.test_shopify_sales import configuration as configuration


def emitted(db: Session, configuration: Settings, tmp_path: Path):  # type: ignore[no-untyped-def]
    wid, actor, binding, scope, target, action, runtime, server = ready(
        db, configuration, tmp_path, "google_ads"
    )
    review = o.prepare_optimization(
        db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
    )
    o.approve_optimization(
        db, wid, review.id, review.digest, review.plan_digest, actor, runtime, lambda: NOW
    )
    run = o.create_run(db, wid, review.id, actor, runtime, lambda: NOW)
    claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
    assert claim is not None
    receipt = o.execute_claim(db, claim, actor, runtime, lambda: NOW)
    assert receipt.outcome == "verified_target_state"
    return wid, actor, claim.attempt_id


@pytest.mark.parametrize("kind", ["budget", "pause"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_actual_capture_preserves_normalized_bytes(kind: str) -> None:
    adapter, _, request, ctx = setup(kind)
    response = adapter.apply_once(request, ctx, request.dispatched_at)
    assert isinstance(response, GoogleCapturedResponse)
    response.capture.bind(request)
    assert response.capture.assertion == "original_configuration_operation_completed"
    legacy = OptimizationResponse(request_digest=request.digest(), outcome="acknowledged")
    assert response.model_dump_json() == legacy.model_dump_json()
    assert "access_token" not in response.capture.model_dump_json()


@pytest.mark.parametrize("mode", ["timeout", "foreign", "partial_error", "async", "empty", "extra"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_no_capture_for_nonexact_original_success(mode: str) -> None:
    adapter, server, request, ctx = setup()

    def wire(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        response = server(req)
        if req.url.path.endswith(":mutate") and not data.get("validateOnly"):
            if mode == "timeout":
                raise httpx.ReadTimeout("private")
            result = response.json()
            if mode == "foreign":
                result["results"][0]["resourceName"] = "customers/9999999999/campaignBudgets/9"
            elif mode == "partial_error":
                result["partialFailureError"] = {"code": 1, "message": "private"}
            elif mode == "async":
                result = {"name": "operations/private", "done": False}
            elif mode == "empty":
                result = {}
            else:
                result["unreviewed"] = "private"
            return httpx.Response(200, json=result)
        return response

    adapter.transport = httpx.MockTransport(wire)
    response = adapter.apply_once(request, ctx, request.dispatched_at)
    assert response.outcome == "unknown"
    assert not isinstance(response, GoogleCapturedResponse)
    assert "private" not in response.model_dump_json()


@pytest.mark.parametrize("tamper", [None, "document", "fence", "request", "digest", "scope"])
def test_durable_reader_and_export_never_release_hold(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    tamper: str | None,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, attempt = emitted(db, configuration, tmp_path)
        row = db.get(GoogleOriginalCompletion, attempt)
        assert row is not None
        assert TABLES[row.__tablename__].protected
        exported = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        projected, missing = serialize(row.__tablename__, exported)
        assert not missing and projected["document"] == row.document
        bad = deepcopy(exported)
        bad["document"]["raw_provider_body"] = {"secret": "private"}
        projected, missing = serialize(row.__tablename__, bad)
        assert "document" in missing and "document" not in projected
        before = [
            (r.id, r.state, r.amount_micros)
            for r in db.scalars(select(ProviderExposureReservation))
        ]
        document = read_owned(db, wid, attempt, actor, NOW)
        assert document is not None
        assert document.capture.attempt_id == attempt
        assert "closed_requests" not in document.model_dump()
        from app.publication.google_execution_completion import read_execution_completion
        from app.publication.service import owner

        view = read_execution_completion(
            db, wid, attempt, actor, authorize=lambda: owner(db, wid, actor), clock=lambda: NOW
        )
        assert view.status == "completed" and view.commitment == document.digest()
        assert view.purpose == "existing_campaign_optimize"
        assert view.financial_finality == "unavailable"
        db.rollback()
        with pytest.raises(HTTPException):
            read_owned(db, wid + 1000, attempt, actor, NOW)
        db.rollback()
        with pytest.raises(HTTPException):
            read_owned(db, wid, attempt, "foreign-user", NOW)
        db.rollback()
        row = db.get(GoogleOriginalCompletion, attempt)
        assert row is not None
        if tamper == "document":
            raw = deepcopy(row.document)
            raw["capture"]["operation_digest"] = "f" * 64
            row.document = raw
        elif tamper == "fence":
            row.fence = "f" * 32
        elif tamper == "request":
            row.request_digest = "f" * 64
        elif tamper == "digest":
            row.digest = "f" * 64
        elif tamper == "scope":
            # Scoped FK is independently checked in migration/native restore tests.
            raw = deepcopy(row.document)
            raw["capture"]["account"]["workspace_id"] += 1000
            row.document = raw
        if tamper:
            db.commit()
            with pytest.raises(HTTPException, match="evidence changed"):
                read_owned(db, wid, attempt, actor, NOW)
            db.rollback()
        else:
            # Idempotent original capture retains original timestamp rather than replacing it.
            _, _, _, request = o.evidence_lock(db, wid, attempt)
            o.record_response(
                db,
                wid,
                attempt,
                GoogleCapturedResponse(
                    request_digest=request.digest(),
                    outcome="acknowledged",
                    capture=document.capture,
                ),
                lambda: NOW + timedelta(seconds=1),
            )
            assert read_owned(db, wid, attempt, actor, NOW + timedelta(seconds=1)) == document
        assert [
            (r.id, r.state, r.amount_micros)
            for r in db.scalars(select(ProviderExposureReservation))
        ] == before


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_legacy_acknowledgment_cannot_manufacture_capture(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, _ = ready(
            db, configuration, tmp_path, "google_ads"
        )
        review = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, review.id, review.digest, review.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, review.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        _, _, _, request = o.evidence_lock(db, wid, claim.attempt_id)
        for outcome in ("unknown", "acknowledged"):
            o.record_response(
                db,
                wid,
                claim.attempt_id,
                OptimizationResponse.model_validate(
                    dict(request_digest=request.digest(), outcome=outcome)
                ),
                lambda: NOW,
            )
            assert read_owned(db, wid, claim.attempt_id, actor, NOW) is None


def test_customer_closure_retains_original_completion_and_financial_hold(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    import time
    from uuid import uuid4

    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerSession, CustomerUser
    from app.lifecycle.contracts import LifecycleScopeV1
    from app.lifecycle.inventory import inventory
    from app.lifecycle.quiescing import quiesce

    from tests.test_customer_identity import FakeProvider
    from tests.test_customer_quiescing import confirmed

    with Session(customer_engine) as db:
        wid, actor, attempt = emitted(db, configuration, tmp_path)
        row = db.get(GoogleOriginalCompletion, attempt)
        assert row is not None
        original = deepcopy(row.document)
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer = FakeProvider.issuer
        session = CustomerSession(
            digest=uuid4().hex * 2,
            user_id=actor,
            csrf_digest="f" * 64,
            created_at=int(time.time()),
            expires_at=int(time.time()) + 3600,
            authenticated_at=int(time.time()),
        )
        db.add(session)
        db.commit()
        principal = CustomerPrincipal(user, session)
        request, digest = confirmed(db, principal, wid, NOW)
        quiesce(db, principal, FakeProvider(), wid, request, 1, digest, NOW)
        db.commit()
        db.refresh(row)
        assert row.document == original
        assert all(r.state == "held" for r in db.scalars(select(ProviderExposureReservation)))
        manifest = inventory(db, LifecycleScopeV1(workspace_id=wid))
        section = next(
            s for s in manifest["sections"] if s["table"] == "google_original_completions"
        )
        assert section["protected"] is True and section["count"] == 1
        assert any(b["subsystem"] == "provider_exposure_reservations" for b in manifest["blockers"])
