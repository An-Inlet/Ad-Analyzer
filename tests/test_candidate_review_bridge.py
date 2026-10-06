"""Runnable all-provider offline composition; only harness performs human approval."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.optimization_candidates import review_bridge as b
from app.optimization_candidates import selection
from app.optimization_candidates import service as c
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.review_contracts import CandidateReviewIntent
from app.optimization_candidates.review_models import CandidateReviewLink
from app.publication import optimization as o
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionAttempt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from tests import test_optimization_candidates as fixtures
from tests.test_candidate_selection import prepared
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_execution_session_authorizer import revoke
from tests.test_shopify_sales import configuration as configuration


def assembled(
    db: Session,
    config: Settings,
    path: Path,
    provider: str,
    monkeypatch: pytest.MonkeyPatch,
    with_selection: bool = False,
) -> tuple[Any, ...]:
    captures = []

    def capture(*args, **kwargs):  # type: ignore[no-untyped-def]
        result = ready(*args, **kwargs)
        captures.append(result[6])
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(fixtures, "ready", capture)
        principal, work, observation, runtime, ref, server = prepared(db, config, path, provider)
    wid, actor, token = work.scope.account.workspace_id, principal.user.id, principal.session.digest
    _, jobs = selection.enqueue_candidate_selection(
        db, principal, wid, work.scope.mandate, ref, runtime
    )
    job_id = jobs[0].id
    db.commit()
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    assert c.process(engine, wid, job_id, runtime.candidate) == "completed"
    result = db.scalar(select(CandidateResult).where(CandidateResult.job_id == job_id))
    assert result
    bridge = b.CandidateReviewRuntime(
        candidate=runtime.candidate, execution=captures[0], clock=lambda: NOW
    )
    principal = b.original(db, actor, token)
    intent = CandidateReviewIntent(
        result_id=result.id, expected_decision_digest=result.decision_digest
    )
    db.commit()
    values = (principal, wid, intent, bridge, server)
    return (*values, runtime) if with_selection else values


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_runnable_all_provider_review_then_genuine_harness_approval(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = assembled(
            db, configuration, tmp_path, provider, monkeypatch
        )
        actor = principal.user.id
        review = b.prepare_candidate_review(db, principal, wid, intent, runtime)
        assert review.status == "review_required"
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert len(server.writes if provider == "google_ads" else server.posts) == 0
        stored = db.get(ProviderExecutionReview, review.review_id)
        assert stored and stored.candidate_provenance_required
        assert (
            b.prepare_candidate_review(db, principal, wid, intent, runtime).review_id
            == review.review_id
        )
        execution = b.bind_execution(runtime, principal)
        # Distinct explicit customer interaction in the harness, never performed by bridge.
        o.approve_optimization(
            db,
            wid,
            review.review_id,
            review.review_digest,
            review.plan_digest,
            actor,
            execution,
            lambda: NOW,
        )
        run = o.create_run(db, wid, review.review_id, actor, execution, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
        assert claim
        receipt = o.execute_claim(db, claim, actor, execution, lambda: NOW)
        assert receipt.outcome == "verified_target_state"
        assert len(server.writes if provider == "google_ads" else server.posts) == 1
        db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
        db.commit()
        link = db.get(CandidateReviewLink, review.review_id, populate_existing=True)
        assert link and link.candidate_result_id is None and link.candidate_workspace_id is None
        assert link.candidate_digest == intent.expected_decision_digest
        # Historical readback/reconciliation remains available after candidate erasure.
        o.reconcile_attempt(
            db, wid, claim.attempt_id, execution, lambda: NOW + timedelta(seconds=1)
        )
        reservation = db.scalar(select(ProviderExposureReservation))
        assert reservation and reservation.state == "held"
        assert len(server.writes if provider == "google_ads" else server.posts) == 1
        from app.publication import coordinator, settlement

        from tests.test_provider_settlement import qualified

        coordinator.cancel_creation(db, wid, run.id, actor, lambda: NOW + timedelta(seconds=2))
        settled = settlement.settle(
            db,
            wid,
            reservation.id,
            actor,
            settlement.SettlementRuntime("contract_test", qualified),
            lambda: NOW + timedelta(seconds=2),
        )
        assert settled.state == "settled"


@pytest.mark.parametrize("stage", ["review", "claimed", "missing_guard", "missing_link"])
def test_retraction_never_falls_back_to_manual(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = assembled(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        actor = principal.user.id
        review = b.prepare_candidate_review(db, principal, wid, intent, runtime)
        execution = b.bind_execution(runtime, principal)
        claim = None
        if stage == "claimed":
            o.approve_optimization(
                db,
                wid,
                review.review_id,
                review.review_digest,
                review.plan_digest,
                actor,
                execution,
                lambda: NOW,
            )
            run = o.create_run(db, wid, review.review_id, actor, execution, lambda: NOW)
            claim = o.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
        if stage == "missing_guard":
            execution = replace(execution, candidate_review_guard=None)
        elif stage == "missing_link":
            db.execute(delete(CandidateReviewLink))
            db.commit()
        else:
            db.execute(delete(CandidateJob))
            db.commit()
        with pytest.raises(HTTPException):
            if claim:
                o.execute_claim(db, claim, actor, execution, lambda: NOW)
            else:
                o.approve_optimization(
                    db,
                    wid,
                    review.review_id,
                    review.review_digest,
                    review.plan_digest,
                    actor,
                    execution,
                    lambda: NOW,
                )
        assert not server.writes


@pytest.mark.parametrize("change", ["logout", "privacy"])
def test_logout_during_qualification_rolls_back_review_link(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, _ = assembled(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        token = principal.session.digest
        reader = runtime.execution.qualification_reader

        def revoked(*args, **kwargs):  # type: ignore[no-untyped-def]
            result = reader(*args, **kwargs)
            if change == "logout":
                revoke(customer_engine, token)
            else:
                from app.lifecycle.privacy import bump_workspace_export_revision

                with Session(customer_engine) as other:
                    bump_workspace_export_revision(other, wid)
                    other.commit()
            return result

        runtime = replace(
            runtime, execution=replace(runtime.execution, qualification_reader=revoked)
        )
        with pytest.raises(HTTPException):
            b.prepare_candidate_review(db, principal, wid, intent, runtime)
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 0
        assert db.scalar(select(func.count()).select_from(CandidateReviewLink)) == 0


def test_retraction_in_final_context_blocks_emission(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = assembled(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        actor = principal.user.id
        review = b.prepare_candidate_review(db, principal, wid, intent, runtime)
        execution = b.bind_execution(runtime, principal)
        o.approve_optimization(
            db,
            wid,
            review.review_id,
            review.review_digest,
            review.plan_digest,
            actor,
            execution,
            lambda: NOW,
        )
        run = o.create_run(db, wid, review.review_id, actor, execution, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
        assert claim
        context = execution.context
        calls = [0]

        def retract(scope):  # type: ignore[no-untyped-def]
            calls[0] += 1
            if calls[0] == 3:
                with Session(customer_engine) as other:
                    other.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
                    other.commit()
            return context(scope)

        execution = replace(execution, context=retract)
        with pytest.raises(HTTPException):
            o.execute_claim(db, claim, actor, execution, lambda: NOW)
        assert calls[0] == 3 and not server.writes
        db.rollback()
        reservation = db.scalar(select(ProviderExposureReservation))
        assert reservation and reservation.state == "held"


def test_failure_after_review_flush_cannot_commit_unlinked_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, _ = assembled(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        original = b.guard_for

        def broken(runtime):  # type: ignore[no-untyped-def]
            real = original(runtime)

            def check(db, wid, rid, actor, clock):  # type: ignore[no-untyped-def]
                real(db, wid, rid, actor, clock)
                assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 1
                assert db.scalar(select(func.count()).select_from(CandidateReviewLink)) == 1
                raise RuntimeError("controlled provenance guard failure")

            return check

        monkeypatch.setattr(b, "guard_for", broken)
        with pytest.raises(RuntimeError, match="controlled provenance"):
            b.prepare_candidate_review(db, principal, wid, intent, runtime)
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 0
        assert db.scalar(select(func.count()).select_from(CandidateReviewLink)) == 0


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_candidate_repeat_resolves_actual_retained_owner(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    from app.optimization_candidates.contracts import CandidateObservation
    from app.optimization_candidates.selection_contracts import CandidatePolicyRef
    from app.publication.customer_optimization_contracts import TargetRequest
    from app.publication.replacement_contracts import RepeatOptimizationReview

    from tests.test_repeat_optimization import reader

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server, selection_runtime = assembled(
            db, configuration, tmp_path, provider, monkeypatch, True
        )
        actor = principal.user.id
        review = b.prepare_candidate_review(db, principal, wid, intent, runtime)
        execution = b.bind_execution(runtime, principal)
        o.approve_optimization(
            db,
            wid,
            review.review_id,
            review.review_digest,
            review.plan_digest,
            actor,
            execution,
            lambda: NOW,
        )
        run = o.create_run(db, wid, review.review_id, actor, execution, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
        assert claim
        o.execute_claim(db, claim, actor, execution, lambda: NOW)
        predecessor = run.reservation_id
        job = db.scalar(select(CandidateJob))
        assert job
        work = c.owned_work(job)
        previous_observation = runtime.candidate.reader(db, work.scope, NOW)

        def fresh(db, scope, now):  # type: ignore[no-untyped-def]
            catalog = selection_runtime.catalog(
                TargetRequest(
                    scope=scope.account,
                    goal_id=scope.goal_id,
                    goal_revision=scope.goal_revision,
                    goal_digest=scope.goal_digest,
                ),
                now,
            )
            return CandidateObservation(
                scope=scope, state=catalog.options[0].state, evidence=previous_observation.evidence
            )

        candidate = replace(runtime.candidate, reader=fresh)
        selected = replace(selection_runtime, candidate=candidate)
        _, jobs = selection.enqueue_candidate_selection(
            db,
            principal,
            wid,
            work.scope.mandate,
            CandidatePolicyRef(policy_id=work.policy.policy_id, revision=work.policy.revision),
            selected,
        )
        job_id = jobs[0].id
        db.commit()
        assert c.process(customer_engine, wid, job_id, candidate) == "completed"
        result = db.scalar(select(CandidateResult).where(CandidateResult.job_id == job_id))
        assert result
        runtime = replace(
            runtime,
            candidate=candidate,
            execution=replace(runtime.execution, replacement_reader=reader(runtime.execution)),
        )
        next_intent = CandidateReviewIntent(
            result_id=result.id, expected_decision_digest=result.decision_digest
        )
        repeated = b.prepare_candidate_review(db, principal, wid, next_intent, runtime)
        row = db.get(ProviderExecutionReview, repeated.review_id)
        assert row
        document = RepeatOptimizationReview.model_validate(row.document)
        assert document.predecessor.predecessor_id == predecessor
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 1
        execution = b.bind_execution(runtime, principal)
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, execution, lambda: NOW
        )
        next_run = o.create_run(db, wid, row.id, actor, execution, lambda: NOW)
        next_claim = o.claim_step(db, wid, next_run.id, actor, execution, lambda: NOW)
        assert next_claim
        assert (
            o.execute_claim(db, next_claim, actor, execution, lambda: NOW).outcome
            == "verified_target_state"
        )
        assert len(server.writes if provider == "google_ads" else server.posts) == 2
        old = db.get(ProviderExposureReservation, predecessor)
        assert old and old.state == "superseded"
        assert o.positive_changes_used(db, wid, work.scope.mandate.ledger_id) == 2_000_000


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_unknown_survives_erasure_and_late_same_fence_reconciles(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = assembled(
            db, configuration, tmp_path, provider, monkeypatch
        )
        actor = principal.user.id
        review = b.prepare_candidate_review(db, principal, wid, intent, runtime)
        execution = b.bind_execution(runtime, principal)
        o.approve_optimization(
            db,
            wid,
            review.review_id,
            review.review_digest,
            review.plan_digest,
            actor,
            execution,
            lambda: NOW,
        )
        run = o.create_run(db, wid, review.review_id, actor, execution, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
        assert claim
        server.ignore, server.timeout = True, True
        receipt = o.execute_claim(db, claim, actor, execution, lambda: NOW)
        assert receipt.outcome == "unknown"
        db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
        db.commit()
        with pytest.raises(HTTPException):
            o.execute_claim(db, claim, actor, execution, lambda: NOW)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        from app.publication.optimization_contracts import (
            GoogleBudgetSetV1,
            MetaBudgetSetV1,
            TikTokBudgetSetV1,
        )

        action = claim.request.intent.action
        assert isinstance(action, (GoogleBudgetSetV1, MetaBudgetSetV1, TikTokBudgetSetV1))
        amount = action.amount_micros
        # Controlled delayed original provider effect, not a second adapter mutation.
        if provider == "google_ads":
            server.budget["amountMicros"] = str(amount)
        elif provider == "meta_ads":
            server.meta_child["daily_budget"] = str(amount // 10_000)
        else:
            server.tk_child["budget"] = amount / 1_000_000
        late = o.reconcile_attempt(
            db, wid, claim.attempt_id, execution, lambda: NOW + timedelta(seconds=1)
        )
        assert late.outcome == "verified_target_state" and late.fence == claim.request.fence
        assert len(server.writes if provider == "google_ads" else server.posts) == 1


def test_fk_retraction_between_source_validation_and_link_lock_blocks(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL independent transaction FK race")
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, _ = assembled(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        actor = principal.user.id
        review = b.prepare_candidate_review(db, principal, wid, intent, runtime)
    validated, proceed = Event(), Event()
    original = b.bound_candidate

    def barrier(*args, **kwargs):  # type: ignore[no-untyped-def]
        value = original(*args, **kwargs)
        validated.set()
        assert proceed.wait(10)
        return value

    monkeypatch.setattr(b, "bound_candidate", barrier)

    def worker() -> None:
        with Session(customer_engine) as db:
            b.guard_for(runtime)(db, wid, review.review_id, actor, lambda: NOW)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        assert validated.wait(10)
        try:
            # Database cascades can be triggered by a dependency transaction; the
            # guard must not rely on its earlier in-memory link remaining current.
            with Session(customer_engine) as db:
                db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
                db.commit()
        finally:
            proceed.set()
        with pytest.raises(HTTPException, match="retracted during admission"):
            future.result(timeout=10)


def test_provenance_export_contains_no_session_or_measurement_body(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.lifecycle.export_serializers import serialize

    with Session(customer_engine) as db:
        principal, wid, intent, runtime, _ = assembled(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        review = b.prepare_candidate_review(db, principal, wid, intent, runtime)
        mapping = dict(db.execute(select(CandidateReviewLink.__table__)).mappings().one())
        exported, missing = serialize(CandidateReviewLink.__tablename__, mapping)
        assert not missing
        assert exported["review_id"] == review.review_id
        assert "original_session_digest" not in exported
        assert not any(isinstance(v, (dict, list)) for v in exported.values())
        assert mapping["original_session_digest"] not in str(exported)
