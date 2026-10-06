"""Daily repeat coverage, correction and explicit bounded feedback arithmetic."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.initial_planning.contracts import EfficiencyObjectiveV1
from app.reported_feedback.contracts import (
    ReportedAcquisitionRequestV1,
    ReportedDayV1,
    ReportedFeedbackPolicyV1,
    ReportedWindowCapsuleV1,
    ReportWindowV1,
)
from app.reported_feedback.evaluator import bounded_delta, compare

from tests.reported_feedback_fixture import window_policy
from tests.test_reported_feedback_contracts import NOW, anchor


def evidence() -> tuple[
    ReportedAcquisitionRequestV1, tuple[ReportedWindowCapsuleV1, ...], datetime
]:
    a = anchor()
    p = window_policy().model_copy(update={"selected_event": a.cohort.selected_event})
    request = ReportedAcquisitionRequestV1(
        id="9" * 32,
        anchor=a,
        objective=EfficiencyObjectiveV1(
            cohort=a.cohort,
            goal_id=a.goal_id,
            goal_revision=1,
            maximum_reported_cpa_micros=10_000_000,
        ),
        policy=p,
        before=ReportWindowV1(starts_on=date(2026, 9, 29), ends_on=date(2026, 10, 5)),
        after=ReportWindowV1(starts_on=date(2026, 10, 7), ends_on=date(2026, 10, 13)),
        created_at=NOW,
        expires_at=NOW + timedelta(days=20),
    )
    first = NOW + timedelta(days=9)
    capsules = tuple(
        ReportedWindowCapsuleV1(
            id=uuid4().hex,
            job_id=request.id,
            acquisition_run_id=uuid4().hex,
            completion_id=uuid4().hex,
            completion_manifest_digest="a" * 64,
            environment=a.environment,
            cohort=a.cohort,
            source_generation=a.source_generation,
            captured_privacy_revision=0,
            policy_digest=p.digest(),
            window=w,
            acquisition_started_at=first + timedelta(minutes=i),
            acquisition_completed_at=first + timedelta(minutes=i, seconds=1),
            captured_at=first + timedelta(minutes=i, seconds=1),
            expires_at=request.expires_at,
            days=tuple(
                ReportedDayV1(
                    day=d,
                    spend_micros=100_000_000,
                    conversions=Decimal(10 if w == request.before else 20),
                    conversion_value_micros=None,
                )
                for d in w.dates()
            ),
        )
        for i, w in enumerate((request.before, request.after, request.before, request.after))
    )
    return request, capsules, first + timedelta(minutes=4)


def test_actual_repeat_count_daily_values_and_bounded_expiry() -> None:
    request, capsules, now = evidence()
    value = compare(request, capsules, now)
    assert value.status == "operational_reported_as_of"
    assert value.relative_cpa_improvement == Decimal("0.5")
    assert value.before.reported_cpa_micros == 10_000_000
    assert value.after.reported_cpa_micros == 5_000_000
    assert value.causal_lift == value.delivery_time == "unavailable"
    assert value.spending_authority == "none"
    policy = request.policy.model_copy(update={"maximum_source_age_seconds": 125})
    request = request.model_copy(update={"policy": policy})
    capsules = tuple(c.model_copy(update={"policy_digest": policy.digest()}) for c in capsules)
    value = compare(request, capsules, now)
    assert value.expires_at == capsules[2].acquisition_completed_at + timedelta(seconds=125)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("missing", "reported_days_missing"),
        ("correction", "reported_revision_outside_tolerance"),
        ("spacing", "repeat_spacing_unavailable"),
        ("old", "acquisition_age_unavailable"),
        ("zero", "reported_conversions_insufficient"),
    ],
)
def test_insufficient_never_emits_numeric_feedback(change: str, reason: str) -> None:
    request, capsules, now = evidence()
    values = list(capsules)
    if change == "missing":
        values[0] = values[0].model_copy(update={"days": values[0].days[1:]})
    if change == "correction":
        days = (
            values[0].days[0].model_copy(update={"spend_micros": 100_000_001}),
            *values[0].days[1:],
        )
        values[0] = values[0].model_copy(update={"days": days})
    if change == "spacing":
        values[2] = values[2].model_copy(
            update={"acquisition_started_at": values[0].acquisition_completed_at}
        )
    if change == "old":
        now += timedelta(days=2)
    if change == "zero":
        values = [
            c.model_copy(
                update={
                    "days": tuple(d.model_copy(update={"conversions": Decimal(0)}) for d in c.days)
                }
            )
            for c in values
        ]
    result = compare(request, tuple(values), now)
    assert result.status == "insufficient" and result.relative_cpa_improvement is None
    assert reason in result.reasons


def test_recapture_foreign_generation_and_duplicate_completion_rejected() -> None:
    request, capsules, now = evidence()
    for update in (
        {"source_generation": 2},
        {"job_id": "f" * 32},
        {"completion_id": capsules[0].completion_id},
    ):
        values = (*capsules[:2], capsules[2].model_copy(update=update), capsules[3])
        with pytest.raises(ValueError):
            compare(request, values, now)


def test_one_original_attempt_and_clamped_recomputed_delta() -> None:
    request, capsules, now = evidence()
    value = compare(request, capsules, now)
    policy = ReportedFeedbackPolicyV1(
        policy_id="1" * 32,
        family="2" * 32,
        revision=1,
        environment="contract_test",
        comparison_policy_digest=request.policy.digest(),
        original_change="increase",
        favorable_direction="increase",
        unfavorable_direction="decrease",
        minimum_distinct_original_attempts=1,
        neutral_band=Decimal("0.01"),
        weight=Decimal("0.5"),
        contribution_clamp=Decimal("0.1"),
        aggregate_clamp=Decimal("0.05"),
        maximum_preview_delta_micros=1_000_000,
        lifetime_seconds=60,
    )
    assert bounded_delta((value,), policy) == 50_000
    assert bounded_delta((value,), policy) == 50_000
    with pytest.raises(ValueError, match="distinct"):
        bounded_delta((value, value.model_copy(update={"id": uuid4().hex})), policy)


def test_exact_source_freshness_boundary_becomes_insufficient() -> None:
    request, capsules, now = evidence()
    policy = request.policy.model_copy(update={"maximum_source_age_seconds": 125})
    request = request.model_copy(update={"policy": policy})
    capsules = tuple(c.model_copy(update={"policy_digest": policy.digest()}) for c in capsules)
    boundary = capsules[2].acquisition_completed_at + timedelta(seconds=125)
    result = compare(request, capsules, boundary)
    assert result.status == "insufficient" and "latest_report_expired" in result.reasons
    assert result.relative_cpa_improvement is None


def test_repeating_cpa_does_not_round_exact_relative_change_down() -> None:
    request, capsules, now = evidence()
    capsules = tuple(
        c.model_copy(
            update={
                "days": tuple(
                    d.model_copy(
                        update={"conversions": Decimal(3 if c.window == request.before else 6)}
                    )
                    for d in c.days
                )
            }
        )
        for c in capsules
    )
    value = compare(request, capsules, now)
    assert value.relative_cpa_improvement == Decimal("0.5")
