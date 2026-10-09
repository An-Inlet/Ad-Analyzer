import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.models import CustomerSession, CustomerUser
from app.publication import coordinator as c
from app.publication import optimization as o
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
from app.publication.service import owner
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready as optimization_ready
from tests.test_provider_coordinator import GoogleServer, ready
from tests.test_shopify_sales import configuration as configuration


def guard(db: Session, actor: str) -> tuple[ExecutionAuthorizer, str]:
    user = db.get(CustomerUser, actor)
    assert user is not None
    token = uuid4().hex * 2
    now = int(time.time())
    row = CustomerSession(
        digest=token,
        user_id=actor,
        csrf_digest="c" * 64,
        created_at=now,
        expires_at=now + 3600,
        authenticated_at=now,
    )
    db.add(row)
    db.commit()
    principal = CustomerPrincipal(user=user, session=row)
    provider = FakeProvider()
    provider.issuer = user.issuer

    def authorize(session: Session, workspace_id: int, current_actor: str) -> None:
        if current_actor != actor:
            raise HTTPException(403, "principal actor mismatch")
        lock_customer_mutation(session, principal, workspace_id, provider)
        owner(session, workspace_id, actor)

    return authorize, token


def revoke(engine: Engine, digest: str) -> None:
    with Session(engine) as other:
        row = other.get(CustomerSession, digest)
        assert row is not None
        row.revoked_at = int(time.time())
        other.commit()


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_session_revoked_during_creation_qualification_cannot_persist_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, GoogleServer())
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None
        row = db.get(ProviderExecutionReview, run.review_id)
        assert row is not None
        document = CreationExecutionReview.model_validate(row.document)
        authorize, token = guard(db, actor)
        read = runtime.qualification_reader

        def qualify(*args, **kwargs):  # type: ignore[no-untyped-def]
            value = read(*args, **kwargs)
            revoke(customer_engine, token)
            return value

        runtime = replace(runtime, authorize=authorize, qualification_reader=qualify)
        with pytest.raises(HTTPException) as denied:
            c.prepare_creation(
                db, wid, document.plan, document.mandate, actor, store, runtime, lambda: NOW
            )
        assert denied.value.status_code == 401


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_session_revoked_during_optimization_preflight_cannot_emit(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, server = optimization_ready(
            db, configuration, tmp_path, "meta_ads"
        )
        authorize, token = guard(db, actor)
        runtime = replace(runtime, authorize=authorize)
        row = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        adapter = runtime.transport(scope)
        read = adapter.read_current

        def preflight(*args, **kwargs):  # type: ignore[no-untyped-def]
            state = read(*args, **kwargs)
            revoke(customer_engine, token)
            return state

        monkeypatch.setattr(adapter, "read_current", preflight)
        with pytest.raises(HTTPException) as denied:
            o.execute_claim(db, claim, actor, runtime, lambda: NOW)
        assert denied.value.status_code == 401 and server.posts == []


@pytest.mark.parametrize("interruption", ["revoke", "expire"])
@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_revocation_in_final_optimization_context_blocks_emission(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    provider: str,
    interruption: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, server = optimization_ready(
            db, configuration, tmp_path, provider
        )
        authorize, token = guard(db, actor)
        runtime = replace(runtime, authorize=authorize)
        row = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        context = runtime.context
        calls = 0
        now = NOW

        def resolve(scope):  # type: ignore[no-untyped-def]
            nonlocal calls, now
            calls += 1
            result = context(scope)
            if calls == 3:  # read-current, validate-only, then emission credential lookup
                if interruption == "revoke":
                    revoke(customer_engine, token)
                else:
                    now += timedelta(minutes=10)
            return result

        runtime = replace(runtime, context=resolve)
        with pytest.raises(HTTPException) as denied:
            o.execute_claim(db, claim, actor, runtime, lambda: now)
        assert denied.value.status_code == (401 if interruption == "revoke" else 409)
        assert (server.writes if provider == "google_ads" else server.posts) == []


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_revocation_in_creation_context_blocks_emission(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        server = GoogleServer()
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        authorize, token = guard(db, actor)
        runtime = replace(runtime, authorize=authorize)
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        context = runtime.google_context

        def resolve(request):  # type: ignore[no-untyped-def]
            result = context(request)
            revoke(customer_engine, token)
            return result

        runtime = replace(runtime, google_context=resolve)
        # Reject forged claim lineage before resolving any credentials.
        with pytest.raises(HTTPException) as forged:
            c.execute_claim(
                db,
                claim.model_copy(update={"attempt_id": "f" * 32}),
                actor,
                store,
                runtime,
                lambda: NOW,
            )
        assert forged.value.status_code == 409
        db.rollback()
        with pytest.raises(HTTPException) as denied:
            c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        assert denied.value.status_code == 401 and server.posts == 0


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_revocation_in_final_activation_context_blocks_emission(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.publication import activation as a
    from app.publication import activation_review as r

    from tests.test_activation_coordinator import runtime_for
    from tests.test_activation_review import activation_ready
    from tests.test_google_activation import Server

    with Session(customer_engine) as db:
        server = Server()
        wid, parent, actor, store, review, binding = activation_ready(
            db, configuration, tmp_path, server
        )
        row = r.prepare_activation(db, wid, parent, binding, actor, store, review, lambda: NOW)
        r.approve_activation(
            db, wid, row.id, row.digest, row.plan_digest, actor, store, review, lambda: NOW
        )
        run = r.create_run(db, wid, row.id, actor, store, review, lambda: NOW)
        authorize, token = guard(db, actor)
        review = replace(review, creation=replace(review.creation, authorize=authorize))
        runtime = runtime_for(review, server)
        claim = a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        preflight = a.preflight_graph
        context = runtime.context
        completed = False

        def checked(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal completed
            preflight(*args, **kwargs)
            completed = True

        def resolve(request):  # type: ignore[no-untyped-def]
            result = context(request)
            if completed:
                revoke(customer_engine, token)
            return result

        monkeypatch.setattr(a, "preflight_graph", checked)
        runtime = replace(runtime, context=resolve)
        count = server.activations
        with pytest.raises(HTTPException) as denied:
            a.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        assert denied.value.status_code == 401 and server.activations == count
