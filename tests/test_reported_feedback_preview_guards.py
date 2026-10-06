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

from tests.reported_feedback_journey_fixture import acquired, baseline
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def test_real_feedback_idempotent_not_compounded_and_retracted_with_retained_finance(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        data, runtime, observation = acquired(db, configuration, tmp_path, monkeypatch)
        wid, principal, _, job, _, _, _, _, _, _, server = data
        runtime, initial = baseline(db, data, runtime, observation)
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
        assert len(server.posts) == 1
