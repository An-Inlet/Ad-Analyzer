from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class CampaignPerformanceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["inlet.owned-campaign-performance.v1"] = (
        "inlet.owned-campaign-performance.v1"
    )
    completion_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    account_id: int = Field(gt=0)
    campaign_id: int = Field(gt=0)
    generation: int = Field(gt=0)
    privacy_revision: int = Field(ge=0)
    starts_on: date
    ends_on: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str
    completed_at: AwareDatetime
    semantics: Literal["explicit_platform_event", "traffic_spend_only"]
    selected_event: str | None
    reporting_basis: Literal["provider_defaults_unspecified"]
    reported_day_count: int = Field(ge=0, le=400)
    campaign_rows_available: bool
    impressions: int | None = Field(ge=0)
    clicks: int | None = Field(ge=0)
    spend_micros: int | None = Field(ge=0)
    conversions: str | None
    conversion_value_micros: int | None = Field(ge=0)
    cpa_micros: str | None
    reported_roas: str | None
    maturity: Literal["unqualified"] = "unqualified"
    causal_attribution: Literal["unavailable"] = "unavailable"
    spending_authorized: Literal[False] = False
