"""Explicit operational report stability; no provider finality or causal inference."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.reported_feedback.contracts import (
    CapsuleReferenceV1,
    OperationalReportedComparisonV1,
    ReportedAcquisitionRequestV1,
    ReportedFeedbackPolicyV1,
    ReportedWindowCapsuleV1,
    ReportedWindowPolicyV1,
    ReportedWindowSummaryV1,
    ReportWindowV1,
)


def midnight(day: date, zone: str) -> datetime:
    return datetime.combine(day, time.min, ZoneInfo(zone)).astimezone(UTC)


def stable(values: list[Decimal], absolute: Decimal, relative: Decimal) -> bool:
    low, high = min(values), max(values)
    return high - low <= max(absolute, abs(low) * relative)


def summarize(
    window: ReportWindowV1,
    capsules: list[ReportedWindowCapsuleV1],
    policy: ReportedWindowPolicyV1,
    now: datetime,
) -> tuple[ReportedWindowSummaryV1, set[str]]:
    if not capsules:
        raise ValueError("at least one actual observation per window required")
    capsules = sorted(capsules, key=lambda c: (c.acquisition_completed_at, c.id))
    if len(capsules) > 8 or any(c.window != window for c in capsules):
        raise ValueError("bounded same-window observations required")
    reasons: set[str] = set()
    if len({c.completion_id for c in capsules}) != len(capsules) or len(
        {c.acquisition_run_id for c in capsules}
    ) != len(capsules):
        raise ValueError("one completion and acquisition per repeat required")
    if len(capsules) < policy.distinct_repeat_completions:
        reasons.add("repeat_observations_unavailable")
    if any(
        (b.acquisition_started_at - a.acquisition_completed_at).total_seconds()
        < policy.minimum_repeat_spacing_seconds
        for a, b in zip(capsules, capsules[1:], strict=False)
    ):
        reasons.add("repeat_spacing_unavailable")
    if any(
        c.acquisition_started_at
        < midnight(window.ends_on + timedelta(days=1), c.cohort.time_zone)
        + timedelta(seconds=policy.minimum_close_age_seconds)
        for c in capsules
    ):
        reasons.add("acquisition_started_before_closed_window_age")
    if any(
        not 0
        <= (now - c.acquisition_completed_at).total_seconds()
        < policy.maximum_acquisition_age_seconds
        for c in capsules
    ):
        reasons.add("acquisition_age_unavailable")
    if (
        not 0
        <= (now - capsules[-1].acquisition_completed_at).total_seconds()
        < policy.maximum_source_age_seconds
    ):
        reasons.add("latest_report_expired")
    if any(now >= c.expires_at for c in capsules):
        raise ValueError("expired capsule cannot produce a current assessment")
    missing = tuple(sorted({day for c in capsules for day in c.missing_dates()}))
    if missing:
        reasons.add("reported_days_missing")
    revisions = not missing
    if revisions:
        for day in window.dates():
            points = [next(p for p in c.days if p.day == day) for c in capsules]
            if not stable(
                [Decimal(p.spend_micros) for p in points],
                Decimal(policy.daily_spend_absolute_tolerance_micros),
                policy.daily_relative_tolerance,
            ) or not stable(
                [p.conversions for p in points],
                policy.daily_conversion_absolute_tolerance,
                policy.daily_relative_tolerance,
            ):
                revisions = False
    if not revisions and not missing:
        reasons.add("reported_revision_outside_tolerance")
    latest = capsules[-1]
    spend = sum(p.spend_micros for p in latest.days) if not latest.missing_dates() else None
    conversions = (
        sum((p.conversions for p in latest.days), Decimal(0)) if spend is not None else None
    )
    cpa = Decimal(spend) / conversions if spend is not None and conversions else None
    if conversions is None or conversions < policy.minimum_conversions:
        reasons.add("reported_conversions_insufficient")
    if spend is None or spend < policy.minimum_spend_micros:
        reasons.add("reported_spend_insufficient")
    return ReportedWindowSummaryV1(
        window=window,
        capsules=tuple(
            CapsuleReferenceV1(
                id=c.id,
                digest=c.digest(),
                completion_id=c.completion_id,
                acquired_at=c.acquisition_completed_at,
            )
            for c in capsules
        ),
        missing_dates=missing,
        spend_micros=spend,
        conversions=conversions,
        reported_cpa_micros=cpa,
        revisions_within_tolerance=revisions,
    ), reasons


def compare(
    request: ReportedAcquisitionRequestV1,
    capsules: tuple[ReportedWindowCapsuleV1, ...],
    now: datetime,
) -> OperationalReportedComparisonV1:
    request = ReportedAcquisitionRequestV1.model_validate(request.model_dump())
    policy, anchor = request.policy, request.anchor
    if now >= request.expires_at or now < request.created_at:
        raise ValueError("request expired or future")
    if len(capsules) > 16 or any(
        c.job_id != request.id
        or c.cohort != anchor.cohort
        or c.environment != anchor.environment
        or c.source_generation != anchor.source_generation
        or c.policy_digest != policy.digest()
        or c.window not in (request.before, request.after)
        for c in capsules
    ):
        raise ValueError("owned acquisition capsule set required")
    with localcontext() as context:
        context.prec = 40
        before, left = summarize(
            request.before, [c for c in capsules if c.window == request.before], policy, now
        )
        after, right = summarize(
            request.after, [c for c in capsules if c.window == request.after], policy, now
        )
        reasons = left | right
        if (
            midnight(request.before.ends_on + timedelta(days=1), anchor.cohort.time_zone)
            > anchor.dispatched_at
            or midnight(request.after.starts_on, anchor.cohort.time_zone)
            < anchor.configuration_observed_at
        ):
            reasons.add("window_overlaps_configuration_observation_bracket")
        improvement = None
        if not reasons:
            assert before.reported_cpa_micros is not None and after.reported_cpa_micros is not None
            if before.reported_cpa_micros <= 0:
                reasons.add("before_cpa_undefined")
            else:
                improvement = (
                    before.reported_cpa_micros - after.reported_cpa_micros
                ) / before.reported_cpa_micros
        expiry = min(
            request.expires_at,
            now + timedelta(seconds=policy.decision_lifetime_seconds),
            *(c.expires_at for c in capsules),
        )
        if not reasons:
            expiry = min(
                expiry,
                *(
                    c.acquisition_completed_at
                    + timedelta(seconds=policy.maximum_acquisition_age_seconds)
                    for c in capsules
                ),
                *(
                    max(c.acquisition_completed_at for c in capsules if c.window == window)
                    + timedelta(seconds=policy.maximum_source_age_seconds)
                    for window in (request.before, request.after)
                ),
            )
            if expiry <= now:
                raise ValueError("report freshness boundary reached")
        return OperationalReportedComparisonV1(
            id=uuid4().hex,
            job_id=request.id,
            anchor=anchor,
            objective=request.objective,
            policy_digest=policy.digest(),
            policy_family=policy.family,
            before=before,
            after=after,
            status="insufficient" if reasons else "operational_reported_as_of",
            reasons=tuple(sorted(reasons)),
            relative_cpa_improvement=improvement,
            assessed_at=now,
            expires_at=expiry,
        )


def bounded_delta(
    values: tuple[OperationalReportedComparisonV1, ...], policy: ReportedFeedbackPolicyV1
) -> int:
    """One capped contribution per original action, recomputed without compounding."""
    if not values or len({v.anchor.original_attempt_id for v in values}) != len(values):
        raise ValueError("distinct original opportunities required")
    with localcontext() as context:
        context.prec = 40
        contributions = []
        for value in values:
            improvement = value.relative_cpa_improvement
            if improvement is None or value.status != "operational_reported_as_of":
                raise ValueError("operational comparison required")
            if abs(improvement) <= policy.neutral_band:
                contributions.append(Decimal(0))
                continue
            direction = (
                policy.favorable_direction if improvement > 0 else policy.unfavorable_direction
            )
            sign = 1 if direction == "increase" else -1 if direction == "decrease" else 0
            contributions.append(
                sign * min(abs(improvement) * policy.weight, policy.contribution_clamp)
            )
        aggregate = max(
            -policy.aggregate_clamp,
            min(policy.aggregate_clamp, sum(contributions) / len(contributions)),
        )
        return int(aggregate * policy.maximum_preview_delta_micros)
