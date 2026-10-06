"""Customer intent only: scopes, proof, environment and executable plans are server-owned."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.provider_contracts import Digest, Id


class PolicyIntent(StrictModel):
    goal_id: Id
    goal_revision: int = Field(strict=True, ge=1)
    account_ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(min_length=1, max_length=20)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    total_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    per_plan_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    positive_change_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    action_limit: int = Field(strict=True, ge=1, le=1000)
    cooldown_seconds: int = Field(strict=True, ge=0, le=86400)
    aggressiveness_percent: Literal[5, 10, 20]
    allowed_purposes: list[Literal["create_paused", "activate"]] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def bounded(self) -> "PolicyIntent":
        if (
            len(set(self.account_ids)) != len(self.account_ids)
            or len(set(self.allowed_purposes)) != len(self.allowed_purposes)
            or not 0 < (self.ends_at - self.starts_at).total_seconds() <= 366 * 86400
            or self.per_plan_cap_micros > self.total_cap_micros
            or self.positive_change_cap_micros > self.total_cap_micros
        ):
            raise ValueError("invalid fixed-period policy limits")
        return self


class PolicyEdit(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    intent: PolicyIntent


class ConsentIntent(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    policy_digest: Digest


class ExactApproval(StrictModel):
    review_digest: Digest
    plan_digest: Digest


class GoogleConfigurationIntent(StrictModel):
    """Resource IDs are untrusted choices, independently qualified by provider reads."""

    daily_budget_micros: int = Field(strict=True, gt=0, le=10**15)
    max_cpc_micros: int = Field(strict=True, gt=0, le=10**15)
    catalog_option_id: Digest
    search_partners: bool = Field(strict=True, default=False)


class GoogleTotalConfigurationIntent(StrictModel):
    budget_kind: Literal["campaign_total_v1"]
    total_budget_micros: int = Field(strict=True, gt=0, le=10**15)
    max_cpc_micros: int = Field(strict=True, gt=0, le=10**15)
    catalog_option_id: Digest
    search_partners: bool = Field(strict=True, default=False)


class CreationIntent(StrictModel):
    draft_id: Id
    draft_revision: int = Field(strict=True, ge=1)
    mandate_id: Id
    mandate_revision: int = Field(strict=True, ge=1)
    google: GoogleConfigurationIntent | GoogleTotalConfigurationIntent


class ActivationIntent(StrictModel):
    parent_run_id: Id
    mandate_id: Id
    mandate_revision: int = Field(strict=True, ge=1)


class ReconcileIntent(StrictModel):
    attempt_id: Id


class CatalogIntent(StrictModel):
    draft_id: Id
