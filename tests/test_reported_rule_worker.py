"""Actual candidate queue dispatch from owned operational reports, never mature evidence."""

from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from app.executors.meta_optimization import MetaOptimizationTransport
from app.optimization_candidates import service
from app.optimization_candidates.contracts import CandidateObservation, CandidateScope
from app.optimization_candidates.models import CandidateResult
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.publication.optimization_contracts import OptimizationContext
from app.reported_feedback.candidate_contracts import ReportedRuleCandidateV1
from app.settings import Settings
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_rule_fixture import ready_reported_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("change", ["none", "session", "source", "capsule"])
def test_owned_reported_queue_produces_separate_decision(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        principal, identity, work, observation, clock, _, server = ready_reported_rule(
            db, configuration, tmp_path, monkeypatch
        )
        before = [
            db.scalar(select(func.count()).select_from(model))
            for model in (ProviderExecutionAttempt, ProviderExposureReservation)
        ]
        posts = len(server.posts)
        session_digest = principal.session.digest
        adapter = MetaOptimizationTransport(transport=httpx.MockTransport(server))

        def native(db: Session, scope: CandidateScope, now: datetime) -> CandidateObservation:
            assert not db.in_transaction()
            old = observation.state
            state = adapter.read_current(
                scope.account,
                old.target,
                old.money,
                old.qualification_id,
                old.qualification_revision,
                OptimizationContext(
                    scope=scope.account,
                    access_token=SecretStr("offline-token"),
                    expires_at=now + timedelta(hours=1),
                ),
                now,
            )
            if change != "none":
                from app.commerce.models import CommerceStore
                from app.customers.models import CustomerSession
                from app.reported_feedback.models import ReportedWindowCapsule
                from sqlalchemy import delete

                with Session(customer_engine) as update:
                    if change == "session":
                        session = update.get(CustomerSession, session_digest)
                        assert session
                        session.revoked_at = int(now.timestamp())
                    elif change == "source":
                        store = update.get(CommerceStore, work.scope.source.store_id)
                        assert store
                        store.revision += 1
                    else:
                        update.execute(
                            delete(ReportedWindowCapsule).where(
                                ReportedWindowCapsule.workspace_id
                                == work.scope.account.workspace_id
                            )
                        )
                    update.commit()
            return CandidateObservation.model_validate(
                observation.model_copy(update={"state": state})
            )

        runtime = service.CandidateRuntime(
            environment="contract_test",
            identity=identity,
            reader=native,
            policy_reader=lambda *_: None,
            clock=lambda: clock[0],
            operational_policies=(work.policy,),
        )
        from app.goals import service as goals
        from app.publication import execution_mandates
        from app.publication.execution_models import ProviderExecutionMandate

        mandate_row = db.get(ProviderExecutionMandate, work.scope.mandate.mandate_id)
        assert mandate_row
        policy = execution_mandates.policy(db, mandate_row)
        assert clock[0] < policy.ends_at, (clock[0], policy.ends_at)
        goal = goals.owned(db, work.scope.account.workspace_id, work.scope.goal_id)
        assert goals.assessment(db, goal, clock[0]) == "confirmed"
        if change == "none":
            from app.optimization_candidates import selection
            from app.optimization_candidates.selection_contracts import CandidatePolicyRef
            from app.publication.customer_optimization_contracts import TargetCatalog, TargetOption
            from app.reported_feedback.candidate_contracts import ReportedRuleSelectionBatchV1

            def catalog(request, now):  # type: ignore[no-untyped-def]
                assert not db.in_transaction()
                state = native(db, work.scope, now).state
                return TargetCatalog(
                    request=request,
                    observed_at=now,
                    expires_at=now + timedelta(minutes=1),
                    options=[
                        TargetOption(label="Owned campaign", parent_label="Campaign", state=state)
                    ],
                    complete=True,
                )

            batch, jobs = selection.enqueue_candidate_selection(
                db,
                principal,
                work.scope.account.workspace_id,
                work.scope.mandate,
                CandidatePolicyRef(policy_id=work.policy.policy_id, revision=work.policy.revision),
                selection.CandidateSelectionRuntime(
                    candidate=runtime,
                    catalog=catalog,
                    source_fence_reader=lambda *_: work.scope.source,
                    clock=lambda: clock[0],
                ),
            )
            assert isinstance(batch, ReportedRuleSelectionBatchV1)
            assert not batch.blocked and len(jobs) == 1
            job = jobs[0]
        else:
            job = service.enqueue(db, principal, work, runtime)
        identifier, wid = job.id, job.workspace_id
        db.commit()
        outcome = service.process(customer_engine, wid, identifier, runtime)
        if change != "none":
            assert outcome == "blocked"
            assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0
            assert len(server.posts) == posts
            assert before == [
                db.scalar(select(func.count()).select_from(model))
                for model in (ProviderExecutionAttempt, ProviderExposureReservation)
            ]
            return
        assert outcome == "completed"
        result = db.scalar(select(CandidateResult).where(CandidateResult.job_id == identifier))
        assert result
        decision = service.read_result(db, wid, result.id, principal, runtime)
        assert isinstance(decision, ReportedRuleCandidateV1)
        assert decision.status == "suggested" and decision.action
        assert decision.action.amount_micros == 44_750_000
        assert decision.evidence.basis == "operational_reported_efficiency_rule"
        assert decision.evidence.causal_lift == "unavailable"
        assert decision.spending_authority == "none"
        from app.optimization_candidates.customer_contracts import CandidateReadStatus
        from app.reported_feedback.candidate_source import current_comparison
        from app.reported_feedback.customer_contracts import basis_details

        _, comparison = current_comparison(db, principal, work, lambda: clock[0])
        view = CandidateReadStatus(
            job_id=identifier,
            state="completed",
            result_id=result.id,
            decision=decision,
            decision_digest=decision.digest(),
            basis_details=basis_details(decision, comparison, work.policy),
        )
        assert view.basis_details
        assert view.basis_details.before.reported_cpa_micros == "5000000"
        assert view.basis_details.after.reported_cpa_micros == "2500000"
        assert view.basis_details.proposed_delta_micros == -250_000
        assert view.basis_details.original_attempt_count == 1
        assert view.basis_details.reported_completion_count == 4
        assert "capsules" not in view.basis_details.model_dump_json()
        from app.lifecycle.export_serializers import serialize
        from app.optimization_candidates.models import CandidateJob

        for model, key in ((CandidateJob, identifier), (CandidateResult, result.id)):
            saved = db.execute(select(model.__table__).where(model.id == key)).mappings().one()
            exported, missing = serialize(model.__tablename__, dict(saved))
            assert not missing and exported
            field = "work" if model is CandidateJob else "decision"
            assert exported[field] == saved[field]
        db.commit()
        assert service.process(customer_engine, wid, identifier, runtime) == "not_due"
        assert len(server.posts) == posts
        assert before == [
            db.scalar(select(func.count()).select_from(model))
            for model in (ProviderExecutionAttempt, ProviderExposureReservation)
        ]
