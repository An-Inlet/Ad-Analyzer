"""Explicit fixture sensitivity is not empirical policy qualification."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.initial_planning.calibration import classify, evaluate
from app.initial_planning.contracts import (
    CohortV1,
    EfficiencyObjectiveV1,
    InitialPlanningConfiguration,
    ObservationV1,
)
from fastapi import HTTPException

from tests.test_initial_planning_contracts import rule

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


def policy(**changes: object) -> InitialPlanningConfiguration:
    return InitialPlanningConfiguration.model_validate(
        dict(
            environment="contract_test",
            policy_family="a" * 32,
            revision=1,
            retention_seconds=864000,
            maximum_observations=16,
            minimum_training_windows=1,
            minimum_holdout_windows=1,
            maximum_report_age_seconds=864000,
            minimum_report_age_seconds=0,
            preview_lifetime_seconds=300,
            selected_rule="fixture",
            supported_event="purchase",
            rules=[rule()],
            **changes,
        )
    )


def observation(month: int, **changes: object) -> ObservationV1:
    return ObservationV1.model_validate(
        dict(
            id=uuid4().hex,
            cohort=CohortV1(
                workspace_id=1,
                account_id=1,
                campaign_id=1,
                selected_event="purchase",
                currency="USD",
                time_zone="UTC",
                query_version="fixture",
            ),
            environment="contract_test",
            completion_id=uuid4().hex,
            manifest_digest="a" * 64,
            generation=1,
            privacy_revision=0,
            starts_on=date(2026, month, 1),
            ends_on=date(2026, month, 28),
            completed_at=NOW - timedelta(hours=10 - month),
            captured_at=NOW - timedelta(hours=10 - month),
            expires_at=NOW + timedelta(days=1),
            retention_policy_digest=policy().digest(),
            reported_day_count=1,
            impressions=100,
            clicks=10,
            spend_micros=1000000,
            conversions="10",
            conversion_value_micros=None,
            **changes,
        )
    )


def objective(item: ObservationV1) -> EfficiencyObjectiveV1:
    return EfficiencyObjectiveV1(
        cohort=item.cohort, goal_id="b" * 32, goal_revision=1, maximum_reported_cpa_micros=1000000
    )


def test_replay_reproducible_revisions_not_independent() -> None:
    first, second = observation(7), observation(8)
    revision = second.model_copy(
        update={
            "id": uuid4().hex,
            "captured_at": NOW - timedelta(minutes=5),
            "conversions": Decimal("0"),
        }
    )
    report = evaluate((revision, second, first), objective(first), policy(), NOW)
    again = evaluate((first, second, revision), objective(first), policy(), NOW)
    assert report.status == "evaluated" and report.input_digest == again.input_digest
    assert report.training_windows == report.holdout_windows == 1
    assert report.rules[0].increase_count == 2 and report.rules[0].revision_direction_changes == 1
    assert not report.empirical_qualification and not report.spending_authorized


@pytest.mark.parametrize("value", [None, Decimal(0)])
def test_unknown_and_zero_conversion_no_cpa(value: Decimal | None) -> None:
    item = observation(7).model_copy(update={"conversions": value})
    assert classify(item, objective(item), rule()) == "insufficient"


@pytest.mark.parametrize("case", ["expired", "future", "overlap", "order"])
def test_ineligible_facts_are_explicit(case: str) -> None:
    first, second = observation(7), observation(8)
    if case == "expired":
        first = first.model_copy(update={"expires_at": NOW})
    if case == "future":
        first = first.model_copy(update={"captured_at": NOW + timedelta(seconds=1)})
    if case == "overlap":
        second = second.model_copy(update={"starts_on": first.ends_on})
    if case == "order":
        first = first.model_copy(update={"captured_at": NOW - timedelta(minutes=1)})
    result = evaluate((first, second), objective(first), policy(), NOW)
    assert result.status == "insufficient" and result.reasons and result.expires_at > NOW


def test_calendar_overflow_controlled() -> None:
    item = observation(7).model_copy(update={"ends_on": date.max})
    with pytest.raises(HTTPException, match="calendar"):
        evaluate((item,), objective(item), policy(), NOW)
