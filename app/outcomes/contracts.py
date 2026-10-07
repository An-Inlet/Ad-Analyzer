"""Frozen consumer inputs, intentionally independent of scheduler transport ports."""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Code = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
Positive = Annotated[int, Field(strict=True, gt=0)]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class AccountScope(Frozen):
    workspace_id: Positive
    platform: Literal["google_ads", "meta_ads", "tiktok_ads"]
    connection_id: Positive
    account_id: Positive
    external_advertiser_id: Identifier
    connection_version: Identifier
    generation: Positive | None


class ActionBinding(Frozen):
    action_id: Identifier
    action_digest: Digest
    account: AccountScope
    operation: Literal[
        "budget_change", "pause", "resume", "new_campaign", "creative", "negative_keyword"
    ]
    mandate_id: Identifier
    mandate_revision: Positive
    mandate_digest: Digest
    goal_id: Identifier
    goal_revision: Positive
    goal_digest: Digest


class ReceiptInput(Frozen):
    # A consumer value, NOT a new scheduler method or a production receipt adapter.
    mode: Literal["synthetic", "unavailable_production"]
    binding: ActionBinding
    request_digest: Digest | None = None
    receipt_digest: Digest | None = None
    outcome: Literal["verified_effect", "verified_no_effect", "unknown", "conflict"]
    dispatched_at: AwareDatetime | None = None
    observed_at: AwareDatetime | None = None
    effective_upper_bound: AwareDatetime | None = None
    activation_verified: bool = False

    @model_validator(mode="after")
    def honest_receipt(self) -> "ReceiptInput":
        if self.mode == "unavailable_production" and (
            self.outcome != "unknown" or self.activation_verified or self.effective_upper_bound
        ):
            raise ValueError("production lineage is unavailable")
        if self.effective_upper_bound is not None and (
            self.outcome != "verified_effect"
            or self.dispatched_at is None
            or self.observed_at is None
            or not self.dispatched_at <= self.effective_upper_bound <= self.observed_at
        ):
            raise ValueError("effective interval must be bounded by verified receipt")
        if self.dispatched_at and self.observed_at and self.dispatched_at > self.observed_at:
            raise ValueError("receipt timestamps out of order")
        return self


class SourceScope(Frozen):
    workspace_id: Positive
    provider: Literal["shopify", "google_ads", "meta_ads", "tiktok_ads", "unified"]
    connection_id: Positive
    source_id: Identifier
    generation: Positive | None
    account: AccountScope | None = None


class MetricBasis(Frozen):
    definition: Code
    definition_digest: Digest
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    unit: Literal["micros", "count", "decimal_count"]
    grain: Literal["store", "account", "campaign", "ad_group", "ad"]
    entity_id: Identifier
    time_zone: str = Field(min_length=1, max_length=64)
    time_basis: Literal["cumulative", "calendar_month"]
    attribution: Literal["not_applicable_store_total", "platform_reported", "unified_contract"]
    attribution_digest: Digest | None
    maturity_policy: Code | None

    @model_validator(mode="after")
    def known_zone(self) -> "MetricBasis":
        ZoneInfo(self.time_zone)
        if self.grain == "store" and self.attribution != "not_applicable_store_total":
            raise ValueError("store totals are not ad-attributed revenue")
        return self


class Window(Frozen):
    start: date
    end: date  # exclusive
    time_zone: str
    start_utc: AwareDatetime
    end_utc: AwareDatetime

    @model_validator(mode="after")
    def exact_boundaries(self) -> "Window":
        zone = ZoneInfo(self.time_zone)
        if not 0 < (self.end - self.start).days <= 400:
            raise ValueError("invalid bounded window")
        if self.start_utc != datetime.combine(self.start, time.min, zone).astimezone(UTC):
            raise ValueError("start boundary mismatch")
        if self.end_utc != datetime.combine(self.end, time.min, zone).astimezone(UTC):
            raise ValueError("end boundary mismatch")
        return self

    @classmethod
    def local(cls, start: date, end: date, zone_name: str) -> "Window":
        zone = ZoneInfo(zone_name)
        return cls(
            start=start,
            end=end,
            time_zone=zone_name,
            start_utc=datetime.combine(start, time.min, zone).astimezone(UTC),
            end_utc=datetime.combine(end, time.min, zone).astimezone(UTC),
        )


class Coverage(Frozen):
    complete: bool
    # Explicit zero days are included in covered_days, never synthesized from absent rows.
    covered_days: tuple[date, ...] = Field(max_length=400)
    zero_days: tuple[date, ...] = Field(max_length=400)
    mature_through: date | None  # inclusive
    fresh_through: AwareDatetime | None
    correction_state: Literal["settled_as_of", "pending", "unknown"]
    reasons: tuple[Code, ...] = Field(default=(), max_length=40)

    @model_validator(mode="after")
    def unique_days(self) -> "Coverage":
        if len(set(self.covered_days)) != len(self.covered_days) or len(set(self.zero_days)) != len(
            self.zero_days
        ):
            raise ValueError("duplicate coverage day")
        if not set(self.zero_days) <= set(self.covered_days):
            raise ValueError("zero days require coverage")
        return self


class Observation(Frozen):
    source: SourceScope
    basis: MetricBasis
    window: Window
    snapshot_id: Identifier
    snapshot_digest: Digest
    data_revision: Annotated[int, Field(strict=True, ge=0)]
    as_of: AwareDatetime
    value: Annotated[Decimal, Field(max_digits=30, decimal_places=6)] | None
    coverage: Coverage
    privacy: Literal["available", "invalidated", "unknown"]

    @model_validator(mode="after")
    def scoped_basis(self) -> "Observation":
        if self.basis.time_zone != self.window.time_zone:
            raise ValueError("window and metric zone differ")
        if self.source.account and self.source.account.workspace_id != self.source.workspace_id:
            raise ValueError("source account owner mismatch")
        if self.basis.grain != "store" and self.source.account is None:
            raise ValueError("advertising metrics require explicit account scope")
        if (
            self.basis.unit in {"micros", "count"}
            and self.value is not None
            and self.value != self.value.to_integral_value()
        ):
            raise ValueError("integer micros/count required")
        return self


class ComparisonPolicy(Frozen):
    version: Code
    as_of: AwareDatetime
    max_source_age_seconds: Annotated[int, Field(strict=True, ge=0, le=604800)]
    washout_seconds: Annotated[int, Field(strict=True, ge=0, le=31536000)]
    calendar_policy: Literal["equal_local_days", "whole_calendar_months"]


class Confounder(Frozen):
    code: Code
    evidence: Literal["observed", "user_reported", "unknown"]
    reference_digest: Digest | None = None


class EvaluationInput(Frozen):
    action: ActionBinding
    receipt: ReceiptInput
    before: Observation
    after: Observation
    policy: ComparisonPolicy
    confounders: tuple[Confounder, ...] = Field(default=(), max_length=100)
    supersedes: Digest | None = None


class Evaluation(Frozen):
    schema_version: Literal["inlet.action-outcome-evidence.v1"] = "inlet.action-outcome-evidence.v1"
    evaluator_version: Literal["pure_observational_v1"] = "pure_observational_v1"
    input_digest: Digest
    status: Literal["synthetic_comparable", "insufficient"]
    reasons: tuple[Code, ...]
    warnings: tuple[Code, ...]
    before_value: Decimal | None
    after_value: Decimal | None
    absolute_difference: Decimal | None
    relative_difference: Decimal | None
    interpretation: Literal["observational_only"] = "observational_only"
    causal_lift: None = None
    spending_authority: Literal["none"] = "none"
