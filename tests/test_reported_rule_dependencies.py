"""Actual source lineage erases only derived suggestions; financial history remains."""

from pathlib import Path
from uuid import uuid4

import pytest
from app.optimization_candidates.models import CandidateJob
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.reported_feedback.candidate_models import ReportedRuleCandidateDependency
from app.reported_feedback.models import ReportedActionComparison, ReportedWindowCapsule
from app.settings import Settings
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.reported_feedback_fixture import window_policy
from tests.reported_rule_fixture import ready_reported_rule
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("erasure", ["candidate", "comparison", "capsule", "supersede"])
def test_dependency_erasure_preserves_original_obligations(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    erasure: str,
) -> None:
    with Session(customer_engine) as db:
        principal, _, work, _, clock, _, _ = ready_reported_rule(
            db, configuration, tmp_path, monkeypatch
        )
        row = db.get(ReportedActionComparison, work.comparison_id)
        assert row
        job = CandidateJob(
            id=uuid4().hex,
            workspace_id=row.workspace_id,
            environment="contract_test",
            publication_id=work.scope.source.publication_id,
            attempt_id=row.original_attempt_id,
            actor_id=principal.user.id,
            auth_session_digest=principal.session.digest,
            input_digest=work.digest(),
            work=work.model_dump(mode="json"),
            state="pending",
            due_at=clock[0],
            created_at=clock[0],
            attempts=0,
        )
        db.add(job)
        db.flush()
        db.add(
            ReportedRuleCandidateDependency(
                candidate_job_id=job.id,
                workspace_id=row.workspace_id,
                account_id=row.account_id,
                campaign_id=row.campaign_id,
                comparison_id=row.id,
                acquisition_job_id=row.job_id,
            )
        )
        db.commit()
        before = [
            db.scalar(select(func.count()).select_from(model))
            for model in (ProviderExecutionAttempt, ProviderExposureReservation)
        ]
        held = db.scalar(select(ProviderExposureReservation))
        assert held and held.state == "held"
        amount = held.amount_micros
        if erasure == "candidate":
            import importlib

            from alembic.migration import MigrationContext
            from alembic.operations import Operations

            migration = importlib.import_module(
                "migrations.versions.20261007_0083_reported_rule_dependencies"
            )
            with (
                Operations.context(MigrationContext.configure(db.connection())),
                pytest.raises(RuntimeError, match="retained reported rule dependencies"),
            ):
                migration.downgrade()
            assert db.scalar(select(func.count()).select_from(ReportedRuleCandidateDependency)) == 1
        if erasure == "candidate":
            db.execute(delete(CandidateJob).where(CandidateJob.id == job.id))
        elif erasure == "comparison":
            db.execute(
                delete(ReportedActionComparison).where(ReportedActionComparison.id == row.id)
            )
        elif erasure == "capsule":
            capsule_id = row.document["before"]["capsules"][0]["id"]
            db.execute(delete(ReportedWindowCapsule).where(ReportedWindowCapsule.id == capsule_id))
        else:
            from app.initial_planning.runtime import InitialPlanningRuntime
            from app.reported_feedback.contracts import ComparisonIntentV1
            from app.reported_feedback.runtime import ReportedFeedbackRuntime
            from app.reported_feedback.service import request_comparison

            runtime = ReportedFeedbackRuntime(
                initial=InitialPlanningRuntime(
                    session_factory=lambda: Session(customer_engine), clock=lambda: clock[0]
                ),
                window_policy=window_policy(),
            )
            successor = request_comparison(
                db,
                principal,
                FakeProvider(),
                row.workspace_id,
                ComparisonIntentV1(
                    attempt_id=row.original_attempt_id,
                    goal_id=work.scope.goal_id,
                    goal_revision=work.scope.goal_revision,
                    maximum_reported_cpa_micros=90_000_000,
                ),
                runtime,
            )
            assert successor.id != row.job_id
            assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0
        db.commit()
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 0
        assert db.scalar(select(func.count()).select_from(ReportedRuleCandidateDependency)) == 0
        assert before == [
            db.scalar(select(func.count()).select_from(model))
            for model in (ProviderExecutionAttempt, ProviderExposureReservation)
        ]
        db.refresh(held)
        assert held.state == "held" and held.amount_micros == amount


def test_foreign_dependency_rejected(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        principal, _, work, _, clock, _, _ = ready_reported_rule(
            db, configuration, tmp_path, monkeypatch
        )
        row = db.get(ReportedActionComparison, work.comparison_id)
        assert row
        job = CandidateJob(
            id=uuid4().hex,
            workspace_id=row.workspace_id,
            environment="contract_test",
            publication_id=work.scope.source.publication_id,
            attempt_id=row.original_attempt_id,
            actor_id=principal.user.id,
            auth_session_digest=principal.session.digest,
            input_digest=work.digest(),
            work=work.model_dump(mode="json"),
            state="pending",
            due_at=clock[0],
            created_at=clock[0],
            attempts=0,
        )
        db.add(job)
        db.commit()
        with pytest.raises(DBAPIError, match="owned reported rule lineage required"):
            db.add(
                ReportedRuleCandidateDependency(
                    candidate_job_id=job.id,
                    workspace_id=row.workspace_id,
                    account_id=row.account_id + 100,
                    campaign_id=row.campaign_id,
                    comparison_id=row.id,
                    acquisition_job_id=row.job_id,
                )
            )
            db.commit()
        db.rollback()
        assert db.get(CandidateJob, job.id)
