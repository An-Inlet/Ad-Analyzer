"""Operational rule source is real; financial closure remains explicit contract scenario."""

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.optimization_candidates import review_bridge, selection
from app.optimization_candidates import service as candidates
from app.optimization_candidates.contracts import CandidateObservation, CandidateScope
from app.optimization_candidates.models import CandidateResult
from app.optimization_candidates.review_contracts import CandidateReviewIntent
from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.publication import optimization
from app.publication.customer_optimization_contracts import TargetCatalog, TargetOption
from app.publication.execution_contracts import ExecutionAccount
from app.publication.execution_models import ProviderExecutionApproval, ProviderExposureReservation
from app.publication.optimization_contracts import OptimizationContext
from app.reported_feedback.automatic_contracts import (
    REPORTED_RULE_EPOCH_FAMILY,
    REPORTED_RULE_FAMILY,
    ReportedRuleAutomaticPolicyV1,
    StartReportedRuleAutomationV1,
)
from app.session_automation import admission, service
from app.session_automation.contracts import StartSessionAutomation
from app.session_automation.models import AutomaticDecisionAdmission
from app.session_automation.runtime import SessionAutomationRuntime
from app.settings import Settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_rule_fixture import ready_reported_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_repeat_optimization import reader
from tests.test_shopify_sales import configuration as configuration


def assembled(
    db: Session, configuration: Settings, path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, ...]:
    executions: list[Any] = []
    principal, identity, work, observation, clock, _, server = ready_reported_rule(
        db, configuration, path, monkeypatch, execution_out=executions
    )

    def context(scope: ExecutionAccount) -> OptimizationContext:
        return OptimizationContext(
            scope=scope,
            access_token=SecretStr("offline-token"),
            expires_at=clock[0] + timedelta(hours=1),
        )

    execution = replace(executions[0], context=context)
    execution = replace(execution, replacement_reader=reader(execution))

    def native(db: Session, scope: CandidateScope, now: datetime) -> CandidateObservation:
        assert not db.in_transaction()
        state = execution.meta.read_current(
            scope.account,
            scope.target,
            observation.state.money,
            observation.state.qualification_id,
            observation.state.qualification_revision,
            context(scope.account),
            now,
        )
        return CandidateObservation(scope=scope, state=state, evidence=observation.evidence)

    candidate = candidates.CandidateRuntime(
        "contract_test",
        identity,
        native,
        lambda *_: None,
        lambda: clock[0],
        operational_policies=(work.policy,),
    )

    def catalog(request, now):  # type: ignore[no-untyped-def]
        state = native(db, work.scope, now).state
        return TargetCatalog(
            request=request,
            observed_at=now,
            expires_at=now + timedelta(minutes=1),
            options=[TargetOption(label="Owned campaign", parent_label="Campaign", state=state)],
            complete=True,
        )

    selected = selection.CandidateSelectionRuntime(
        candidate, catalog, lambda *_: work.scope.source, lambda: clock[0]
    )
    bridge = review_bridge.CandidateReviewRuntime(candidate, execution, lambda: clock[0])
    policy = ReportedRuleAutomaticPolicyV1(
        decision_basis="operational_reported_efficiency_rule",
        workspace_id=work.policy.workspace_id,
        environment="contract_test",
        policy_family=REPORTED_RULE_FAMILY,
        policy_id="a" * 32,
        revision=1,
        candidate_policy=CandidatePolicyRef(
            policy_id=work.policy.policy_id, revision=work.policy.revision
        ),
        candidate_policy_digest=work.policy.digest(),
        allowed_operations=("meta_budget_set_v1",),
        semantic_producer_families=(REPORTED_RULE_EPOCH_FAMILY,),
        lifetime_seconds=60,
        cadence_seconds=30,
    )
    runtime = SessionAutomationRuntime(selected, bridge, (policy,), (), lambda: clock[0])
    return principal, work, runtime, policy, clock, server


@pytest.mark.parametrize(
    "automatic,change",
    [
        (False, "none"),
        (True, "none"),
        (True, "session"),
        (True, "capsule"),
        (True, "original"),
        (True, "unknown"),
    ],
)
def test_actual_reported_candidate_review_and_distinct_admission(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    automatic: bool,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        principal, work, runtime, policy, clock, server = assembled(
            db, configuration, tmp_path, monkeypatch
        )
        wid, actor = work.scope.account.workspace_id, principal.user.id
        approval_count = int(
            db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) or 0
        )
        if automatic:
            with pytest.raises(HTTPException, match="explicit_reported_rule_start_required"):
                service.start(
                    db,
                    principal,
                    wid,
                    StartSessionAutomation(
                        mandate=work.scope.mandate,
                        policy={"policy_id": policy.policy_id, "revision": 1},
                    ),
                    runtime,
                )
            db.rollback()
            session_run = service.start(
                db,
                principal,
                wid,
                StartReportedRuleAutomationV1(
                    schema_version="inlet.start-reported-rule-automation.v1",
                    decision_basis="operational_reported_efficiency_rule",
                    mandate=work.scope.mandate,
                    policy={"policy_id": policy.policy_id, "revision": 1},
                    expected_policy_digest=policy.digest(),
                ),
                runtime,
            )
            session_id = session_run.id
        _, jobs = selection.enqueue_candidate_selection(
            db, principal, wid, work.scope.mandate, policy.candidate_policy, runtime.selection
        )
        job_id = jobs[0].id
        db.commit()
        assert (
            candidates.process(customer_engine, wid, job_id, runtime.review.candidate)
            == "completed"
        )
        result = db.scalar(select(CandidateResult).where(CandidateResult.job_id == job_id))
        assert result
        reviewed = review_bridge.prepare_candidate_review(
            db,
            principal,
            wid,
            CandidateReviewIntent(
                result_id=result.id, expected_decision_digest=result.decision_digest
            ),
            runtime.review,
        )
        if automatic:
            run = admission.admit(db, wid, session_id, reviewed.review_id, runtime)
            execution = admission.execution_runtime(db, wid, session_id, runtime)
            if change == "none":
                revised = policy.model_copy(update={"revision": 2})
                revised_runtime = replace(runtime, policies=(policy, revised))
                restarted = service.start(
                    db,
                    principal,
                    wid,
                    StartReportedRuleAutomationV1(
                        schema_version="inlet.start-reported-rule-automation.v1",
                        decision_basis="operational_reported_efficiency_rule",
                        mandate=work.scope.mandate,
                        policy={"policy_id": revised.policy_id, "revision": revised.revision},
                        expected_policy_digest=revised.digest(),
                    ),
                    revised_runtime,
                )
                with pytest.raises(HTTPException, match="decision_already_used"):
                    admission.admit(db, wid, restarted.id, reviewed.review_id, revised_runtime)
                assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1
        else:
            execution = review_bridge.bind_execution(runtime.review, principal)
            optimization.approve_optimization(
                db,
                wid,
                reviewed.review_id,
                reviewed.review_digest,
                reviewed.plan_digest,
                actor,
                execution,
                runtime.clock,
            )
            run = optimization.create_run(
                db, wid, reviewed.review_id, actor, execution, runtime.clock
            )
        claim = optimization.claim_step(db, wid, run.id, actor, execution, runtime.clock)
        assert claim
        # Normal reads and unrelated review IDs cannot use the private continuation.
        with pytest.raises(HTTPException):
            candidates.read_result(
                db, wid, result.id, principal, runtime.review.candidate, erase_invalid=False
            )
        with pytest.raises(HTTPException):
            candidates.read_result(
                db,
                wid,
                result.id,
                principal,
                runtime.review.candidate,
                erase_invalid=False,
                forward_review_id="0" * 32,
            )
        if change in {"session", "capsule", "original"}:
            from app.customers.models import CustomerSession
            from app.publication.execution_models import ProviderExecutionAttempt
            from app.publication.optimization_contracts import OptimizationRequest
            from app.reported_feedback.models import ReportedWindowCapsule
            from sqlalchemy import delete

            if change == "session":
                saved_session = db.get(CustomerSession, principal.session.digest)
                assert saved_session
                saved_session.revoked_at = int(clock[0].timestamp())
            elif change == "capsule":
                db.execute(
                    delete(ReportedWindowCapsule).where(ReportedWindowCapsule.workspace_id == wid)
                )
            else:
                original = db.get(ProviderExecutionAttempt, work.scope.source.attempt_id)
                assert original
                request = OptimizationRequest.model_validate(original.request)
                optimization.record_receipt(
                    db,
                    wid,
                    original.id,
                    optimization.unknown(request, runtime.clock),
                    runtime.clock,
                )
            db.commit()
            with pytest.raises(HTTPException):
                optimization.execute_claim(db, claim, actor, execution, runtime.clock)
            assert len(server.posts) == 1
        else:
            server.timeout = server.ignore = change == "unknown"
            receipt = optimization.execute_claim(db, claim, actor, execution, runtime.clock)
            assert receipt.outcome == (
                "unknown" if change == "unknown" else "verified_target_state"
            )
            assert len(server.posts) == 2
            with pytest.raises(HTTPException):
                optimization.execute_claim(db, claim, actor, execution, runtime.clock)
            if change == "unknown":
                from app.optimization_candidates.models import CandidateJob
                from sqlalchemy import delete

                db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
                db.commit()
                optimization.reconcile_attempt(db, wid, claim.attempt_id, execution, runtime.clock)
                assert len(server.posts) == 2

        assert db.scalar(
            select(func.count()).select_from(ProviderExecutionApproval)
        ) == approval_count + int(not automatic)
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == int(
            automatic
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(ProviderExposureReservation)
                .where(ProviderExposureReservation.state == "held")
            )
            == 1
        )
