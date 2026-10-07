"""Frozen initial-planning contract. Every policy number is explicitly configured."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.publication.contracts import fingerprint
from app.publication.customer_optimization_contracts import TargetChoice


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CohortV1(Frozen):
    workspace_id: int = Field(strict=True, gt=0)
    account_id: int = Field(strict=True, gt=0)
    campaign_id: int = Field(strict=True, gt=0)
    platform: Literal["meta_ads"] = "meta_ads"
    selected_event: str = Field(min_length=1, max_length=64)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    query_version: str = Field(min_length=1, max_length=100)
    reporting_basis: Literal["provider_defaults_unspecified"] = "provider_defaults_unspecified"

    def digest(self) -> str:
        return fingerprint("inlet.initial-cohort.v1", self.model_dump(mode="json"))


class EfficiencyObjectiveV1(Frozen):
    schema_version: Literal["inlet.reported-efficiency-objective.v1"] = (
        "inlet.reported-efficiency-objective.v1"
    )
    cohort: CohortV1
    goal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    goal_revision: int = Field(strict=True, gt=0)
    maximum_reported_cpa_micros: int = Field(strict=True, gt=0, le=10**15)
    interpretation: Literal["customer_confirmed_reported_event_objective"] = (
        "customer_confirmed_reported_event_objective"
    )

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class RuleParametersV1(Frozen):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    increase_below_ratio: Decimal = Field(gt=0, lt=1)
    decrease_above_ratio: Decimal = Field(gt=1)
    minimum_reported_conversions: Decimal = Field(gt=0)
    minimum_spend_micros: int = Field(strict=True, ge=0, le=10**15)
    budget_step_micros: int = Field(strict=True, gt=0, le=10**15)


class InitialPlanningConfiguration(Frozen):
    schema_version: Literal["inlet.initial-planning-configuration.v1"] = (
        "inlet.initial-planning-configuration.v1"
    )
    environment: Literal["contract_test", "live"]
    policy_family: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: int = Field(strict=True, gt=0)
    retention_seconds: int = Field(strict=True, gt=0, le=2**31 - 1)
    maximum_observations: int = Field(strict=True, ge=2, le=128)
    minimum_training_windows: int = Field(strict=True, ge=1, le=64)
    minimum_holdout_windows: int = Field(strict=True, ge=1, le=64)
    maximum_report_age_seconds: int = Field(strict=True, gt=0, le=2**31 - 1)
    minimum_report_age_seconds: int = Field(strict=True, ge=0, le=2**31 - 1)
    preview_lifetime_seconds: int = Field(strict=True, ge=1, le=300)
    selected_rule: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    supported_event: str = Field(min_length=1, max_length=64)
    rules: tuple[RuleParametersV1, ...] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def coherent(self) -> "InitialPlanningConfiguration":
        names = [r.name for r in self.rules]
        if len(set(names)) != len(names) or self.selected_rule not in names:
            raise ValueError("unique explicitly selected rule required")
        if self.minimum_training_windows + self.minimum_holdout_windows > self.maximum_observations:
            raise ValueError("configured chronological samples exceed capture bound")
        if self.minimum_report_age_seconds > self.maximum_report_age_seconds:
            raise ValueError("invalid report age bounds")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ObservationV1(Frozen):
    schema_version: Literal["inlet.initial-observation.v1"] = "inlet.initial-observation.v1"
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    cohort: CohortV1
    environment: Literal["contract_test", "live"]
    completion_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation: int = Field(strict=True, gt=0)
    privacy_revision: int = Field(strict=True, ge=0)
    starts_on: date
    ends_on: date
    completed_at: AwareDatetime
    captured_at: AwareDatetime
    expires_at: AwareDatetime
    retention_policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    reported_day_count: int = Field(strict=True, ge=0, le=400)
    impressions: int | None = Field(default=None, strict=True, ge=0)
    clicks: int | None = Field(default=None, strict=True, ge=0)
    spend_micros: int | None = Field(default=None, strict=True, ge=0)
    conversions: Decimal | None = Field(default=None, ge=0)
    conversion_value_micros: int | None = Field(default=None, strict=True, ge=0)

    @model_validator(mode="after")
    def bounded(self) -> "ObservationV1":
        if not 0 <= (self.ends_on - self.starts_on).days < 400:
            raise ValueError("bounded inclusive report window required")
        if not self.completed_at <= self.captured_at < self.expires_at:
            raise ValueError("actual availability and retention ordering required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class RuleReplayV1(Frozen):
    rule: str
    training_eligible: int = Field(strict=True, ge=0)
    holdout_eligible: int = Field(strict=True, ge=0)
    increase_count: int = Field(strict=True, ge=0)
    decrease_count: int = Field(strict=True, ge=0)
    hold_count: int = Field(strict=True, ge=0)
    insufficient_count: int = Field(strict=True, ge=0)
    chronological_direction_changes: int = Field(strict=True, ge=0)
    revision_direction_changes: int = Field(strict=True, ge=0)


class CalibrationReportV1(Frozen):
    schema_version: Literal["inlet.initial-calibration-report.v1"] = (
        "inlet.initial-calibration-report.v1"
    )
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    status: Literal["evaluated", "insufficient"]
    environment: Literal["contract_test", "live"]
    cohort: CohortV1
    objective_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    observation_ids: tuple[Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")], ...] = Field(
        max_length=128
    )
    training_windows: int = Field(strict=True, ge=0)
    holdout_windows: int = Field(strict=True, ge=0)
    selected_rule: str
    rules: tuple[RuleReplayV1, ...] = Field(max_length=25)
    reasons: tuple[str, ...] = Field(max_length=20)
    evaluated_at: AwareDatetime
    expires_at: AwareDatetime
    empirical_qualification: Literal[False] = False
    causal_lift: Literal["unavailable"] = "unavailable"
    spending_authorized: Literal[False] = False

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))

    @model_validator(mode="after")
    def valid_report(self) -> "CalibrationReportV1":
        if (
            len(set(self.observation_ids)) != len(self.observation_ids)
            or self.expires_at <= self.evaluated_at
        ):
            raise ValueError("unique observations and unexpired report required")
        if self.status == "evaluated" and self.reasons:
            raise ValueError("evaluated report cannot contain blocking reasons")
        return self


class InitialPreviewV1(Frozen):
    schema_version: Literal["inlet.initial-efficiency-preview.v1"] = (
        "inlet.initial-efficiency-preview.v1"
    )
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    calibration_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    observation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    objective: EfficiencyObjectiveV1
    policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    recommendation_status: Literal["proposed", "hold", "insufficient"]
    direction: Literal["increase", "decrease", "none"]
    before_budget_micros: int | None = Field(default=None, strict=True, gt=0)
    after_budget_micros: int | None = Field(default=None, strict=True, gt=0)
    native_state_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    reasons: tuple[str, ...] = Field(max_length=20)
    created_at: AwareDatetime
    expires_at: AwareDatetime
    review_available: Literal[False] = False
    handoff_reason: Literal["initial_preview_review_handoff_unavailable"] = (
        "initial_preview_review_handoff_unavailable"
    )
    spending_authorized: Literal[False] = False
    empirical_qualification: Literal[False] = False

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))

    @model_validator(mode="after")
    def exact_or_absent(self) -> "InitialPreviewV1":
        values = (self.before_budget_micros, self.after_budget_micros, self.native_state_digest)
        if any(v is not None for v in values) and any(v is None for v in values):
            raise ValueError("native amounts require complete current native evidence")
        if (self.recommendation_status == "proposed") != (
            self.direction in {"increase", "decrease"}
        ):
            raise ValueError("recommendation direction inconsistent")
        if self.recommendation_status == "insufficient" and any(v is not None for v in values):
            raise ValueError("insufficient evidence cannot carry native amounts")
        if self.before_budget_micros is not None and self.after_budget_micros is not None:
            delta = self.after_budget_micros - self.before_budget_micros
            if (
                (self.direction == "increase" and delta <= 0)
                or (self.direction == "decrease" and delta >= 0)
                or (self.direction == "none" and delta != 0)
            ):
                raise ValueError("native amount direction inconsistent")
        if not self.created_at < self.expires_at:
            raise ValueError("bounded preview lifetime required")
        return self


class PreviewIntentV1(Frozen):
    objective: EfficiencyObjectiveV1
    calibration_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    observation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    # Exact owned selection is optional only when no native amount can be shown.
    choice: "TargetChoice | None" = None
    mandate_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    mandate_revision: int | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode="after")
    def owned_selection(self) -> "PreviewIntentV1":
        present = (
            self.choice is not None,
            self.mandate_id is not None,
            self.mandate_revision is not None,
        )
        if any(present) and not all(present):
            raise ValueError("complete owned native selection required")
        if self.choice is not None and (
            self.choice.account_id != self.objective.cohort.account_id
            or self.choice.goal_id != self.objective.goal_id
            or self.choice.goal_revision != self.objective.goal_revision
        ):
            raise ValueError("native choice and confirmed objective differ")
        return self
