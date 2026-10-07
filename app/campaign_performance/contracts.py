from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


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


class CampaignPerformanceV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["inlet.owned-campaign-performance.v2"] = (
        "inlet.owned-campaign-performance.v2"
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
    semantics: Literal["provider_aggregate_unspecified"] = "provider_aggregate_unspecified"
    selected_event: None = None
    reporting_basis: Literal["provider_defaults_unspecified"] = "provider_defaults_unspecified"
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

    platform: Literal["google_ads", "tiktok_ads"]
    conversion_basis: Literal["google_metrics_conversions", "tiktok_generic_conversion"]
    reported_generic_conversions: str | None

    @model_validator(mode="after")
    def provider_meaning(self) -> "CampaignPerformanceV2":
        if self.platform == "google_ads":
            if (
                self.conversion_basis != "google_metrics_conversions"
                or self.reported_generic_conversions is not None
            ):
                raise ValueError("inconsistent Google reported metric basis")
        elif self.conversion_basis != "tiktok_generic_conversion" or any(
            value is not None
            for value in (
                self.conversions,
                self.conversion_value_micros,
                self.cpa_micros,
                self.reported_roas,
            )
        ):
            raise ValueError("TikTok generic reporting cannot qualify conversion/value metrics")
        return self
