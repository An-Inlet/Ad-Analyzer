"""Reproducible reported-efficiency sensitivity, never predictive qualification."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.service import read_current
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.initial_planning.capture import configuration, read_observation, unavailable
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import (
    CalibrationReportV1,
    EfficiencyObjectiveV1,
    InitialPlanningConfiguration,
    ObservationV1,
    RuleParametersV1,
    RuleReplayV1,
)
from app.initial_planning.limits import MAX_RETAINED_CALIBRATIONS_PER_CAMPAIGN
from app.initial_planning.models import CalibrationDependency, CalibrationRow, ObservationRow
from app.initial_planning.runtime import InitialPlanningRuntime
from app.meta.security import utc
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority

Direction = Literal["increase", "decrease", "hold", "insufficient"]


def classify(
    observation: ObservationV1, objective: EfficiencyObjectiveV1, rule: RuleParametersV1
) -> Direction:
    if (
        observation.cohort != objective.cohort
        or observation.conversions is None
        or observation.spend_micros is None
        or observation.conversions <= 0
        or observation.conversions < rule.minimum_reported_conversions
        or observation.spend_micros < rule.minimum_spend_micros
    ):
        return "insufficient"
    ratio = (
        Decimal(observation.spend_micros)
        / observation.conversions
        / objective.maximum_reported_cpa_micros
    )
    if ratio < rule.increase_below_ratio:
        return "increase"
    if ratio > rule.decrease_above_ratio:
        return "decrease"
    return "hold"


def current_objective(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    objective: EfficiencyObjectiveV1,
    runtime: InitialPlanningRuntime,
) -> None:
    policy = configuration(runtime)
    c = objective.cohort
    authorize = bind_authority(principal, provider)
    authorize(db, c.workspace_id, principal.user.id)
    goal = goals.owned(db, c.workspace_id, objective.goal_id)
    goals.expect(goal, objective.goal_revision)
    if goals.assessment(db, goal, effective_now(db, runtime)) != "confirmed":
        raise unavailable("current_confirmed_goal_required")
    definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
    if definition.target_window.currency != c.currency:
        raise unavailable("initial_objective_currency_mismatch")
    report = read_current(
        db, c.workspace_id, principal.user.id, c.account_id, c.campaign_id, None, authorize
    )
    completion = db.get(PerformanceCompletion, report.completion_id)
    if (
        completion is None
        or report.selected_event != c.selected_event
        or c.selected_event != policy.supported_event
        or report.currency != c.currency
        or report.time_zone != c.time_zone
        or completion.query_version != c.query_version
        or report.reporting_basis != c.reporting_basis
    ):
        raise unavailable("initial_objective_report_basis_changed")
    now = effective_now(db, runtime)
    if (
        not timedelta(0)
        <= now - report.completed_at
        <= timedelta(seconds=policy.maximum_report_age_seconds)
    ):
        raise unavailable("initial_current_report_stale")


def evaluate(
    observations: tuple[ObservationV1, ...],
    objective: EfficiencyObjectiveV1,
    policy: InitialPlanningConfiguration,
    now: datetime,
) -> CalibrationReportV1:
    reasons: set[str] = set()
    grouped: dict[tuple[date, date], list[ObservationV1]] = {}
    for item in observations:
        if item.cohort != objective.cohort or item.environment != policy.environment:
            reasons.add("observation_basis_mismatch")
        if not item.captured_at <= now < item.expires_at:
            reasons.add("observation_expired_or_future")
        try:
            close = datetime.combine(
                item.ends_on + timedelta(days=1), time.min, ZoneInfo(item.cohort.time_zone)
            )
        except (OverflowError, ValueError, KeyError):
            raise unavailable("initial_observation_calendar_unavailable") from None
        if (item.completed_at - close).total_seconds() < policy.minimum_report_age_seconds:
            reasons.add("observation_window_age_insufficient")
        grouped.setdefault((item.starts_on, item.ends_on), []).append(item)
    groups = [
        sorted(v, key=lambda x: (x.captured_at, x.completed_at, x.id))
        for _, v in sorted(grouped.items())
    ]
    for previous, following in zip(groups, groups[1:], strict=False):
        if previous[0].captured_at >= following[0].captured_at:
            reasons.add("chronological_availability_leakage")
        if previous[0].ends_on >= following[0].starts_on:
            reasons.add("overlapping_report_windows")
    train = groups[: policy.minimum_training_windows]
    holdout = groups[policy.minimum_training_windows :]
    if (
        len(train) < policy.minimum_training_windows
        or len(holdout) < policy.minimum_holdout_windows
    ):
        reasons.add("insufficient_distinct_windows")
    if (
        train
        and holdout
        and max(g[0].captured_at for g in train) >= min(g[0].captured_at for g in holdout)
    ):
        reasons.add("chronological_availability_leakage")
    replays = []
    for rule in policy.rules:
        first = [classify(g[0], objective, rule) for g in groups]
        training = first[: len(train)]
        held = first[len(train) :]
        replays.append(
            RuleReplayV1(
                rule=rule.name,
                training_eligible=sum(v != "insufficient" for v in training),
                holdout_eligible=sum(v != "insufficient" for v in held),
                increase_count=first.count("increase"),
                decrease_count=first.count("decrease"),
                hold_count=first.count("hold"),
                insufficient_count=first.count("insufficient"),
                chronological_direction_changes=sum(
                    a != b for a, b in zip(first, first[1:], strict=False)
                ),
                revision_direction_changes=sum(
                    classify(item, objective, rule) != classify(group[0], objective, rule)
                    for group in groups
                    for item in group[1:]
                ),
            )
        )
    chosen = next(r for r in replays if r.rule == policy.selected_rule)
    if (
        chosen.training_eligible < policy.minimum_training_windows
        or chosen.holdout_eligible < policy.minimum_holdout_windows
    ):
        reasons.add("insufficient_eligible_windows")
    canonical = sorted(observations, key=lambda x: (x.captured_at, x.id))
    return CalibrationReportV1(
        id=uuid4().hex,
        status="insufficient" if reasons else "evaluated",
        environment=policy.environment,
        cohort=objective.cohort,
        objective_digest=objective.digest(),
        policy_digest=policy.digest(),
        input_digest=fingerprint(
            "inlet.initial-calibration-input.v1",
            {
                "observations": [v.digest() for v in canonical],
                "objective": objective.digest(),
                "policy": policy.digest(),
                "cutoff": now.isoformat(),
            },
        ),
        observation_ids=tuple(v.id for v in canonical),
        training_windows=len(train),
        holdout_windows=len(holdout),
        selected_rule=policy.selected_rule,
        rules=tuple(replays),
        reasons=tuple(sorted(reasons)),
        evaluated_at=now,
        expires_at=min(
            [now + timedelta(seconds=policy.preview_lifetime_seconds)]
            + [v.expires_at for v in observations if v.expires_at > now]
        ),
    )


def require_calibration_capacity(
    db: Session, workspace_id: int, account_id: int, campaign_id: int, environment: str
) -> None:
    """Caller holds workspace fence; expired rows count until physical cleanup."""
    retained = list(
        db.scalars(
            select(CalibrationRow.id)
            .where(
                CalibrationRow.workspace_id == workspace_id,
                CalibrationRow.account_id == account_id,
                CalibrationRow.campaign_id == campaign_id,
                CalibrationRow.environment == environment,
            )
            .limit(MAX_RETAINED_CALIBRATIONS_PER_CAMPAIGN)
        )
    )
    if len(retained) >= MAX_RETAINED_CALIBRATIONS_PER_CAMPAIGN:
        raise unavailable("initial_calibration_capacity_reached")


def run_calibration(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    objective: EfficiencyObjectiveV1,
    runtime: InitialPlanningRuntime,
) -> CalibrationReportV1:
    policy = configuration(runtime)
    current_objective(db, principal, provider, objective, runtime)
    c = objective.cohort
    ids = list(
        db.scalars(
            select(ObservationRow.id)
            .where(
                ObservationRow.workspace_id == c.workspace_id,
                ObservationRow.account_id == c.account_id,
                ObservationRow.campaign_id == c.campaign_id,
                ObservationRow.environment == policy.environment,
                ObservationRow.cohort_digest == c.digest(),
            )
            .order_by(ObservationRow.captured_at, ObservationRow.id)
            .limit(policy.maximum_observations + 1)
        )
    )
    if len(ids) > policy.maximum_observations:
        raise unavailable("initial_observation_capacity_reached")
    observations = tuple(
        read_observation(db, principal, provider, c.workspace_id, i, runtime) for i in ids
    )
    report = evaluate(observations, objective, policy, effective_now(db, runtime))
    bind_authority(principal, provider)(db, c.workspace_id, principal.user.id)
    if effective_now(db, runtime) >= report.expires_at:
        raise unavailable("initial_calibration_expired")
    previous = db.scalar(
        select(CalibrationRow)
        .where(
            CalibrationRow.workspace_id == c.workspace_id,
            CalibrationRow.account_id == c.account_id,
            CalibrationRow.campaign_id == c.campaign_id,
            CalibrationRow.input_digest == report.input_digest,
        )
        .order_by(CalibrationRow.id)
        .limit(1)
    )
    if previous is not None:
        return read_calibration(db, principal, provider, c.workspace_id, previous.id, runtime)
    require_calibration_capacity(
        db, c.workspace_id, c.account_id, c.campaign_id, policy.environment
    )
    db.add(
        CalibrationRow(
            id=report.id,
            workspace_id=c.workspace_id,
            account_id=c.account_id,
            campaign_id=c.campaign_id,
            document=report.model_dump(mode="json"),
            document_digest=report.digest(),
            expires_at=report.expires_at,
            environment=policy.environment,
            objective=objective.model_dump(mode="json"),
            objective_digest=objective.digest(),
            policy_digest=policy.digest(),
            input_digest=report.input_digest,
            created_at=report.evaluated_at,
        )
    )
    db.flush()
    db.add_all(
        [
            CalibrationDependency(
                calibration_id=report.id,
                observation_id=i,
                workspace_id=c.workspace_id,
                account_id=c.account_id,
                campaign_id=c.campaign_id,
            )
            for i in report.observation_ids
        ]
    )
    db.flush()
    return report


@dataclass(frozen=True)
class _CalibrationInputs:
    """Fresh DB-only validation result; never accepted as reusable authority."""

    report: CalibrationReportV1
    objective: EfficiencyObjectiveV1
    observations: tuple[ObservationV1, ...]


def _read_calibration_inputs(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    calibration_id: str,
    runtime: InitialPlanningRuntime,
) -> _CalibrationInputs:
    policy = configuration(runtime)
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    row = db.scalar(
        select(CalibrationRow)
        .where(CalibrationRow.workspace_id == workspace_id, CalibrationRow.id == calibration_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise unavailable("initial_calibration_unavailable")
    report = CalibrationReportV1.model_validate(row.document)
    objective = EfficiencyObjectiveV1.model_validate(row.objective)
    if (
        report.digest() != row.document_digest
        or report.id != row.id
        or report.cohort != objective.cohort
        or report.cohort.workspace_id != workspace_id
        or (report.cohort.account_id, report.cohort.campaign_id)
        != (row.account_id, row.campaign_id)
        or report.objective_digest != objective.digest()
        or row.objective_digest != objective.digest()
        or report.policy_digest != policy.digest()
        or row.policy_digest != report.policy_digest
        or report.environment != policy.environment
        or row.environment != report.environment
        or row.input_digest != report.input_digest
        or utc(row.created_at) != report.evaluated_at
        or utc(row.expires_at) != report.expires_at
        or not report.evaluated_at <= effective_now(db, runtime) < report.expires_at
    ):
        raise unavailable("initial_calibration_expired_or_changed")
    current_objective(db, principal, provider, objective, runtime)
    dependency_ids = set(
        db.scalars(
            select(CalibrationDependency.observation_id).where(
                CalibrationDependency.calibration_id == row.id,
                CalibrationDependency.workspace_id == workspace_id,
            )
        )
    )
    if dependency_ids != set(report.observation_ids):
        raise unavailable("initial_calibration_dependencies_changed")
    observations = tuple(
        read_observation(db, principal, provider, workspace_id, oid, runtime)
        for oid in report.observation_ids
    )
    reconstructed = evaluate(observations, objective, policy, report.evaluated_at)
    if reconstructed.model_dump(exclude={"id"}) != report.model_dump(exclude={"id"}):
        raise unavailable("initial_calibration_inputs_changed")
    if effective_now(db, runtime) >= report.expires_at:
        raise unavailable("initial_calibration_expired")
    return _CalibrationInputs(report, objective, observations)


def read_calibration(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    calibration_id: str,
    runtime: InitialPlanningRuntime,
) -> CalibrationReportV1:
    return _read_calibration_inputs(
        db, principal, provider, workspace_id, calibration_id, runtime
    ).report


def read_objective(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    calibration_id: str,
    runtime: InitialPlanningRuntime,
) -> EfficiencyObjectiveV1:
    return _read_calibration_inputs(
        db, principal, provider, workspace_id, calibration_id, runtime
    ).objective
