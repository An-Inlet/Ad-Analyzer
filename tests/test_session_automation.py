"""Real owned Start→automatic admission→durable actual MockHTTP mutations; no approval rows."""

from pathlib import Path
from typing import Any

import pytest
from app.optimization_candidates.contracts import CandidateDecision
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.publication.execution_models import ProviderExecutionApproval, ProviderExecutionAttempt
from app.session_automation import service, worker
from app.session_automation.contracts import (
    AutomaticPolicyRef,
    SemanticDecisionEpoch,
    SessionAutomaticPolicy,
    StartSessionAutomation,
)
from app.session_automation.models import AutomaticDecisionAdmission
from app.session_automation.runtime import SemanticEpochProducer, SessionAutomationRuntime
from app.settings import Settings
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from tests.test_candidate_review_bridge import assembled
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def automatic_fixture(
    db: Session,
    configuration: Settings,
    path: Path,
    provider: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, ...]:
    principal, wid, intent, bridge, server, selection = assembled(
        db, configuration, path, provider, monkeypatch, with_selection=True
    )
    result = db.get(CandidateResult, intent.result_id)
    assert result
    decision = CandidateDecision.model_validate(result.decision)
    assert decision.action
    family = "a" * 32
    policy = SessionAutomaticPolicy(
        workspace_id=wid,
        environment="contract_test",
        policy_family="b" * 32,
        policy_id="c" * 32,
        revision=1,
        candidate_policy=CandidatePolicyRef(policy_id="0" * 32, revision=1),
        candidate_policy_digest="0" * 64,
        allowed_operations=[decision.action.kind],
        semantic_producer_families=[family],
        lifetime_seconds=300,
        cadence_seconds=1,
    )
    job = db.get(CandidateJob, result.job_id)
    assert job
    from app.optimization_candidates.service import owned_work

    work = owned_work(job)
    policy = policy.model_copy(
        update={
            "candidate_policy_digest": work.policy.digest(),
            "candidate_policy": CandidatePolicyRef(
                policy_id=work.policy.policy_id, revision=work.policy.revision
            ),
        }
    )
    policy = SessionAutomaticPolicy.model_validate(policy.model_dump(mode="json"))
    runtime = SessionAutomationRuntime(
        selection=selection,
        review=bridge,
        policies=(policy,),
        epoch_producers=(
            SemanticEpochProducer(
                family=family,
                source_schema=decision.evidence.source_schema,
                environment="contract_test",
                read=lambda db, candidate: SemanticDecisionEpoch(
                    producer_family=family,
                    source_schema=candidate.evidence.source_schema,
                    source_reference=candidate.evidence.source_reference,
                    semantic_digest=candidate.evidence.source_digest,
                ),
            ),
        ),
        clock=lambda: NOW,
    )
    start = StartSessionAutomation(
        mandate=decision.scope.mandate,
        policy=AutomaticPolicyRef(policy_id=policy.policy_id, revision=policy.revision),
    )
    # The actual worker must recreate the queue/results from selection after Start.
    db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
    db.commit()
    return principal, wid, start, runtime, server


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_start_to_actual_provider_effect_with_zero_human_approvals(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, provider, monkeypatch
        )
        run = service.start(db, principal, wid, intent, runtime)
        identifier = run.id
        assert service.start(db, principal, wid, intent, runtime).id == identifier
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0
    assert worker.advance(customer_engine, wid, identifier, runtime) == "completed"
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
    assert len(server.writes if provider == "google_ads" else server.posts) == 1
    assert worker.advance(customer_engine, wid, identifier, runtime) == "not_due"


@pytest.mark.parametrize("boundary", ["stop", "logout", "retract", "missing_guard"])
def test_revocation_after_claim_prevents_effect_and_keeps_financial_claim(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    from dataclasses import replace

    from app.optimization_candidates import review_bridge, selection
    from app.optimization_candidates import service as candidates
    from app.optimization_candidates.review_contracts import CandidateReviewIntent
    from app.publication import optimization
    from app.publication.execution_models import ProviderExposureReservation
    from app.session_automation import admission
    from fastapi import HTTPException

    from tests.test_execution_session_authorizer import revoke

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        started = service.start(db, principal, wid, intent, runtime)
        _, jobs = selection.enqueue_candidate_selection(
            db,
            principal,
            wid,
            intent.mandate,
            runtime.policies[0].candidate_policy,
            runtime.selection,
        )
        job_id = jobs[0].id
        db.commit()
        assert (
            candidates.process(customer_engine, wid, job_id, runtime.review.candidate)
            == "completed"
        )
        result = db.scalar(select(CandidateResult).where(CandidateResult.job_id == job_id))
        assert result
        prepared = review_bridge.prepare_candidate_review(
            db,
            principal,
            wid,
            CandidateReviewIntent(
                result_id=result.id, expected_decision_digest=result.decision_digest
            ),
            runtime.review,
        )
        run = admission.admit(db, wid, started.id, prepared.review_id, runtime)
        execution = admission.execution_runtime(db, wid, started.id, runtime)
        claim = optimization.claim_step(
            db, wid, run.id, principal.user.id, execution, runtime.clock
        )
        assert claim
        if boundary == "stop":
            service.stop(db, principal, wid, started.id, runtime.review.candidate.identity, runtime)
        elif boundary == "logout":
            revoke(customer_engine, principal.session.digest)
        elif boundary == "retract":
            db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
            db.commit()
        else:
            execution = replace(execution, automatic_authority_guard=None)
        with pytest.raises(HTTPException):
            optimization.execute_claim(db, claim, principal.user.id, execution, runtime.clock)
        db.rollback()
        assert not server.writes
        reservation = db.scalar(select(ProviderExposureReservation))
        assert reservation and reservation.state == "held"
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0


def test_default_scheduler_does_not_construct_runtime_under_master_disable(
    customer_engine: Engine,
) -> None:
    from app.automation.models import PlatformAutomationControl

    with Session(customer_engine) as db:
        db.add(PlatformAutomationControl(key="all_data_syncs", enabled=False, updated_by="fixture"))
        db.commit()

    def forbidden():  # type: ignore[no-untyped-def]
        raise AssertionError("disabled runtime constructed")

    assert worker.run_due(customer_engine, forbidden) == {}


@pytest.mark.parametrize(
    ("restart", "provider"),
    [
        (kind, "google_ads")
        for kind in ("observation_refresh", "new_start", "policy_revision", "mandate_revision")
    ]
    + [("new_semantic_signal", p) for p in ("google_ads", "meta_ads", "tiktok_ads")],
)
def test_one_semantic_epoch_survives_restarts_and_revisions(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restart: str,
    provider: str,
) -> None:
    from dataclasses import replace
    from datetime import timedelta

    from app.publication import execution_mandates as mandates
    from app.session_automation.models import SessionAutomationRun

    from tests.test_repeat_optimization import reader

    clock = [NOW]
    semantic = [False]
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, provider, monkeypatch
        )
        execution = replace(
            runtime.review.execution, replacement_reader=reader(runtime.review.execution)
        )
        original_reader = runtime.review.candidate.reader

        def read_current(db, scope, now):  # type: ignore[no-untyped-def]
            observation = original_reader(db, scope, now)
            state = execution.transport(scope.account).read_current(
                scope.account,
                scope.target,
                observation.state.money,
                observation.state.qualification_id,
                observation.state.qualification_revision,
                execution.context(scope.account),
                now,
            )
            # Explicit scenario: fresh native observations retain the SAME semantic
            # measurement identity. No timestamp/state digest may reset admission.
            evidence = observation.evidence.model_copy(
                update={
                    "scope_digest": scope.digest(),
                    "observed_at": now,
                    "expires_at": now + timedelta(minutes=1),
                }
            )
            if semantic[0]:
                # A separately supplied explicit new scenario measurement, not a
                # native clock, policy change or recalibration of the prior signal.
                evidence = evidence.model_copy(
                    update={
                        "source_reference": "d" * 32,
                        "source_digest": "e" * 64,
                    }
                )
            return observation.model_copy(
                update={"scope": scope, "state": state, "evidence": evidence}
            )

        candidate = replace(runtime.review.candidate, reader=read_current, clock=lambda: clock[0])
        runtime = replace(
            runtime,
            clock=lambda: clock[0],
            selection=replace(runtime.selection, candidate=candidate, clock=lambda: clock[0]),
            review=replace(
                runtime.review, candidate=candidate, execution=execution, clock=lambda: clock[0]
            ),
        )
        started = service.start(db, principal, wid, intent, runtime)
        identifier = started.id
        actor, session_digest = principal.user.id, principal.session.digest
    assert worker.advance(customer_engine, wid, identifier, runtime) == "completed"
    clock[0] += timedelta(seconds=2)
    semantic[0] = restart == "new_semantic_signal"
    with Session(customer_engine) as db:
        from app.optimization_candidates.review_bridge import original

        principal = original(db, actor, session_digest)
        if restart not in {"observation_refresh", "new_semantic_signal"}:
            service.stop(db, principal, wid, identifier, runtime.review.candidate.identity, runtime)
            if restart == "policy_revision":
                policy = runtime.policies[0].model_copy(update={"revision": 2})
                runtime = replace(runtime, policies=(policy,))
                intent = intent.model_copy(
                    update={"policy": AutomaticPolicyRef(policy_id=policy.policy_id, revision=2)}
                )
            elif restart == "mandate_revision":
                _, original_mandate = mandates.owned(db, wid, intent.mandate.mandate_id)
                policy = mandates.policy(db, original_mandate)
                revised = mandates.revise(
                    db,
                    wid,
                    policy,
                    principal.user.id,
                    runtime.clock,
                    mandate_id=original_mandate.id,
                    expected_revision=original_mandate.revision,
                )
                consent = mandates.consent(
                    db,
                    wid,
                    revised.id,
                    revised.revision,
                    policy.digest(),
                    principal.user.id,
                    runtime.clock,
                )
                intent = intent.model_copy(update={"mandate": consent})
            identifier = service.start(db, principal, wid, intent, runtime).id
    expected = 2 if semantic[0] else 1
    assert worker.advance(customer_engine, wid, identifier, runtime) == (
        "completed" if semantic[0] else "blocked"
    )
    with Session(customer_engine) as db:
        row = db.get(SessionAutomationRun, identifier)
        assert row and row.reason == ("ready" if semantic[0] else "decision_already_used")
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == expected
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == expected
    assert len(server.writes if provider == "google_ads" else server.posts) == expected


def test_final_context_stop_blocks_emission_and_manual_fallback(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from app.optimization_candidates import review_bridge, selection
    from app.optimization_candidates import service as candidates
    from app.optimization_candidates.review_contracts import CandidateReviewIntent
    from app.publication import optimization
    from app.session_automation import admission
    from fastapi import HTTPException

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        started = service.start(db, principal, wid, intent, runtime)
        identifier, actor, token = started.id, principal.user.id, principal.session.digest
        _, jobs = selection.enqueue_candidate_selection(
            db,
            principal,
            wid,
            intent.mandate,
            runtime.policies[0].candidate_policy,
            runtime.selection,
        )
        job_id = jobs[0].id
        db.commit()
        assert (
            candidates.process(customer_engine, wid, job_id, runtime.review.candidate)
            == "completed"
        )
        result = db.scalar(select(CandidateResult).where(CandidateResult.job_id == job_id))
        assert result
        prepared = review_bridge.prepare_candidate_review(
            db,
            principal,
            wid,
            CandidateReviewIntent(
                result_id=result.id, expected_decision_digest=result.decision_digest
            ),
            runtime.review,
        )
        run = admission.admit(db, wid, identifier, prepared.review_id, runtime)
        execution = admission.execution_runtime(db, wid, identifier, runtime)
        with pytest.raises(HTTPException, match="cannot become customer approval"):
            optimization.approve_optimization(
                db,
                wid,
                prepared.review_id,
                prepared.review_digest,
                prepared.plan_digest,
                actor,
                execution,
                runtime.clock,
            )
        db.rollback()
        with pytest.raises(HTTPException, match="cannot become customer approval"):
            optimization.create_run(db, wid, prepared.review_id, actor, execution, runtime.clock)
        db.rollback()
        claim = optimization.claim_step(db, wid, run.id, actor, execution, runtime.clock)
        assert claim
        calls = []

        def context(scope):  # type: ignore[no-untyped-def]
            calls.append(1)
            if len(calls) == 3:
                with Session(customer_engine) as other:
                    current = review_bridge.original(other, actor, token)
                    service.stop(
                        other, current, wid, identifier, runtime.review.candidate.identity, runtime
                    )
            return execution.context(scope)

        blocked = replace(execution, context=context)
        with pytest.raises(HTTPException):
            optimization.execute_claim(db, claim, actor, blocked, runtime.clock)
        db.rollback()
        assert len(calls) == 3 and not server.writes
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0


def test_registry_export_keeps_authority_lineage_without_session_secret(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.lifecycle.export_serializers import serialize
    from app.lifecycle.local_work import verify_work_registry
    from app.session_automation.models import SessionAutomationRun

    verify_work_registry()
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, _ = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        identifier = service.start(db, principal, wid, intent, runtime).id
    assert worker.advance(customer_engine, wid, identifier, runtime) == "completed"
    with Session(customer_engine) as db:
        for model in (SessionAutomationRun, AutomaticDecisionAdmission):
            raw = dict(db.execute(select(model.__table__)).mappings().one())
            exported, missing = serialize(model.__tablename__, raw)
            assert not missing and exported["workspace_id"] == wid
            assert "original_session_digest" not in exported
            assert "decision" not in exported and "evidence" not in exported


def test_revoked_earliest_run_does_not_shadow_new_session_in_same_workspace(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.optimization_candidates.review_bridge import original

    from tests.test_execution_session_authorizer import guard, revoke

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        actor, original_token = principal.user.id, principal.session.digest
        first_id = service.start(db, principal, wid, intent, runtime).id
    revoke(customer_engine, original_token)
    with Session(customer_engine) as db:
        _, new_token = guard(db, actor)
        principal = original(db, actor, new_token)
        second_id = service.start(db, principal, wid, intent, runtime).id
        assert first_id != second_id
        # Deterministic earlier slot; there is no timestamp-based financial authority.
        from datetime import timedelta

        first = service.load(db, wid, first_id)
        first.next_due_at = NOW - timedelta(seconds=1)
        db.commit()
    assert worker.run_due(customer_engine, lambda: runtime) == {"blocked": 1}
    assert worker.run_due(customer_engine, lambda: runtime) == {"completed": 1}
    assert len(server.writes) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_unknown_original_keeps_hold_and_reconciles_after_session_stop_without_replay(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    from app.optimization_candidates import review_bridge
    from app.publication import optimization
    from app.publication.execution_models import ProviderExposureReservation
    from app.publication.optimization_contracts import (
        GoogleBudgetSetV1,
        MetaBudgetSetV1,
        OptimizationRequest,
        TikTokBudgetSetV1,
    )

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, provider, monkeypatch
        )
        actor, token = principal.user.id, principal.session.digest
        identifier = service.start(db, principal, wid, intent, runtime).id
    server.ignore, server.timeout = True, True
    assert worker.advance(customer_engine, wid, identifier, runtime) == "completed"
    with Session(customer_engine) as db:
        attempt = db.scalar(select(ProviderExecutionAttempt))
        assert attempt
        attempt_id, fence = attempt.id, attempt.fence
        request = OptimizationRequest.model_validate(attempt.request)
        principal = review_bridge.original(db, actor, token)
        service.stop(db, principal, wid, identifier, runtime.review.candidate.identity, runtime)
        db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
        db.commit()
        reservation = db.scalar(select(ProviderExposureReservation))
        assert reservation and reservation.state == "held"
        db.commit()
        # A late original operation becomes visible. This mutates only MockServer
        # state and does not submit another request or invent a new fence.
        assert isinstance(
            request.intent.action, (GoogleBudgetSetV1, MetaBudgetSetV1, TikTokBudgetSetV1)
        )
        amount = request.intent.action.amount_micros
        if provider == "google_ads":
            server.budget["amountMicros"] = str(amount)
        elif provider == "meta_ads":
            server.meta_child["daily_budget"] = str(amount // 10_000)
        else:
            server.tk_child["budget"] = amount / 1_000_000
        receipt = optimization.reconcile_attempt(
            db, wid, attempt_id, runtime.review.execution, runtime.clock
        )
        assert receipt.outcome == "verified_target_state"
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        assert db.get(ProviderExecutionAttempt, attempt_id).fence == fence  # type: ignore[union-attr]
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(ProviderExposureReservation.state)) == "held"
    assert len(server.writes if provider == "google_ads" else server.posts) == 1


def test_concurrent_session_ticks_create_one_original_attempt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency qualification")
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        identifier = service.start(db, principal, wid, intent, runtime).id
    barrier = Barrier(2)

    def tick() -> str:
        barrier.wait(timeout=10)
        return worker.advance(customer_engine, wid, identifier, runtime)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(tick), pool.submit(tick)
        results = {first.result(timeout=30), second.result(timeout=30)}
    assert results == {"completed", "not_due"}
    assert len(server.writes) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0


def test_shipped_scheduler_opt_in_reaches_actual_session_worker(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.jobs.customer_runtime import run_customer_tick

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        service.start(db, principal, wid, intent, runtime)
    result = run_customer_tick(
        customer_engine,
        configuration=Settings(INLET_CUSTOMER_SESSION_AUTOMATION_ENABLED=True),
        automation_factory=lambda: runtime,
    )
    assert result == {"session_automation": "completed"}
    assert len(server.writes) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1


def test_same_reference_cannot_silently_change_numeric_policy(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from fastapi import HTTPException

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, _ = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        identifier = service.start(db, principal, wid, intent, runtime).id
        original = runtime.selection.candidate.policy_reader

        def changed(db, wid, policy_id, revision):  # type: ignore[no-untyped-def]
            policy = original(db, wid, policy_id, revision)
            assert policy
            return policy.model_copy(update={"budget_step_micros": 2_000_000})

        altered = replace(
            runtime,
            selection=replace(
                runtime.selection,
                candidate=replace(runtime.selection.candidate, policy_reader=changed),
            ),
        )
        with pytest.raises(HTTPException, match="policy_not_available"):
            service.current(db, wid, identifier, altered)
        with pytest.raises(HTTPException, match="policy_not_available"):
            service.start(db, principal, wid, intent, altered)
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0


def test_final_admission_failure_rolls_back_marker_epoch_and_run_together(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from app.optimization_candidates import review_bridge, selection
    from app.optimization_candidates import service as candidates
    from app.optimization_candidates.review_contracts import CandidateReviewIntent
    from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
    from app.session_automation import admission
    from fastapi import HTTPException

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, _ = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        identifier = service.start(db, principal, wid, intent, runtime).id
        _, jobs = selection.enqueue_candidate_selection(
            db,
            principal,
            wid,
            intent.mandate,
            runtime.policies[0].candidate_policy,
            runtime.selection,
        )
        job_id = jobs[0].id
        db.commit()
        assert (
            candidates.process(customer_engine, wid, job_id, runtime.review.candidate)
            == "completed"
        )
        result = db.scalar(select(CandidateResult).where(CandidateResult.job_id == job_id))
        assert result
        prepared = review_bridge.prepare_candidate_review(
            db,
            principal,
            wid,
            CandidateReviewIntent(
                result_id=result.id, expected_decision_digest=result.decision_digest
            ),
            runtime.review,
        )
        producer = runtime.epoch_producers[0]
        calls = []

        def fail_after_flush(db, decision):  # type: ignore[no-untyped-def]
            if db.scalar(select(func.count()).select_from(ProviderExecutionRun)):
                calls.append("flushed_run")
                raise HTTPException(409, "final semantic source retracted")
            return producer.read(db, decision)

        broken = replace(runtime, epoch_producers=(replace(producer, read=fail_after_flush),))
        with pytest.raises(HTTPException, match="final semantic source retracted"):
            admission.admit(db, wid, identifier, prepared.review_id, broken)
        assert calls == ["flushed_run"]
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
        review = db.get(ProviderExecutionReview, prepared.review_id, populate_existing=True)
        assert review and not review.automatic_authority_required
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
