"""Actual current preview and native HTTP feed the central candidate/review worker."""

from pathlib import Path
from typing import Any

import pytest
from app.optimization_candidates import review_bridge, service
from app.optimization_candidates.models import CandidateResult
from app.optimization_candidates.review_contracts import CandidateReviewIntent
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.settings import Settings
from sqlalchemy import Engine, func, select

from tests.initial_rule_fixture import configured_initial_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("change", ["none", "session", "observation"])
def historical_contract_actual_initial_source_candidate_worker_and_exact_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    with configured_initial_rule(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    ) as context:
        native = context.planning.optimization
        assert native
        runtime = service.CandidateRuntime(
            "contract_test",
            context.provider,
            context.reads.read,
            lambda *_: None,
            native.clock,
            operational_policies=(context.policy,),
            initial_planning=context.planning,
        )
        wid = context.work.scope.account.workspace_id
        row = service.enqueue(context.db, context.principal, context.work, runtime)
        job_id = row.id
        context.db.commit()
        assert service.process(customer_engine, wid, job_id, runtime) == "completed"
        result = context.db.scalar(select(CandidateResult).where(CandidateResult.job_id == job_id))
        assert result
        decision = service.read_result(context.db, wid, result.id, context.principal, runtime)
        assert decision.status == "suggested"
        assert decision.schema_version == "inlet.initial-reported-rule-candidate.v1"
        assert (
            decision.action
            and decision.action.amount_micros == context.preview["after_budget_micros"]
        )
        reviewed = review_bridge.prepare_candidate_review(
            context.db,
            context.principal,
            wid,
            CandidateReviewIntent(result_id=result.id, expected_decision_digest=decision.digest()),
            review_bridge.CandidateReviewRuntime(runtime, native.execution, native.clock),
        )
        assert reviewed.status == "review_required"
        if change == "none":
            from app.lifecycle.export_serializers import serialize
            from app.optimization_candidates.models import CandidateJob

            for model, identifier in [(CandidateJob, job_id), (CandidateResult, result.id)]:
                stored = dict(
                    context.db.execute(
                        select(model.__table__).where(model.__table__.c.id == identifier)
                    )
                    .mappings()
                    .one()
                )
                exported, unavailable = serialize(model.__tablename__, stored)
                assert not unavailable and exported["workspace_id"] == wid
        assert context.db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert context.db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0

        if change != "none":
            from app.customers.models import CustomerSession
            from app.initial_planning.models import ObservationRow
            from fastapi import HTTPException
            from sqlalchemy.orm import Session

            context.db.commit()
            with Session(customer_engine) as other:
                if change == "session":
                    session = other.get(CustomerSession, context.principal.session.digest)
                    assert session
                    session.revoked_at = int(native.clock().timestamp())
                else:
                    erased = other.get(
                        ObservationRow, context.work.basis.observation_references[0].observation_id
                    )
                    assert erased
                    other.delete(erased)
                other.commit()
            guard = review_bridge.guard_for(
                review_bridge.CandidateReviewRuntime(runtime, native.execution, native.clock)
            )
            with pytest.raises(HTTPException):
                guard(context.db, wid, reviewed.review_id, context.principal.user.id, native.clock)
            context.db.rollback()
            assert (
                context.db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
            )
            assert (
                context.db.scalar(select(func.count()).select_from(ProviderExposureReservation))
                == 0
            )
