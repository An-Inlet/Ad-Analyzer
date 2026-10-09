"""Real acquired evidence and baseline: idempotency, fresh policy, physical retraction."""

from dataclasses import replace
from pathlib import Path

import pytest
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExposureReservation,
)
from app.reported_feedback.contracts import FeedbackPreviewIntentV1
from app.reported_feedback.models import ReportedFeedbackSlot, ReportedWindowCapsule
from app.reported_feedback.service import (
    apply_feedback_preview,
    read_comparison,
    read_feedback_preview,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_planning_journey_fixture import (
    PlanningOrigin,
    acquired_current,
    baseline_current,
)
from tests.reported_planning_journey_fixture import planning_origin as planning_origin
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture(autouse=True)
def enforced_foreign_keys(customer_engine: Engine) -> None:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def test_real_feedback_idempotent_not_compounded_and_retracted_with_retained_finance(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    planning_origin: PlanningOrigin,
) -> None:
    with Session(customer_engine) as db:
        data, runtime, observation = acquired_current(
            db, configuration, tmp_path, monkeypatch, planning_origin
        )
        wid, principal, _, job, _, _, _, _, _, _, original = data
        runtime, initial, reads = baseline_current(
            db, data, runtime, observation, planning_origin, tmp_path, monkeypatch
        )
        comparison = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        intent = FeedbackPreviewIntentV1(
            comparison_id=comparison.id, baseline_preview_id=initial.id
        )
        first = apply_feedback_preview(db, principal, FakeProvider(), wid, intent, runtime)
        db.commit()
        second = apply_feedback_preview(db, principal, FakeProvider(), wid, intent, runtime)
        db.commit()
        assert second.id == first.id and second.delta_micros == first.delta_micros
        assert second.baseline_budget_micros == initial.after_budget_micros
        assert second.distinct_original_attempt_count == 1
        assert db.scalar(select(func.count()).select_from(ReportedFeedbackSlot)) == 1
        assert read_feedback_preview(db, principal, FakeProvider(), wid, first.id, runtime) == first
        assert runtime.feedback_policy is not None
        changed = replace(
            runtime, feedback_policy=runtime.feedback_policy.model_copy(update={"revision": 2})
        )
        with pytest.raises(HTTPException, match="policy_changed"):
            read_feedback_preview(db, principal, FakeProvider(), wid, first.id, changed)
        protected = tuple(
            db.scalar(select(func.count()).select_from(model))
            for model in (
                ProviderExecutionAttempt,
                ProviderExecutionReceipt,
                ProviderExposureReservation,
            )
        )
        capsule = db.get(ReportedWindowCapsule, comparison.before.capsules[0].id)
        assert capsule is not None
        db.delete(capsule)
        db.commit()
        assert db.scalar(select(func.count()).select_from(ReportedFeedbackSlot)) == 0
        with pytest.raises(HTTPException):
            read_feedback_preview(db, principal, FakeProvider(), wid, first.id, runtime)
        assert protected == tuple(
            db.scalar(select(func.count()).select_from(model))
            for model in (
                ProviderExecutionAttempt,
                ProviderExecutionReceipt,
                ProviderExposureReservation,
            )
        )
        assert original.original_post_count == 1
        reads.assert_read_only()


@pytest.mark.parametrize("erasure", ["pointer", "current_revision"])
def test_changed_mapping_appends_current_revision_without_invalidating_baseline(
    erasure: str,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    planning_origin: PlanningOrigin,
) -> None:
    from app.initial_planning.preview import read_preview
    from app.workspaces.models import Workspace

    with Session(customer_engine) as db:
        data, runtime, observation = acquired_current(
            db, configuration, tmp_path, monkeypatch, planning_origin
        )
        wid, principal, _, job, _, _, _, _, _, _, original = data
        runtime, initial, reads = baseline_current(
            db, data, runtime, observation, planning_origin, tmp_path, monkeypatch
        )
        comparison = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        intent = FeedbackPreviewIntentV1(
            comparison_id=comparison.id, baseline_preview_id=initial.id
        )
        first = apply_feedback_preview(db, principal, FakeProvider(), wid, intent, runtime)
        db.commit()
        space = db.get(Workspace, wid)
        assert space and runtime.feedback_policy
        before_revision = space.export_privacy_revision
        changed = replace(
            runtime,
            feedback_policy=runtime.feedback_policy.model_copy(
                update={"revision": 2, "maximum_preview_delta_micros": 1_000_000}
            ),
        )
        from app.lifecycle import privacy
        from app.reported_feedback.export import numeric_dependency_stamp
        from app.reported_feedback.models import ReportedFeedbackCurrent
        from app.reported_feedback.revisions import require_current_slot

        monkeypatch.setattr(privacy, "database_utc_now", lambda _: data[6][0])
        stamp = numeric_dependency_stamp(db, wid, validate=True)
        original_row = db.get(ReportedFeedbackSlot, first.id)
        assert original_row
        original_bytes = original_row.document.copy()
        second = apply_feedback_preview(db, principal, FakeProvider(), wid, intent, changed)
        db.commit()
        assert second.id != first.id and second.delta_micros != first.delta_micros
        retained_space = db.get(Workspace, wid)
        assert retained_space and retained_space.export_privacy_revision == before_revision
        assert db.scalar(select(func.count()).select_from(ReportedFeedbackSlot)) == 2
        original_row = db.get(ReportedFeedbackSlot, first.id)
        assert original_row and original_row.document == original_bytes
        assert (
            read_preview(db, principal, FakeProvider(), wid, initial.id, runtime.initial) == initial
        )
        assert (
            read_feedback_preview(db, principal, FakeProvider(), wid, second.id, changed) == second
        )
        with pytest.raises(HTTPException, match="superseded"):
            read_feedback_preview(db, principal, FakeProvider(), wid, first.id, runtime)
        assert numeric_dependency_stamp(db, wid, validate=True) != stamp
        assert apply_feedback_preview(db, principal, FakeProvider(), wid, intent, changed) == second
        db.commit()
        pointer = db.scalar(select(ReportedFeedbackCurrent))
        assert pointer and pointer.slot_id == second.id and pointer.revision == 2
        if erasure == "pointer":
            db.delete(pointer)
        else:
            current_row = db.get(ReportedFeedbackSlot, second.id)
            assert current_row
            db.delete(current_row)
        db.commit()
        old = db.get(ReportedFeedbackSlot, first.id)
        assert old
        with pytest.raises(HTTPException, match="pointer_unavailable"):
            require_current_slot(db, old)
        with pytest.raises(HTTPException):
            apply_feedback_preview(db, principal, FakeProvider(), wid, intent, changed)
        assert original.original_post_count == 1
        reads.assert_read_only()
