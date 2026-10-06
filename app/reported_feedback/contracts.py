"""Separate B17 operational contracts; every policy number requires server input."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.initial_planning.contracts import CohortV1, EfficiencyObjectiveV1, Frozen
from app.publication.contracts import fingerprint

Id = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Positive = Annotated[int, Field(strict=True, gt=0)]
Direction = Literal["increase", "decrease", "none"]


class Committed(Frozen):
    def digest(self) -> str:
        return fingerprint(type(self).__name__, self.model_dump(mode="json"))


class ReportWindowV1(Committed):
    starts_on: date
    ends_on: date  # Inclusive provider query dates, never an inferred delivery interval.

    @model_validator(mode="after")
    def bounded(self) -> "ReportWindowV1":
        if not 0 <= (self.ends_on - self.starts_on).days < 56:
            raise ValueError("closed bounded report window required")
        return self

    def dates(self) -> tuple[date, ...]:
        return tuple(
            self.starts_on + timedelta(days=i)
            for i in range((self.ends_on - self.starts_on).days + 1)
        )


class ConfigurationObservationAnchorV1(Committed):
    schema_version: Literal["inlet.configuration-observation-anchor.v1"] = (
        "inlet.configuration-observation-anchor.v1"
    )
    environment: Literal["contract_test", "live"]
    cohort: CohortV1
    integration_id: Positive
    source_connection_id: Positive
    source_generation: Positive
    external_account_id: str = Field(pattern=r"^[0-9]{1,32}$")
    external_campaign_id: str = Field(pattern=r"^[0-9]{1,32}$")
    original_attempt_id: Id
    original_request_digest: Digest
    original_plan_digest: Digest
    reservation_id: Id
    ledger_id: Id
    latest_receipt_id: Id
    latest_receipt_digest: Digest
    latest_receipt_sequence: Positive
    dispatched_at: AwareDatetime
    configuration_observed_at: AwareDatetime
    before_configuration_digest: Digest
    after_configuration_digest: Digest
    budget_field: Literal["daily_budget", "lifetime_budget"]
    before_budget_micros: Positive
    after_budget_micros: Positive
    goal_id: Id
    goal_revision: Positive
    goal_digest: Digest
    privacy_revision: int = Field(strict=True, ge=0)
    interpretation: Literal["configuration_observed_not_delivery_effective"] = (
        "configuration_observed_not_delivery_effective"
    )
    delivery_time: Literal["unavailable"] = "unavailable"
    causal_lift: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def chronology(self) -> "ConfigurationObservationAnchorV1":
        if self.configuration_observed_at < self.dispatched_at:
            raise ValueError("configuration readback precedes original dispatch")
        if self.before_budget_micros == self.after_budget_micros:
            raise ValueError("changed campaign budget required")
        return self

    def opportunity_digest(self, family: str) -> str:
        # Neither receipt, report, job, session nor policy revision creates a new action.
        return fingerprint(
            "inlet.reported-action-opportunity.v1",
            {
                "environment": self.environment,
                "workspace_id": self.cohort.workspace_id,
                "account_id": self.cohort.account_id,
                "campaign_id": self.cohort.campaign_id,
                "cohort_digest": self.cohort.digest(),
                "original_attempt_id": self.original_attempt_id,
                "original_request_digest": self.original_request_digest,
                "family": family,
            },
        )


class ReportedWindowPolicyV1(Committed):
    schema_version: Literal["inlet.reported-window-policy.v1"] = "inlet.reported-window-policy.v1"
    policy_id: Id
    family: Id
    revision: Positive
    environment: Literal["contract_test", "live"]
    selected_event: str = Field(min_length=1, max_length=64)
    query_version: str = Field(min_length=1, max_length=100)
    window_days: int = Field(strict=True, ge=7, le=56)
    minimum_close_age_seconds: int = Field(strict=True, ge=0, le=2**31 - 1)
    distinct_repeat_completions: int = Field(strict=True, ge=2, le=8)
    minimum_repeat_spacing_seconds: int = Field(strict=True, gt=0, le=2**31 - 1)
    maximum_acquisition_age_seconds: int = Field(strict=True, gt=0, le=2**31 - 1)
    maximum_source_age_seconds: int = Field(strict=True, gt=0, le=2**31 - 1)
    daily_spend_absolute_tolerance_micros: int = Field(strict=True, ge=0, le=10**15)
    daily_conversion_absolute_tolerance: Decimal = Field(ge=0, le=10**12)
    daily_relative_tolerance: Decimal = Field(ge=0, le=1)
    minimum_conversions: Decimal = Field(gt=0, le=10**12)
    minimum_spend_micros: int = Field(strict=True, gt=0, le=10**15)
    retention_seconds: int = Field(strict=True, gt=0, le=2**31 - 1)
    maximum_capsules: int = Field(strict=True, ge=4, le=128)
    maximum_requests: int = Field(strict=True, ge=1, le=16)
    decision_lifetime_seconds: int = Field(strict=True, ge=1, le=300)

    @model_validator(mode="after")
    def comparable(self) -> "ReportedWindowPolicyV1":
        if self.window_days % 7 or self.maximum_capsules < 2 * self.distinct_repeat_completions:
            raise ValueError("whole-week comparable windows and adequate capsule capacity required")
        return self


class ReportedDayV1(Frozen):
    day: date
    spend_micros: int = Field(strict=True, ge=0, le=10**18)
    conversions: Decimal = Field(ge=0, le=10**12)
    conversion_value_micros: int | None = Field(strict=True, ge=-(10**18), le=10**18)


class ReportedWindowCapsuleV1(Committed):
    schema_version: Literal["inlet.reported-window-capsule.v1"] = "inlet.reported-window-capsule.v1"
    id: Id
    job_id: Id
    acquisition_run_id: Id
    completion_id: Id
    completion_manifest_digest: Digest
    environment: Literal["contract_test", "live"]
    cohort: CohortV1
    source_generation: Positive
    captured_privacy_revision: int = Field(strict=True, ge=0)
    policy_digest: Digest
    window: ReportWindowV1
    acquisition_started_at: AwareDatetime
    acquisition_completed_at: AwareDatetime
    captured_at: AwareDatetime
    expires_at: AwareDatetime
    days: tuple[ReportedDayV1, ...] = Field(max_length=56)

    @model_validator(mode="after")
    def exact_days(self) -> "ReportedWindowCapsuleV1":
        dates = [r.day for r in self.days]
        if dates != sorted(set(dates)) or not set(dates) <= set(self.window.dates()):
            raise ValueError("exact unique in-window campaign days required")
        if (
            not self.acquisition_started_at
            <= self.acquisition_completed_at
            <= self.captured_at
            < self.expires_at
        ):
            raise ValueError("actual acquisition and capture chronology required")
        return self

    def missing_dates(self) -> tuple[date, ...]:
        reported = {r.day for r in self.days}
        return tuple(day for day in self.window.dates() if day not in reported)


class CapsuleReferenceV1(Frozen):
    id: Id
    digest: Digest
    completion_id: Id
    acquired_at: AwareDatetime


class ReportedWindowSummaryV1(Frozen):
    window: ReportWindowV1
    capsules: tuple[CapsuleReferenceV1, ...] = Field(min_length=1, max_length=8)
    missing_dates: tuple[date, ...] = Field(max_length=56)
    spend_micros: int | None = Field(default=None, strict=True, ge=0)
    conversions: Decimal | None = Field(default=None, ge=0)
    reported_cpa_micros: Decimal | None = Field(default=None, ge=0)
    revisions_within_tolerance: bool


class OperationalReportedComparisonV1(Committed):
    schema_version: Literal["inlet.operational-reported-comparison.v1"] = (
        "inlet.operational-reported-comparison.v1"
    )
    id: Id
    job_id: Id
    anchor: ConfigurationObservationAnchorV1
    objective: EfficiencyObjectiveV1
    policy_digest: Digest
    policy_family: Id
    before: ReportedWindowSummaryV1
    after: ReportedWindowSummaryV1
    status: Literal["operational_reported_as_of", "insufficient"]
    reasons: tuple[str, ...] = Field(max_length=32)
    relative_cpa_improvement: Decimal | None
    assessed_at: AwareDatetime
    expires_at: AwareDatetime
    correction_status: Literal["as_observed_unsettled"] = "as_observed_unsettled"
    interpretation: Literal["configuration_associated_reported_efficiency_not_causal"] = (
        "configuration_associated_reported_efficiency_not_causal"
    )
    delivery_time: Literal["unavailable"] = "unavailable"
    causal_lift: Literal["unavailable"] = "unavailable"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def honest(self) -> "OperationalReportedComparisonV1":
        if self.expires_at <= self.assessed_at:
            raise ValueError("bounded assessment lifetime required")
        if self.status == "insufficient":
            if not self.reasons or self.relative_cpa_improvement is not None:
                raise ValueError("insufficient comparison cannot produce feedback")
        elif (
            self.reasons
            or self.relative_cpa_improvement is None
            or any(
                s.reported_cpa_micros is None or s.missing_dates or not s.revisions_within_tolerance
                for s in (self.before, self.after)
            )
        ):
            raise ValueError("operational comparison requires usable comparable windows")
        return self


class ReportedFeedbackPolicyV1(Committed):
    policy_id: Id
    family: Id
    revision: Positive
    environment: Literal["contract_test", "live"]
    comparison_policy_digest: Digest
    original_change: Literal["increase", "decrease"]
    favorable_direction: Direction
    unfavorable_direction: Direction
    minimum_distinct_original_attempts: int = Field(strict=True, ge=1, le=64)
    neutral_band: Decimal = Field(ge=0, le=1)
    weight: Decimal = Field(gt=0, le=1)
    contribution_clamp: Decimal = Field(gt=0, le=1)
    aggregate_clamp: Decimal = Field(gt=0, le=1)
    maximum_preview_delta_micros: int = Field(strict=True, gt=0, le=10**15)
    lifetime_seconds: int = Field(strict=True, ge=1, le=300)


class ReportedFeedbackPreviewV1(Committed):
    id: Id
    comparison_id: Id
    comparison_digest: Digest
    baseline_preview_id: Id
    baseline_preview_digest: Digest
    opportunity_digest: Digest
    active_set_digest: Digest
    policy_digest: Digest
    distinct_original_attempt_count: int = Field(strict=True, ge=1, le=64)
    before_reported_cpa_micros: Decimal = Field(ge=0)
    after_reported_cpa_micros: Decimal = Field(ge=0)
    baseline_budget_micros: Positive
    delta_micros: int = Field(strict=True, ge=-(10**15), le=10**15)
    proposed_budget_micros: Positive
    explanation: tuple[str, ...] = Field(min_length=1, max_length=32)
    created_at: AwareDatetime
    expires_at: AwareDatetime
    review_available: Literal[False] = False
    spending_authority: Literal["none"] = "none"
    causal_lift: Literal["unavailable"] = "unavailable"
    delivery_time: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def exact_delta(self) -> "ReportedFeedbackPreviewV1":
        if (
            self.baseline_budget_micros + self.delta_micros != self.proposed_budget_micros
            or self.created_at >= self.expires_at
        ):
            raise ValueError("bounded non-compounding preview required")
        return self


class ComparisonIntentV1(Frozen):
    attempt_id: Id
    goal_id: Id
    goal_revision: Positive
    maximum_reported_cpa_micros: int = Field(strict=True, gt=0, le=10**15)


class FeedbackPreviewIntentV1(Frozen):
    comparison_id: Id
    baseline_preview_id: Id


class ComparisonProgressV1(Frozen):
    id: Id
    state: Literal["pending", "acquiring", "waiting", "ready", "blocked", "expired"]
    completed_observations: int = Field(strict=True, ge=0, le=16)
    required_observations: int = Field(strict=True, ge=4, le=16)
    next_due_at: AwareDatetime | None
    expires_at: AwareDatetime
    reason: str | None = Field(default=None, max_length=80)
    comparison_id: Id | None = None


class ReportedAcquisitionRequestV1(Committed):
    id: Id
    supersedes_request_id: Id | None = None
    anchor: ConfigurationObservationAnchorV1
    objective: EfficiencyObjectiveV1
    policy: ReportedWindowPolicyV1
    before: ReportWindowV1
    after: ReportWindowV1
    created_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def owned_comparable(self) -> "ReportedAcquisitionRequestV1":
        if (
            self.supersedes_request_id == self.id
            or self.anchor.cohort != self.objective.cohort
            or self.anchor.goal_id != self.objective.goal_id
            or self.anchor.goal_revision != self.objective.goal_revision
            or self.anchor.environment != self.policy.environment
            or self.anchor.cohort.selected_event != self.policy.selected_event
            or self.anchor.cohort.query_version != self.policy.query_version
            or len(self.before.dates()) != self.policy.window_days
            or len(self.after.dates()) != self.policy.window_days
            or self.before.ends_on >= self.after.starts_on
            or self.created_at >= self.expires_at
        ):
            raise ValueError("owned comparable acquisition request required")
        return self


class FixedWindowLeaseV1(Committed):
    job_id: Id
    acquisition_run_id: Id
    source_connection_id: Positive
    source_generation: Positive
    observation_ordinal: int = Field(strict=True, ge=0, le=15)
    window: ReportWindowV1
    acquisition_started_at: AwareDatetime
    rolling_covered_from: date | None
    rolling_covered_through: date | None
    rolling_last_sync_at: AwareDatetime | None
