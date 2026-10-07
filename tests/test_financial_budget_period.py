"""Budget horizons deny folds/gaps but preserve ordinary DST elapsed durations."""

from datetime import UTC, date, datetime

import pytest
from app.goals.schemas import GoalDefinition
from app.publication.budget_period import financial_budget_period
from fastapi import HTTPException

from tests.test_customer_goals import definition


def goal(zone: str, start: date, end: date) -> GoalDefinition:
    value = definition("a" * 32)
    return value.model_copy(
        update={
            "budget_start": start,
            "budget_end": end,
            "target_window": value.target_window.model_copy(update={"time_zone": zone}),
            "baseline_window": value.baseline_window.model_copy(update={"time_zone": zone}),
        }
    )


@pytest.mark.parametrize(
    "zone,start,end",
    [
        ("America/Havana", date(2026, 11, 1), date(2026, 11, 2)),
        ("America/Havana", date(2026, 10, 31), date(2026, 11, 1)),
        ("Pacific/Apia", date(2011, 12, 30), date(2011, 12, 31)),
        ("Pacific/Apia", date(2011, 12, 29), date(2011, 12, 30)),
    ],
)
def test_ambiguous_or_nonexistent_either_boundary_denies(zone: str, start: date, end: date) -> None:
    with pytest.raises(HTTPException) as caught:
        financial_budget_period(goal(zone, start, end))
    assert caught.value.status_code == 409
    assert caught.value.detail == "financial_budget_period_unavailable"


@pytest.mark.parametrize(
    "start,end,hours,utc_hour",
    [
        (date(2026, 3, 8), date(2026, 3, 9), 23, 5),
        (date(2026, 11, 1), date(2026, 11, 2), 25, 4),
    ],
)
def test_ordinary_dst_days_preserve_exact_elapsed_time(
    start: date, end: date, hours: int, utc_hour: int
) -> None:
    before, after = financial_budget_period(goal("America/New_York", start, end))
    assert before == datetime(start.year, start.month, start.day, utc_hour, tzinfo=UTC)
    assert (after - before).total_seconds() == hours * 3600


def test_utc_unchanged() -> None:
    assert financial_budget_period(goal("UTC", date(2026, 10, 7), date(2026, 10, 8))) == (
        datetime(2026, 10, 7, tzinfo=UTC),
        datetime(2026, 10, 8, tzinfo=UTC),
    )
