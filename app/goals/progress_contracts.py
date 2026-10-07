"""Informational current goal progress; no achievement or spending authority."""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.commerce.reporting import MeasurementWindow


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


ProgressReason = Literal[
    "goal_not_confirmed", "goal_definition_unavailable", "source_unavailable",
    "measurement_basis_changed", "ambiguous_local_boundary", "no_closed_days",
    "outside_retention", "missing_history", "incomplete_window", "stale_source",
    "import_in_progress", "source_error", "unreconciled_source", "privacy_suppressed_source",
]


class ClosedDayCoverageV1(Frozen):
    starts_on: date
    ends_on_exclusive: date
    starts_at: AwareDatetime
    ends_at_exclusive: AwareDatetime
    closed_day_count: int = Field(strict=True, gt=0, le=400)
    extent: Literal["partial_period", "full_window_as_of"]

    @model_validator(mode="after")
    def interval(self) -> "ClosedDayCoverageV1":
        if (
            self.ends_at_exclusive <= self.starts_at
            or (self.ends_on_exclusive - self.starts_on).days != self.closed_day_count
        ):
            raise ValueError("exact positive closed-day coverage required")
        return self


class GoalSalesProgressV1(Frozen):
    schema_version: Literal["inlet.goal-sales-progress.v1"] = "inlet.goal-sales-progress.v1"
    workspace_id: int = Field(strict=True, gt=0)
    goal_id: str = Field(min_length=32, max_length=32)
    revision: int = Field(strict=True, gt=0)
    definition_digest: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    metric: Literal["shopify_merchandise_net_sales_v1"] = "shopify_merchandise_net_sales_v1"
    status: Literal["available_as_of", "not_started", "unavailable"]
    target_window: MeasurementWindow | None
    target_micros: int | None = Field(strict=True, gt=0)
    store_id: str | None = Field(min_length=32, max_length=32)
    currency: str | None = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str | None = Field(max_length=64)
    coverage: ClosedDayCoverageV1 | None
    net_sales_micros: int | None = Field(strict=True)
    source_watermark: AwareDatetime | None
    source_revision: int | None = Field(strict=True, ge=0)
    import_in_progress: bool | None
    as_of: AwareDatetime
    reasons: tuple[ProgressReason, ...] = Field(max_length=14)
    goal_achievement: Literal["not_assessed"] = "not_assessed"
    attribution: Literal["unavailable"] = "unavailable"
    spending_authorized: Literal[False] = False

    @model_validator(mode="after")
    def exact_available(self) -> "GoalSalesProgressV1":
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("unique reasons required")
        definition = (
            self.definition_digest, self.target_window, self.target_micros,
            self.store_id, self.currency, self.time_zone,
        )
        if any(value is None for value in definition) and any(
            value is not None for value in definition
        ):
            raise ValueError("complete definition metadata required")
        window = self.target_window
        if window is not None and (window.currency, window.time_zone) != (
            self.currency, self.time_zone
        ):
            raise ValueError("exact goal measurement basis required")
        coverage = self.coverage
        if coverage is not None and (
            window is None or coverage.starts_on != window.start
            or coverage.ends_on_exclusive > window.end
            or (coverage.extent == "full_window_as_of") != (
                coverage.ends_on_exclusive == window.end
            )
        ):
            raise ValueError("coverage must be a prefix of the unchanged goal")
        if self.status == "available_as_of":
            if (
                any(value is None for value in definition) or coverage is None
                or self.net_sales_micros is None or self.source_watermark is None
                or self.source_revision is None or self.import_in_progress is not False
                or self.reasons or coverage.ends_at_exclusive > self.source_watermark
                or coverage.ends_at_exclusive > self.as_of or self.source_watermark > self.as_of
            ):
                raise ValueError("available progress requires complete current closed-day coverage")
        elif self.net_sales_micros is not None or not self.reasons:
            raise ValueError("unavailable progress cannot carry an amount")
        return self
