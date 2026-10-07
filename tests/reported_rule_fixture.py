"""Real original HTTP operation and four completed Meta report acquisitions."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.commerce.evidence import digest as source_digest
from app.commerce.models import CommerceMeasurementPublication, CommerceStore
from app.commerce.sync import CommerceSyncService
from app.executors.meta_optimization import MetaOptimizationTransport
from app.goals import service as goals
from app.optimization_candidates.contracts import (
    CandidateEvidence,
    CandidateObservation,
    CandidateScope,
    SourceFence,
)
from app.optimization_candidates.selection_contracts import SelectionProvenance
from app.publication.contracts import fingerprint
from app.publication.coordinator import read_owned_outcome_receipt
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExecutionRun,
)
from app.publication.optimization_contracts import (
    MetaCurrentState,
    OptimizationContext,
    OptimizationReceipt,
)
from app.publication.replacement_contracts import parse_review
from app.reported_feedback.candidate_contracts import ReportedRulePolicyV1, ReportedRuleWorkV1
from app.reported_feedback.service import read_comparison
from app.settings import Settings
from app.shopify.models import ShopifyConnection
from app.workspaces.models import Workspace
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tests.reported_feedback_fixture import feedback_policy
from tests.test_commerce_measurement import NOW, FakeMeasurement
from tests.test_customer_identity import FakeProvider
from tests.test_reported_feedback_acquisition import acquisition_fixture, complete


def ready_reported_rule(
    db: Session,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    execution_out: list[Any] | None = None,
) -> tuple[Any, ...]:
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON"))
    from tests import reported_feedback_fixture
    from tests.test_durable_optimization import ready as actual_ready

    def recorded(*args, **kwargs):  # type: ignore[no-untyped-def]
        result = actual_ready(*args, **kwargs)
        if execution_out is not None:
            execution_out.append(result[6])
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(reported_feedback_fixture, "ready", recorded)
        wid, principal, runtime, job, _, _, clock, runner, requests, control, server = (
            acquisition_fixture(db, config, path, monkeypatch, period_end=NOW + timedelta(days=30))
        )
    control.update(before_conversions="2", after_conversions="4")
    for _ in range(3):
        complete(runner, wid, clock[0])
    clock[0] += timedelta(seconds=61)
    for _ in range(2):
        complete(runner, wid, clock[0])
    comparison = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
    db.commit()
    receipt_row = db.get(ProviderExecutionReceipt, comparison.anchor.latest_receipt_id)
    assert receipt_row
    receipt = OptimizationReceipt.model_validate(receipt_row.receipt)
    assert isinstance(receipt.after, MetaCurrentState)
    original = receipt.after
    adapter = MetaOptimizationTransport(transport=httpx.MockTransport(server))
    state = adapter.read_current(
        original.scope,
        original.target,
        original.money,
        original.qualification_id,
        original.qualification_revision,
        OptimizationContext(
            scope=original.scope,
            access_token=SecretStr("offline-token"),
            expires_at=clock[0] + timedelta(hours=1),
        ),
        clock[0],
    )
    attempt = db.get(ProviderExecutionAttempt, receipt_row.attempt_id)
    assert attempt
    run = db.get(ProviderExecutionRun, attempt.run_id)
    assert run
    review = db.get(ProviderExecutionReview, run.review_id)
    assert review
    document = parse_review(review.document)
    projection = read_owned_outcome_receipt(db, wid, attempt.id, principal.user.id)
    assert projection
    shop = db.scalar(select(ShopifyConnection).where(ShopifyConnection.workspace_id == wid))
    assert shop
    store = db.get(CommerceStore, shop.commerce_store_id)
    assert store
    db.commit()
    CommerceSyncService(db, config, FakeMeasurement(config, [([], None)])).page(wid, now=clock[0])
    publication = db.scalar(
        select(CommerceMeasurementPublication)
        .where(CommerceMeasurementPublication.workspace_id == wid)
        .order_by(CommerceMeasurementPublication.publication_revision.desc())
    )
    workspace = db.get(Workspace, wid)
    assert publication and workspace
    goal = goals.owned(db, wid, comparison.anchor.goal_id)
    scope = CandidateScope(
        account=state.scope,
        mandate=document.plan.intent.mandate,
        goal_id=goal.id,
        goal_revision=goal.revision,
        goal_digest=fingerprint(
            "inlet.optimization-goal.v1", {"definition": goals.current(db, goal).definition}
        ),
        target=state.target,
        budget_owner_key=state.budget_owner.key(state.scope),
        target_set_digest=state.budget_owner.target_set_digest(),
        source=SourceFence(
            workspace_privacy_revision=workspace.export_privacy_revision,
            store_id=publication.store_id,
            publication_id=publication.id,
            generation=publication.generation,
            privacy_epoch=publication.privacy_epoch,
            publication_revision=publication.publication_revision,
            source_revision=publication.source_revision,
            manifest_digest=publication.manifest_digest,
            attempt_id=attempt.id,
            receipt_id=projection.receipt_id,
            receipt_sequence=projection.sequence,
            receipt_digest=projection.receipt_digest,
            projection_digest=source_digest(
                ["inlet.owned-receipt.v1", projection.model_dump(mode="json")]
            ),
        ),
    )
    rule = ReportedRulePolicyV1(
        workspace_id=wid,
        environment="contract_test",
        policy_id="8" * 32,
        revision=1,
        policy_family="9" * 32,
        feedback_policy=feedback_policy(),
        comparison_policy_digest=comparison.policy_digest,
        allowed_operation="meta_budget_set_v1",
        maximum_candidate_age_seconds=60,
    )
    work = ReportedRuleWorkV1(
        scope=scope,
        policy=rule,
        comparison_id=comparison.id,
        selection=SelectionProvenance(
            actor_id=principal.user.id,
            scope_digest=scope.digest(),
            policy_digest=rule.digest(),
            catalog_digest="a" * 64,
            option_id="b" * 64,
            state_digest=state.digest(),
            manifest_digest="c" * 64,
            observed_at=clock[0],
            expires_at=clock[0] + timedelta(seconds=60),
        ),
    )
    observation = CandidateObservation(
        scope=scope,
        state=state,
        evidence=CandidateEvidence(
            scope_digest=scope.digest(),
            source_schema="native_test_observation",
            source_digest="d" * 64,
            source_reference=publication.id,
            qualification="unqualified",
            direction="none",
            observed_at=clock[0],
            expires_at=clock[0] + timedelta(seconds=60),
        ),
    )
    return principal, FakeProvider(), work, observation, clock, requests, server
