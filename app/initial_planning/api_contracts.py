"""Customer intent and display projections; callers never submit reporting proof."""

from typing import Literal

from pydantic import Field, model_validator

from app.initial_planning.contracts import Frozen, InitialPlanningConfiguration
from app.publication.customer_optimization_contracts import TargetChoice


class CaptureIntent(Frozen):
    account_id: int = Field(strict=True, gt=0)
    campaign_id: int = Field(strict=True, gt=0)


class CalibrationIntent(Frozen):
    observation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    goal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    goal_revision: int = Field(strict=True, gt=0)
    maximum_reported_cpa_micros: int = Field(strict=True, gt=0, le=10**15)


class PreviewIntent(Frozen):
    calibration_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    observation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    choice: TargetChoice | None = None
    mandate_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    mandate_revision: int | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode="after")
    def complete_selection(self) -> "PreviewIntent":
        fields = (self.choice, self.mandate_id, self.mandate_revision)
        if any(v is not None for v in fields) and any(v is None for v in fields):
            raise ValueError("Complete current native selection required")
        return self


class CampaignOption(Frozen):
    account_id: int
    campaign_id: int
    account_name: str
    campaign_name: str
    currency: str


class PlanningOptions(Frozen):
    configured: bool
    configuration: InitialPlanningConfiguration | None
    environment: Literal["contract_test", "live"] | None
    campaigns: tuple[CampaignOption, ...] = Field(max_length=200)
    native_catalog_available: bool
    review_available: Literal[False] = False
    spending_authorized: Literal[False] = False
    reason: Literal["planning_policy_unavailable"] | None = None


class NativeOption(Frozen):
    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    choice: TargetChoice
    label: str = Field(min_length=1, max_length=160)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    budget_kind: Literal["daily", "lifetime"]
    amount_micros: int = Field(strict=True, gt=0)


class MandateOption(Frozen):
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: int = Field(strict=True, gt=0)
    label: str = Field(min_length=1, max_length=160)


class NativeOptions(Frozen):
    options: tuple[NativeOption, ...] = Field(max_length=50)
    mandates: tuple[MandateOption, ...] = Field(max_length=50)
    review_available: Literal[False] = False
    spending_authorized: Literal[False] = False


class PreviewReviewStatus(Frozen):
    """Readiness to request a review, never financial qualification."""

    preview_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    preview_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_available: bool
    reason: Literal["review_service_unavailable", "exact_proposal_required"] | None
    financial_qualification: Literal["not_checked"] = "not_checked"
    spending_authority: Literal["none"] = "none"
