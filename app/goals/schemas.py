from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.commerce.reporting import MeasurementWindow


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoalDefinition(StrictModel):
    metric: Literal["shopify_merchandise_net_sales_v1"]
    store_id: str = Field(min_length=32, max_length=32)
    target_micros: int = Field(strict=True, gt=0, le=10**15)
    target_window: MeasurementWindow
    baseline_window: MeasurementWindow
    deadline: date  # Inclusive local deadline; window end is exclusive.
    budget_micros: int = Field(strict=True, ge=0, le=10**15)
    budget_start: date
    budget_end: date
    aggressiveness: Literal["conservative", "balanced", "assertive"]

    @model_validator(mode="after")
    def coherent(self) -> "GoalDefinition":
        target, baseline = self.target_window, self.baseline_window
        if (target.currency, target.time_zone, target.time_basis) != (
            baseline.currency,
            baseline.time_zone,
            baseline.time_basis,
        ):
            raise ValueError("inconsistent measurement basis")
        if baseline.end > target.start or self.deadline.toordinal() != target.end.toordinal() - 1:
            raise ValueError("invalid baseline or deadline")
        if self.budget_start >= self.budget_end:
            raise ValueError("invalid budget period")
        if target.time_basis == "cumulative" and (target.end - target.start) != (
            baseline.end - baseline.start
        ):
            raise ValueError("cumulative baseline must have comparable duration")
        return self


class DraftInput(StrictModel):
    definition: GoalDefinition | None = None


class EditInput(DraftInput):
    expected_revision: int = Field(strict=True, ge=1)


class PreviewInput(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)


class ConfirmInput(PreviewInput):
    preview_id: str = Field(min_length=32, max_length=32)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class InterpretationInput(PreviewInput):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    milestone: str = Field(min_length=1, max_length=4096)


class GoalCandidate(StrictModel):
    # Model output cannot supply owned store IDs, baseline facts or permissions.
    metric: Literal["shopify_merchandise_net_sales_v1"] | None = None
    target_micros: int | None = Field(default=None, strict=True, gt=0, le=10**15)
    time_basis: Literal["calendar_month", "cumulative"] | None = None
    start: date | None = None
    end: date | None = None
    deadline: date | None = None


class InterpretationOutput(StrictModel):
    status: Literal["proposal", "needs_clarification", "unsupported"]
    candidate: GoalCandidate | None = None
    missing_fields: list[
        Literal["metric", "target", "time_basis", "window", "deadline", "source", "baseline"]
    ] = Field(default_factory=list, max_length=7)
    questions: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def bounded(self) -> "InterpretationOutput":
        if any(len(q) > 300 for q in self.questions):
            raise ValueError("question too long")
        if self.status == "proposal" and self.candidate is None:
            raise ValueError("missing proposal")
        return self
