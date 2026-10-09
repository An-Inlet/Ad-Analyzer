"""Relative fixture calendar: dates are chosen before the effect, never rewritten."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from tests.fixtures.retired_execution.reported_planning_relative_seed_driver import (
    RelativePlanningTimeline,
)


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        datetime(2028, 2, 29, 23, 59, 59, tzinfo=UTC),
        datetime(2028, 3, 1, tzinfo=UTC),
        datetime(2027, 2, 28, 23, 59, 59, tzinfo=UTC),
        datetime(2027, 3, 1, tzinfo=UTC),
        datetime(2031, 7, 16, 12, tzinfo=UTC),
        datetime(2031, 7, 31, 23, 59, 59, tzinfo=UTC),
    ],
)
def test_calendar_is_coherent_before_effect(value: datetime) -> None:
    timeline = RelativePlanningTimeline.from_as_of(value)
    assert timeline == RelativePlanningTimeline.from_as_of(value)
    assert timeline.as_of == value
    assert timeline.effect_at.date() == value.date() - timedelta(days=15)
    assert timeline.effect_at.hour == 12
    assert timeline.baseline_start.day == timeline.baseline_end.day == 1
    assert timeline.baseline_start < timeline.order_at.date() < timeline.baseline_end
    assert timeline.baseline_end <= timeline.effect_at.date()
    assert timeline.budget_start <= timeline.effect_at.date() < value.date()
    assert value.date() < timeline.target_start < timeline.target_end == timeline.budget_end
    assert timeline.target_start.day == timeline.target_end.day == 1
    after_end = timeline.effect_at.date() + timedelta(days=7)
    due = datetime.combine(after_end + timedelta(days=1), datetime.min.time(), UTC)
    due += timedelta(seconds=60)
    assert due < value
    assert (value + timedelta(seconds=63)).date() < timeline.budget_end
    assert (timeline.baseline_end - timeline.baseline_start).days in {28, 29, 30, 31}
    assert (timeline.target_end - timeline.target_start).days in {28, 29, 30, 31}


@pytest.mark.parametrize(
    "value", [datetime(2026, 10, 9), datetime(2026, 10, 9, tzinfo=timezone(timedelta(hours=1)))]
)
def test_calendar_rejects_non_utc_input(value: datetime) -> None:
    with pytest.raises(AssertionError):
        RelativePlanningTimeline.from_as_of(value)
