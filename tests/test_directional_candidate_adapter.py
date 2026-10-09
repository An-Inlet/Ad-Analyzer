"""Actual queued native reads→authorized directional transform→owned stable epoch.

Qualification, calibration and effective-time facts remain explicit contract fixtures.
"""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from app.directional_feedback.adapter import SCHEMA, DirectionalCandidateAdapter
from app.executors.google_optimization import GoogleOptimizationTransport
from app.optimization_candidates import service as candidates
from app.optimization_candidates.contracts import (
    CandidateDecision,
    CandidateEvidence,
    CandidateObservation,
)
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.outcome_feedback.models import ContributionSlot
from app.publication.optimization_contracts import OptimizationContext
from app.settings import Settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from tests import test_feedback_snapshot as fixture_source
from tests.feedback_snapshot_retained_fixture import (
    snapshot_receipt_source as snapshot_receipt_source,
)
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_directional_feedback import assembly
from tests.test_shopify_sales import configuration as configuration


def prepared(
    db: Session, configuration: Settings, path: Path, monkeypatch: pytest.MonkeyPatch
) -> Any:
    from app.publication import optimization
    from app.publication.optimization_contracts import GoogleBudgetSetV1, GoogleCurrentState

    from tests.test_google_optimization_http import BUDGET, CAMPAIGN, Server

    native: list[Server] = []
    original = cast(Any, fixture_source).fixture

    def capture(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        assert isinstance(result, tuple) and len(result) == 6
        principal, work, observation, _, _, server = result
        assert isinstance(server, Server) and not server.writes
        assert isinstance(observation.state, GoogleCurrentState)
        assert observation.state.budget_amount_micros == 50_000_000
        assert server.budget["amountMicros"] == "50000000"
        scope = work.scope
        assert scope.source.attempt_id and scope.source.receipt_id
        _, _, attempt, request = optimization.evidence_lock(
            db, scope.account.workspace_id, scope.source.attempt_id
        )
        receipt = optimization.read_owned_outcome_receipt(
            db, scope.account.workspace_id, attempt.id, principal.user.id
        )
        assert receipt and receipt.receipt_id == scope.source.receipt_id
        assert receipt.sequence == 1 and receipt.outcome == "verified_target_state"
        assert request.intent.scope == scope.account and receipt.account == scope.account
        assert request.intent.target == scope.target
        assert scope.target.kind == "campaign" and scope.target.external_id == "5"
        assert isinstance(request.intent.action, GoogleBudgetSetV1)
        assert request.intent.action.amount_micros == 45_000_000
        assert isinstance(request.before, GoogleCurrentState)
        assert request.before.budget_amount_micros == 50_000_000
        assert request.before.native_budget_resource == observation.state.native_budget_resource
        assert observation.state.native_budget_resource == server.budget["resourceName"] == BUDGET
        assert server.campaign["resourceName"] == CAMPAIGN
        server.budget["amountMicros"] = str(request.intent.action.amount_micros)
        assert observation.state.budget_amount_micros == 50_000_000 and not server.writes
        native.append(server)
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(fixture_source, "fixture", capture)
        principal, work, _, policy, profile, runtime, now, slot, _ = assembly(
            db, configuration, path, monkeypatch
        )
    assert len(native) == 1
    template = runtime.candidate.reader(db, work.scope, now)
    server = native[0]
    assert template.state.budget_amount_micros == 50_000_000
    assert server.budget["amountMicros"] == "45000000" and not server.writes
    transport = GoogleOptimizationTransport(transport=httpx.MockTransport(server))
    numeric = work.policy.model_copy(update={"minimum_observations": 2})
    work = work.model_copy(update={"policy": numeric})
    policy = policy.model_copy(update={"candidate_policy_digest": numeric.digest()})
    profile = profile.model_copy(update={"policy_digest": policy.policy_digest})
    clock = [now]

    def read(session: Session, scope: Any, at: Any) -> CandidateObservation:
        state = transport.read_current(
            scope.account,
            scope.target,
            template.state.money,
            template.state.qualification_id,
            template.state.qualification_revision,
            OptimizationContext(
                scope=scope.account,
                access_token=SecretStr("offline-token"),
                expires_at=at + timedelta(hours=1),
            ),
            at,
        )
        return CandidateObservation(
            scope=scope,
            state=state,
            evidence=CandidateEvidence(
                scope_digest=scope.digest(),
                source_schema="test.native_unqualified.v1",
                source_digest="a" * 64,
                source_reference=scope.source.publication_id,
                qualification="unqualified",
                direction="none",
                observation_count=None,
                observed_at=at,
                expires_at=at + timedelta(minutes=1),
            ),
        )

    candidate = replace(
        runtime.candidate, reader=read, policy_reader=lambda *_: numeric, clock=lambda: clock[0]
    )
    runtime = replace(
        runtime, candidate=candidate, policies=lambda _: policy, qualifications=lambda _: profile
    )
    adapter = DirectionalCandidateAdapter(runtime, policy.family)
    return principal, work, policy, profile, adapter, clock, slot, server


def run(db: Session, principal: Any, work: Any, adapter: DirectionalCandidateAdapter) -> Any:
    bound = adapter.bind()
    row = candidates.enqueue(db, principal, work, bound)
    job_id, wid = row.id, row.workspace_id
    db.commit()
    assert candidates.process(cast(Engine, db.get_bind()), wid, job_id, bound) == "completed"
    result = db.scalar(select(CandidateResult).where(CandidateResult.job_id == job_id))
    assert result
    decision = candidates.read_result(db, wid, result.id, principal, bound, erase_invalid=False)
    assert isinstance(decision, CandidateDecision)
    assert decision.status == "suggested" and decision.evidence.source_schema == SCHEMA
    assert decision.evidence.observation_count == 2
    return decision


@pytest.mark.planning_boundary
def test_real_queue_and_authorized_epoch_cannot_reset_on_policy_refresh(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    with Session(customer_engine) as db:
        principal, work, policy, profile, adapter, clock, _, server = prepared(
            db, configuration, tmp_path, monkeypatch
        )
        writes_before = len(server.writes)
        decision = run(db, principal, work, adapter)
        producer = adapter.epoch_producer()
        assert producer and producer.authorized_read and producer.read is None
        epoch = producer.authorized_read(db, principal, decision)
        clock[0] += timedelta(seconds=1)
        assert producer.authorized_read(db, principal, decision) == epoch
        db.commit()
        # New registered numeric/calibration/profile revision cannot mint a new
        # original-action opportunity even though the candidate audit changes.
        numeric = work.policy.model_copy(update={"revision": 2})
        changed_work = work.model_copy(update={"policy": numeric})
        changed_policy = policy.model_copy(
            update={
                "revision": 2,
                "candidate_policy_digest": numeric.digest(),
                "calibration_digest": "9" * 64,
            }
        )
        changed_profile = profile.model_copy(
            update={
                "revision": 2,
                "policy_digest": changed_policy.policy_digest,
                "calibration_digest": changed_policy.calibration_digest,
            }
        )
        changed_runtime = replace(
            adapter.runtime,
            candidate=replace(adapter.runtime.candidate, policy_reader=lambda *_: numeric),
            policies=lambda _: changed_policy,
            qualifications=lambda _: changed_profile,
        )
        changed_adapter = DirectionalCandidateAdapter(changed_runtime, policy.family)
        next_decision = run(db, principal, changed_work, changed_adapter)
        next_producer = changed_adapter.epoch_producer()
        assert next_producer and next_producer.authorized_read
        assert next_producer.authorized_read(db, principal, next_decision) == epoch
        assert next_decision.evidence.source_digest != decision.evidence.source_digest
        assert len(server.writes) == writes_before


@pytest.mark.planning_boundary
def test_committed_retraction_after_native_io_cannot_publish_candidate(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    with Session(customer_engine) as db:
        principal, work, _, _, adapter, _, slot, server = prepared(
            db, configuration, tmp_path, monkeypatch
        )
        original = adapter.runtime.candidate.reader

        def retract(session: Session, scope: Any, now: Any) -> CandidateObservation:
            observed = original(session, scope, now)
            with Session(customer_engine) as other:
                other.execute(delete(ContributionSlot).where(ContributionSlot.id == slot))
                other.commit()
            return cast(CandidateObservation, observed)

        runtime = replace(
            adapter.runtime, candidate=replace(adapter.runtime.candidate, reader=retract)
        )
        bound = DirectionalCandidateAdapter(runtime, adapter.policy_family).bind()
        row = candidates.enqueue(db, principal, work, bound)
        identifier, wid = row.id, row.workspace_id
        db.commit()
        writes_before = len(server.writes)
        assert candidates.process(customer_engine, wid, identifier, bound) == "blocked"
        db.expire_all()
        assert db.get(CandidateJob, identifier) is None
        assert db.scalar(select(CandidateResult.id)) is None
        assert db.get(ContributionSlot, slot) is None
        assert len(server.writes) == writes_before


@pytest.mark.planning_boundary
def test_epoch_requires_exact_original_session_and_installed_producers(
    snapshot_receipt_source: Engine,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = snapshot_receipt_source
    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerSession

    from tests.test_execution_session_authorizer import guard

    with Session(customer_engine) as db:
        principal, work, _, _, adapter, _, _, _ = prepared(db, configuration, tmp_path, monkeypatch)
        decision = run(db, principal, work, adapter)
        producer = adapter.epoch_producer()
        assert producer and producer.authorized_read
        _, token = guard(db, principal.user.id)
        session = db.get(CustomerSession, token)
        assert session
        other = CustomerPrincipal(user=principal.user, session=session)
        with pytest.raises(HTTPException):
            producer.authorized_read(db, other, decision)
        assert (
            DirectionalCandidateAdapter(
                replace(adapter.runtime, policies=lambda _: None), adapter.policy_family
            ).epoch_producer()
            is None
        )
        with pytest.raises(ValueError, match="replace existing"):
            DirectionalCandidateAdapter(
                replace(adapter.runtime, candidate=adapter.bind()), adapter.policy_family
            ).bind()
