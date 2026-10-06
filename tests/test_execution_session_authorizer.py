import time
from dataclasses import replace
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
