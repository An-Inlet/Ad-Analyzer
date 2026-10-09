"""Genuine current V1 baseline retains planning confirmation without execution consent."""

from pathlib import Path

import pytest
from app.initial_planning.contracts import InitialPreviewV1, PreviewIntentV1
from app.initial_planning.models import PreviewRow
from app.initial_planning.preview import read_preview
from app.reported_feedback.contracts import FeedbackPreviewIntentV1
from app.reported_feedback.service import apply_feedback_preview, read_comparison
from app.settings import Settings
from sqlalchemy import Engine
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


def test_actual_v1_planning_confirmation_baseline_and_feedback(
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
        runtime, initial, reads = baseline_current(
            db, data, runtime, observation, planning_origin, tmp_path, monkeypatch
        )
        assert type(initial) is InitialPreviewV1
        row = db.get(PreviewRow, initial.id)
        assert row is not None
        intent = PreviewIntentV1.model_validate(row.intent)
        assert intent.mandate_id != planning_origin.ids.mandate_id
        assert (
            read_preview(
                db, data.principal, FakeProvider(), data.workspace_id, initial.id, runtime.initial
            )
            == initial
        )
        comparison = read_comparison(
            db, data.principal, FakeProvider(), data.workspace_id, data.job.id, runtime
        )
        feedback = apply_feedback_preview(
            db,
            data.principal,
            FakeProvider(),
            data.workspace_id,
            FeedbackPreviewIntentV1(comparison_id=comparison.id, baseline_preview_id=initial.id),
            runtime,
        )
        db.commit()
        assert (feedback.baseline_budget_micros, feedback.proposed_budget_micros) == (
            46_000_000,
            47_000_000,
        )
        assert planning_origin.ids.original_post_count == 1
        reads.assert_read_only()
