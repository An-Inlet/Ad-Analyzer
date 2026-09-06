from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[int, Field(ge=0, le=9_000_000_000_000_000)]
ShortText = Annotated[str, Field(max_length=240)]
Notes = Annotated[str, Field(max_length=2000)]
Metric = Literal["optimization_outcomes", "customers", "revenue", "contribution_profit"]


class RecordKind(StrEnum):
    STRATEGY = "strategy"
    EVENT = "event"
    CREATIVE = "creative"
    EXPERIMENT = "experiment"
    COST = "cost"
    CHANGE = "change"
    DECISION = "decision"


class BusinessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def bounded_dates(self) -> Self:
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, date) and not 2000 <= value.year <= 2100:
                raise ValueError("Planning dates must be between 2000 and 2100.")
        return self


class Strategy(BusinessModel):
    title: str = Field(min_length=1, max_length=160)
    primary_metric: Metric = "customers"
    target: Decimal = Field(gt=0, le=1_000_000_000_000)
    period_start: date
    period_end: date
    currency_code: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    budget_micros: Money
    contribution_margin_bps: int | None = Field(default=None, ge=0, le=10_000)
    maximum_cac_micros: Money | None = None
    sales_capacity_per_week: int | None = Field(default=None, ge=1, le=1_000_000)
    minimum_outcomes: int = Field(default=20, ge=5, le=1000)
    priority_audiences: Notes = ""
    positioning: Notes = ""
    offer: Notes = ""
    constraints: Notes = ""

    @model_validator(mode="after")
    def valid_plan(self) -> Self:
        if not 0 <= (self.period_end - self.period_start).days <= 365:
            raise ValueError("Plan dates must span at most one year.")
        if self.primary_metric == "contribution_profit" and self.contribution_margin_bps is None:
            raise ValueError("A contribution margin assumption is required for a profit goal.")
        if self.primary_metric in {"customers", "optimization_outcomes"} and self.target % 1:
            raise ValueError("Customer and lead targets must be whole numbers.")
        return self


class BusinessEvent(BusinessModel):
    title: str = Field(min_length=1, max_length=160)
    category: Literal["launch", "promotion", "conference", "seasonal", "inventory", "capacity"]
    starts_on: date
    ends_on: date
    preparation_days: int = Field(default=14, ge=0, le=180)
    follow_up_days: int = Field(default=7, ge=0, le=90)
    remaining_reserve_micros: Money = 0
    currency_code: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    status: Literal["draft", "confirmed", "completed", "cancelled"] = "draft"
    audience: ShortText = ""
    message: Notes = ""
    preparation: Notes = ""
    follow_up: Notes = ""

    @model_validator(mode="after")
    def valid_dates(self) -> Self:
        if not 0 <= (self.ends_on - self.starts_on).days <= 365:
            raise ValueError("Event dates must span at most one year.")
        return self


class Creative(BusinessModel):
    title: str = Field(min_length=1, max_length=160)
    campaign_id: int = Field(ge=1)
    audience: ShortText
    hook: ShortText
    promise: ShortText = ""
    visual_style: ShortText = ""
    format: Literal["image", "video", "text", "carousel", "mixed"] = "mixed"
    offer: ShortText = ""
    landing_page_path: str = Field(default="/", max_length=512, pattern=r"^/[^?#@]*$")
    starts_on: date
    ends_on: date
    # Campaign evidence must never be presented as isolated individual-ad evidence.
    evidence_scope: Literal["campaign"] = "campaign"

    @model_validator(mode="after")
    def valid_dates(self) -> Self:
        if not 0 <= (self.ends_on - self.starts_on).days <= 365:
            raise ValueError("Creative dates must span at most one year.")
        return self


class Experiment(BusinessModel):
    title: str = Field(min_length=1, max_length=160)
    hypothesis: str = Field(min_length=1, max_length=2000)
    primary_metric: Literal["qualified_lead_rate", "customer_rate"] = "customer_rate"
    control_description: ShortText
    treatment_description: ShortText
    starts_on: date
    ends_on: date
    measurement_delay_days: int = Field(default=14, ge=0, le=180)
    minimum_sample_per_arm: int = Field(default=100, ge=30, le=10_000_000)
    minimum_lift_bps: int = Field(default=100, ge=0, le=10_000)
    budget_micros: Money = 0
    currency_code: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    randomized_assignment: bool = False
    status: Literal["planned", "running", "completed", "cancelled"] = "planned"
    control_units: int = Field(default=0, ge=0, le=100_000_000)
    control_outcomes: int = Field(default=0, ge=0, le=100_000_000)
    treatment_units: int = Field(default=0, ge=0, le=100_000_000)
    treatment_outcomes: int = Field(default=0, ge=0, le=100_000_000)
    control_spend_micros: Money = 0
    treatment_spend_micros: Money = 0
    observed_through: date | None = None
    evidence_reference: ShortText = ""

    @model_validator(mode="after")
    def valid_experiment(self) -> Self:
        if not 0 <= (self.ends_on - self.starts_on).days <= 365:
            raise ValueError("Experiment dates must span at most one year.")
        if self.control_outcomes > self.control_units:
            raise ValueError("Control outcomes exceed unique assigned units.")
        if self.treatment_outcomes > self.treatment_units:
            raise ValueError("Treatment outcomes exceed unique assigned units.")
        if (self.control_units or self.treatment_units) and (
            self.observed_through is None or not self.evidence_reference
        ):
            raise ValueError("Results require an observation date and evidence reference.")
        return self


class OperatingCost(BusinessModel):
    title: str = Field(min_length=1, max_length=160)
    category: Literal["hosting", "database", "analysis", "software", "other"]
    period_start: date
    period_end: date
    amount_micros: Money
    currency_code: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    basis: Literal["observed", "estimate"] = "observed"
    evidence_reference: ShortText = ""

    @model_validator(mode="after")
    def valid_period(self) -> Self:
        if not 0 <= (self.period_end - self.period_start).days <= 365:
            raise ValueError("Cost dates must span at most one year.")
        return self


class BusinessChange(BusinessModel):
    title: str = Field(min_length=1, max_length=160)
    effective_on: date
    category: Literal["advertising", "website", "offer", "sales", "strategy", "tracking"]
    description: Notes = ""
    hypothesis: Notes = ""
    success_metric: ShortText = ""
    baseline_value: Decimal | None = None
    expected_value: Decimal | None = None
    observed_value: Decimal | None = None
    review_on: date
    outcome_notes: Notes = ""

    @model_validator(mode="after")
    def valid_review(self) -> Self:
        if self.review_on < self.effective_on:
            raise ValueError("Review must follow the effective date.")
        return self


class Decision(BusinessModel):
    title: str = Field(min_length=1, max_length=160)
    recommendation_key: str = Field(min_length=1, max_length=96, pattern=r"^[a-z0-9_:-]+$")
    evidence_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["planned", "accepted", "rejected", "completed"] = "planned"
    reason: Notes = ""
    expected_result: Notes = ""
    observed_result: Notes = ""
    review_on: date
    evidence_snapshot: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def review_has_evidence(self) -> Self:
        if self.status in {"accepted", "rejected"} and not self.reason:
            raise ValueError("Record a reason for the decision.")
        if self.status == "completed" and not self.observed_result:
            raise ValueError("Completed decisions require an observed result.")
        return self


RecordPayload = (
    Strategy | BusinessEvent | Creative | Experiment | OperatingCost | BusinessChange | Decision
)
PAYLOAD_MODELS: dict[RecordKind, type[BaseModel]] = {
    RecordKind.STRATEGY: Strategy,
    RecordKind.EVENT: BusinessEvent,
    RecordKind.CREATIVE: Creative,
    RecordKind.EXPERIMENT: Experiment,
    RecordKind.COST: OperatingCost,
    RecordKind.CHANGE: BusinessChange,
    RecordKind.DECISION: Decision,
}


class SaveRecord(BusinessModel):
    expected_version: int = Field(default=0, ge=0)
    payload: dict[str, Any]


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    version: int
    data: dict[str, Any]
    updated_at: datetime


class ScenarioRequest(BusinessModel):
    proposed_budget_micros: Money
    response_elasticity: Decimal = Field(default=Decimal("0.7"), ge=0, le=1)
    uncertainty_bps: int = Field(default=3000, ge=1000, le=9000)


class AnalystQuestion(BusinessModel):
    question: str = Field(min_length=1, max_length=500)
