from datetime import UTC, date, datetime
from typing import Any

import pytest
from app.goals.progress_contracts import ClosedDayCoverageV1, GoalSalesProgressV1
from pydantic import ValidationError


def available(amount: int) -> GoalSalesProgressV1:
    return GoalSalesProgressV1(
        workspace_id=1, goal_id="a" * 32, revision=1, definition_digest="b" * 64,
        status="available_as_of",
        target_window={"start": "2026-03-01", "end": "2026-04-01",
                       "time_basis": "calendar_month", "currency": "USD",
                       "time_zone": "America/New_York"},
        target_micros=100000000, store_id="c" * 32, currency="USD",
        time_zone="America/New_York",
        coverage=ClosedDayCoverageV1(
            starts_on=date(2026, 3, 1), ends_on_exclusive=date(2026, 3, 9),
            starts_at=datetime(2026, 3, 1, 5, tzinfo=UTC),
            ends_at_exclusive=datetime(2026, 3, 9, 4, tzinfo=UTC), closed_day_count=8,
            extent="partial_period",
        ),
        net_sales_micros=amount, source_watermark=datetime(2026, 3, 9, 6, tzinfo=UTC),
        source_revision=4, import_in_progress=False,
        as_of=datetime(2026, 3, 9, 7, tzinfo=UTC), reasons=(),
    )


@pytest.mark.parametrize("amount", [0, -1000000, 50000000, 200000000])
def test_signed_as_of_values_never_imply_achievement(amount: int) -> None:
    value = available(amount)
    assert value.net_sales_micros == amount
    assert value.goal_achievement == "not_assessed" and not value.spending_authorized
    assert value.target_window and value.target_window.time_basis == "calendar_month"
    assert value.coverage and value.coverage.closed_day_count == 8
    duration = value.coverage.ends_at_exclusive - value.coverage.starts_at
    assert duration.total_seconds() == 191 * 3600


@pytest.mark.parametrize("change", [
    {"status": "unavailable", "reasons": ["missing_history"]},
    {"net_sales_micros": None}, {"reasons": ["privacy_suppressed_source"]},
    {"source_watermark": "2026-03-09T03:00:00Z"}, {"import_in_progress": True},
    {"currency": "EUR"}, {"spending_authorized": True},
])
def test_partial_or_unavailable_evidence_cannot_be_labeled_available(
    change: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        GoalSalesProgressV1.model_validate({**available(100).model_dump(), **change})
