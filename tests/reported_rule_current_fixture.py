"""Current reports and candidate assembly over one genuine relative original effect."""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from app import advertising_capabilities
from app.meta.security import utc
from app.publication import optimization
from app.publication.execution_models import ProviderExecutionReview
from app.publication.optimization_contracts import MetaBudgetSetV1, MetaCurrentState
from app.publication.replacement_contracts import parse_review
from app.reported_feedback.contracts import ReportedWindowCapsuleV1
from app.reported_feedback.models import ReportedFeedbackJob, ReportedWindowCapsule
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import schema_snapshot
from tests.reported_original_fixture import RetainedReportedOriginalIds, prepare_reported_read
from tests.reported_planning_original_fixture import ExpectedPlanningConfirmation
from tests.reported_planning_relative_fixture import retained_reported_planning_relative_fixture
from tests.reported_read_acquisition_fixture import (
    PreparedReportedAcquisition,
    prepare_reported_acquisition,
)
from tests.reported_rule_fixture import _reported_rule_from_acquisition
from tests.test_social_optimization_http import Server


@pytest.fixture
def reported_rule_original(
    customer_engine: Engine, tmp_path: Path
) -> Iterator[RetainedReportedOriginalIds]:
    artifacts = tmp_path / "reported-rule-original"
    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink() and all(not p.is_symlink() for p in artifacts.parents)
    assert not advertising_capabilities.advertising_writes_enabled()
    schema = schema_snapshot(customer_engine)
    with retained_reported_planning_relative_fixture(
        customer_engine, artifacts, expectation=ExpectedPlanningConfirmation()
    ) as (engine, ids):
        assert engine is customer_engine and schema_snapshot(engine) == schema
        try:
            yield ids
        finally:
            assert not advertising_capabilities.advertising_writes_enabled()
            assert schema_snapshot(engine) == schema


def ready_current_reported_rule(
    db: Session,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    original: RetainedReportedOriginalIds,
    engine: Engine,
) -> tuple[Any, ...]:
    assert db.get_bind() is engine
    prepared = prepare_reported_read(db, original)
    run, _, _, request = optimization.evidence_lock(db, original.workspace_id, original.attempt_id)
    assert run.id == original.run_id and run.review_id == original.review_id
    review = db.get(ProviderExecutionReview, run.review_id)
    assert review and review.workspace_id == original.workspace_id
    document = parse_review(review.document)
    assert document.digest() == review.digest and document.plan.digest() == review.plan_digest
    assert isinstance(request.intent.action, MetaBudgetSetV1)
    assert (
        request.intent.action.budget_field == "daily_budget"
        and request.intent.action.amount_micros == 45_000_000
    )
    assert request.intent.scope.account.account_id == original.account_id
    assert request.intent.scope.workspace_id == original.workspace_id
    assert request.intent.scope.external_advertiser_id == "123"
    assert request.intent.target.kind == "campaign" and request.intent.target.external_id == "5"
    receipt = optimization.read_owned_outcome_receipt(
        db, original.workspace_id, original.attempt_id, original.actor_id
    )
    assert (
        receipt
        and receipt.receipt_id == original.receipt_id
        and receipt.outcome == "verified_target_state"
    )
    from app.publication.execution_models import ProviderExecutionReceipt
    from app.publication.optimization_contracts import OptimizationReceipt

    row = db.get(ProviderExecutionReceipt, original.receipt_id)
    assert row
    actual = OptimizationReceipt.model_validate(row.receipt)
    assert isinstance(actual.after, MetaCurrentState)
    assert (
        actual.after.scope == request.intent.scope and actual.after.target == request.intent.target
    )
    assert actual.after.money.currency == "USD" and actual.after.money.currency_exponent == 2
    assert actual.after.daily_budget_micros == 45_000_000
    server = Server("meta_ads")
    server.meta_campaign["daily_budget"] = "4500"
    assert server.posts == []
    acquired = prepare_reported_acquisition(db, config, prepared, monkeypatch)
    config.shopify_measurement_enabled = True
    data = (*acquired[:-1], server)
    page = acquired.runner.page
    completed = 0

    def current_page(
        wid: int, *, now: datetime | None = None, manual: bool = False
    ) -> dict[str, Any]:
        nonlocal completed
        assert wid == original.workspace_id
        result = page(wid, now=max(now or acquired.clock[0], acquired.clock[0]), manual=manual)
        completed = _follow_completed_clock(acquired, engine, original, result, completed)
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(acquired.runner, "page", current_page)
        result = _reported_rule_from_acquisition(db, config, data)
    assert server.posts == []
    return result


def _follow_completed_clock(
    acquired: PreparedReportedAcquisition,
    engine: Engine,
    original: RetainedReportedOriginalIds,
    result: dict[str, Any],
    previous: int,
) -> int:
    lease = acquired.runner._fixed_lease
    if result["status"] != "complete" or lease is None:
        return previous
    assert lease.job_id == acquired.job.id and lease.source_connection_id == original.source_id
    with Session(engine) as db:
        job = db.get(ReportedFeedbackJob, lease.job_id)
        assert job and job.completed_observations == previous + 1
        assert (job.workspace_id, job.account_id, job.campaign_id) == (
            original.workspace_id,
            original.account_id,
            original.campaign_id,
        )
        assert job.original_attempt_id == original.attempt_id
        assert job.original_actor_id == original.actor_id
        assert job.original_session_digest == original.session_digest
        assert job.state in {"waiting", "ready"} and job.native_run_id is None
        capsule = db.scalars(
            select(ReportedWindowCapsule).where(
                ReportedWindowCapsule.job_id == job.id,
                ReportedWindowCapsule.acquisition_run_id == lease.acquisition_run_id,
            )
        ).one()
        value = ReportedWindowCapsuleV1.model_validate(capsule.document)
        assert value.digest() == capsule.document_digest
        assert value.id == capsule.id and value.job_id == job.id
        assert value.completion_id == capsule.completion_id
        assert value.source_generation == capsule.source_generation
        assert job.source_generation == lease.source_generation
        assert job.source_connection_id == lease.source_connection_id
        assert lease.observation_ordinal == previous
        assert (capsule.workspace_id, capsule.account_id, capsule.campaign_id) == (
            job.workspace_id,
            job.account_id,
            job.campaign_id,
        )
        assert value.window == lease.window
        assert (capsule.starts_on, capsule.ends_on) == (
            lease.window.starts_on,
            lease.window.ends_on,
        )
        assert capsule.source_generation == lease.source_generation
        assert value.acquisition_run_id == lease.acquisition_run_id
        finished = utc(capsule.acquisition_completed_at)
        assert finished == value.acquisition_completed_at
        captured = utc(capsule.captured_at)
        assert captured == value.captured_at == utc(job.next_due_at)
        assert lease.acquisition_started_at <= finished <= captured
        acquired.clock[0] = max(acquired.clock[0], captured)
        return job.completed_observations
