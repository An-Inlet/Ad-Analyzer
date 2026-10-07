"""Owned structural lifecycle fixture anchored to an actual offline Meta execution.

The new comparison/slot documents are synthetic contract values; this fixture does
not qualify report stability, policy, or the operational acquisition services.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.initial_planning.contracts import InitialPreviewV1
from app.initial_planning.models import ObservationRow, PreviewRow
from app.initial_planning.review_bridge import prepare_preview_review
from app.publication import customer_optimization, optimization
from app.publication.contracts import fingerprint
from app.publication.execution_models import ProviderExecutionReceipt
from app.reported_feedback.anchor import resolve_anchor
from app.reported_feedback.contracts import (
    CapsuleReferenceV1,
    OperationalReportedComparisonV1,
    ReportedAcquisitionRequestV1,
    ReportedFeedbackPolicyV1,
    ReportedFeedbackPreviewV1,
    ReportedWindowCapsuleV1,
    ReportedWindowPolicyV1,
    ReportedWindowSummaryV1,
    ReportWindowV1,
)
from app.reported_feedback.models import (
    ReportedActionComparison,
    ReportedComparisonDependency,
    ReportedFeedbackJob,
    ReportedFeedbackSlot,
    ReportedWindowCapsule,
)
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_initial_preview_review import ready


def graph(engine: Engine, configuration: Any, monkeypatch: Any, replicas: Any) -> dict[str, Any]:
    wid, preview, principal, provider, runtime, server, _ = ready(
        engine, configuration, monkeypatch, replicas
    )
    result = prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    bound = customer_optimization.bind(runtime.optimization, principal, provider)
    with Session(engine) as db:
        optimization.approve_optimization(
            db,
            wid,
            result.review_id,
            result.review_digest,
            result.plan_digest,
            principal.user.id,
            bound.execution,
            runtime.planning.clock,
        )
        run = optimization.create_run(
            db, wid, result.review_id, principal.user.id, bound.execution, runtime.planning.clock
        )
        claim = optimization.claim_step(
            db, wid, run.id, principal.user.id, bound.execution, runtime.planning.clock
        )
        assert claim
        optimization.execute_claim(
            db, claim, principal.user.id, bound.execution, runtime.planning.clock
        )
        now = datetime.now(UTC)
        anchor = resolve_anchor(db, wid, claim.attempt_id, principal.user.id, now)
        baseline = db.get(PreviewRow, preview.id)
        assert baseline
        initial = InitialPreviewV1.model_validate(baseline.document)
        observation = db.get(ObservationRow, baseline.observation_id)
        assert observation
        scope = dict(
            workspace_id=wid,
            account_id=anchor.cohort.account_id,
            campaign_id=anchor.cohort.campaign_id,
            environment=anchor.environment,
        )
        policy = ReportedWindowPolicyV1(
            policy_id=uuid4().hex,
            family=uuid4().hex,
            revision=1,
            environment="contract_test",
            selected_event=anchor.cohort.selected_event,
            query_version=anchor.cohort.query_version,
            window_days=7,
            minimum_close_age_seconds=0,
            distinct_repeat_completions=2,
            minimum_repeat_spacing_seconds=1,
            maximum_acquisition_age_seconds=86400,
            maximum_source_age_seconds=86400,
            daily_spend_absolute_tolerance_micros=0,
            daily_conversion_absolute_tolerance=Decimal(0),
            daily_relative_tolerance=Decimal(0),
            minimum_conversions=Decimal(1),
            minimum_spend_micros=1,
            retention_seconds=3600,
            maximum_capsules=16,
            maximum_requests=4,
            decision_lifetime_seconds=300,
        )
        before = ReportWindowV1(
            starts_on=(now - timedelta(days=21)).date(), ends_on=(now - timedelta(days=15)).date()
        )
        after = ReportWindowV1(
            starts_on=(now - timedelta(days=14)).date(), ends_on=(now - timedelta(days=8)).date()
        )
        request = ReportedAcquisitionRequestV1(
            id=uuid4().hex,
            anchor=anchor,
            objective=initial.objective,
            policy=policy,
            before=before,
            after=after,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        job = ReportedFeedbackJob(
            **scope,
            id=request.id,
            document=request.model_dump(mode="json"),
            document_digest=request.digest(),
            expires_at=request.expires_at,
            original_attempt_id=claim.attempt_id,
            original_actor_id=principal.user.id,
            original_session_digest=principal.session.digest,
            source_connection_id=anchor.source_connection_id,
            source_generation=anchor.source_generation,
            policy_family=policy.family,
            policy_digest=policy.digest(),
            input_digest="a" * 64,
            opportunity_digest=anchor.opportunity_digest(policy.family),
            state="ready",
            completed_observations=4,
            next_due_at=now,
            created_at=now,
            completed_at=now,
        )
        db.add(job)
        db.flush()
        capsule_doc = ReportedWindowCapsuleV1(
            id=uuid4().hex,
            job_id=job.id,
            acquisition_run_id=uuid4().hex,
            completion_id=observation.completion_id,
            completion_manifest_digest="b" * 64,
            environment="contract_test",
            cohort=anchor.cohort,
            source_generation=anchor.source_generation,
            captured_privacy_revision=0,
            policy_digest=policy.digest(),
            window=before,
            acquisition_started_at=now,
            acquisition_completed_at=now,
            captured_at=now,
            expires_at=request.expires_at,
            days=(),
        )
        capsule = ReportedWindowCapsule(
            **scope,
            id=capsule_doc.id,
            document=capsule_doc.model_dump(mode="json"),
            document_digest=capsule_doc.digest(),
            expires_at=capsule_doc.expires_at,
            job_id=job.id,
            completion_id=observation.completion_id,
            acquisition_run_id=capsule_doc.acquisition_run_id,
            source_generation=anchor.source_generation,
            starts_on=before.starts_on,
            ends_on=before.ends_on,
            acquisition_started_at=now,
            acquisition_completed_at=now,
            captured_at=now,
        )
        db.add(capsule)
        db.flush()
        comparisons = []
        for n in range(2):
            summary = ReportedWindowSummaryV1(
                window=before,
                capsules=(
                    CapsuleReferenceV1(
                        id=capsule.id,
                        digest=capsule.document_digest,
                        completion_id=capsule.completion_id,
                        acquired_at=now,
                    ),
                ),
                missing_dates=before.dates(),
                revisions_within_tolerance=False,
            )
            document = OperationalReportedComparisonV1(
                id=uuid4().hex,
                job_id=job.id,
                anchor=anchor,
                objective=initial.objective,
                policy_digest=policy.digest(),
                policy_family=policy.family,
                before=summary,
                after=summary.model_copy(update={"window": after, "missing_dates": after.dates()}),
                status="insufficient",
                reasons=("fixture_missing_dates",),
                relative_cpa_improvement=None,
                assessed_at=now,
                expires_at=now + timedelta(minutes=2),
            )
            row = ReportedActionComparison(
                **scope,
                id=document.id,
                document=document.model_dump(mode="json"),
                document_digest=document.digest(),
                expires_at=document.expires_at,
                job_id=job.id,
                original_attempt_id=claim.attempt_id,
                receipt_id=anchor.latest_receipt_id,
                receipt_sequence=anchor.latest_receipt_sequence,
                policy_family=policy.family,
                input_digest=str(n + 1) * 64,
                assessed_at=now,
            )
            db.add(row)
            db.flush()
            db.add(
                ReportedComparisonDependency(
                    workspace_id=wid,
                    account_id=row.account_id,
                    campaign_id=row.campaign_id,
                    comparison_id=row.id,
                    capsule_id=capsule.id,
                )
            )
            comparisons.append(row)
        feedback = ReportedFeedbackPolicyV1(
            policy_id=uuid4().hex,
            family=policy.family,
            revision=1,
            environment="contract_test",
            comparison_policy_digest=policy.digest(),
            original_change="increase",
            favorable_direction="increase",
            unfavorable_direction="decrease",
            minimum_distinct_original_attempts=1,
            neutral_band=Decimal("0.1"),
            weight=Decimal("0.1"),
            contribution_clamp=Decimal("0.1"),
            aggregate_clamp=Decimal("0.2"),
            maximum_preview_delta_micros=1000000,
            lifetime_seconds=120,
        )
        doc = ReportedFeedbackPreviewV1(
            id=uuid4().hex,
            environment="contract_test",
            cohort=anchor.cohort,
            policy=feedback,
            comparison_id=comparisons[0].id,
            comparison_digest=comparisons[0].document_digest,
            baseline_preview_id=baseline.id,
            baseline_preview_digest=initial.digest(),
            opportunity_digest=job.opportunity_digest,
            active_set_digest=fingerprint("fixture", {}),
            policy_digest=feedback.digest(),
            distinct_original_attempt_count=1,
            before_reported_cpa_micros=Decimal(10),
            after_reported_cpa_micros=Decimal(10),
            baseline_budget_micros=10000000,
            delta_micros=0,
            proposed_budget_micros=10000000,
            explanation=("synthetic_storage_only",),
            created_at=now,
            expires_at=min(initial.expires_at, comparisons[0].expires_at),
        )
        slot = ReportedFeedbackSlot(
            **scope,
            id=doc.id,
            document=doc.model_dump(mode="json"),
            document_digest=doc.digest(),
            expires_at=doc.expires_at,
            comparison_id=comparisons[0].id,
            baseline_preview_id=baseline.id,
            original_attempt_id=claim.attempt_id,
            original_actor_id=principal.user.id,
            original_session_digest=principal.session.digest,
            policy_family=policy.family,
            cohort_digest=anchor.cohort.digest(),
            opportunity_digest=job.opportunity_digest,
            revision=1,
            created_at=now,
        )
        from app.reported_feedback.revisions import append_revision

        append_revision(db, slot)
        db.commit()
        assert db.get(ProviderExecutionReceipt, anchor.latest_receipt_id)
        return dict(
            wid=wid,
            job=job.id,
            capsule=capsule.id,
            comparisons=[r.id for r in comparisons],
            slot=slot.id,
            session=principal.session.digest,
            receipt=anchor.latest_receipt_id,
            account=anchor.cohort.account_id,
            now=now,
        )
