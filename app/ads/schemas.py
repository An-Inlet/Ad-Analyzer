from datetime import date, datetime
from decimal import Decimal

from app.ads.enums import AdvertisingPlatform, JobRunStatus, MetricEntityType
from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AdvertisingAccountCreate(BaseModel):
    workspace_id: int = Field(default=1, ge=1)
    platform: AdvertisingPlatform
    external_account_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    currency_code: str = Field(min_length=3, max_length=3)
    time_zone: str | None = Field(default=None, max_length=64)


class AdvertisingAccountRead(AdvertisingAccountCreate, OrmModel):
    id: int
    created_at: datetime
    updated_at: datetime


class CampaignCreate(BaseModel):
    account_id: int
    platform: AdvertisingPlatform
    external_campaign_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=64)
    channel_type: str | None = Field(default=None, max_length=64)


class CampaignRead(CampaignCreate, OrmModel):
    id: int
    created_at: datetime
    updated_at: datetime


class AdGroupCreate(BaseModel):
    campaign_id: int
    platform: AdvertisingPlatform
    external_ad_group_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=64)


class AdSetCreate(BaseModel):
    campaign_id: int
    platform: AdvertisingPlatform
    external_ad_set_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=64)


class AdCreate(BaseModel):
    platform: AdvertisingPlatform
    external_ad_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=64)
    ad_group_id: int | None = None
    ad_set_id: int | None = None

    @model_validator(mode="after")
    def require_one_parent(self) -> "AdCreate":
        if (self.ad_group_id is None) == (self.ad_set_id is None):
            raise ValueError("exactly one of ad_group_id or ad_set_id is required")
        return self


class KeywordCreate(BaseModel):
    ad_group_id: int
    platform: AdvertisingPlatform
    external_keyword_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=512)
    match_type: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=64)


class SearchTermCreate(BaseModel):
    ad_group_id: int
    platform: AdvertisingPlatform
    term: str = Field(min_length=1, max_length=512)
    match_type: str | None = Field(default=None, max_length=64)


class DailyMetricCreate(BaseModel):
    platform: AdvertisingPlatform
    metric_date: date
    entity_type: MetricEntityType
    entity_id: int
    campaign_id: int = Field(ge=1)
    ad_group_id: int | None = Field(default=None, ge=1)
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    cost_micros: int = Field(default=0, ge=0)
    conversions: Decimal = Field(default=Decimal("0"), ge=0)
    conversion_value_micros: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_entity_scope(self) -> "DailyMetricCreate":
        if self.entity_type is MetricEntityType.CAMPAIGN:
            if self.entity_id != self.campaign_id or self.ad_group_id is not None:
                raise ValueError("campaign metrics require the campaign as the sole entity scope")
        elif self.ad_group_id is None or self.entity_id != self.ad_group_id:
            raise ValueError("ad-group metrics require matching campaign and ad-group scope")
        return self


class DailyMetricRead(DailyMetricCreate, OrmModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ConversionEventCreate(BaseModel):
    workspace_id: int = Field(default=1, ge=1)
    platform: AdvertisingPlatform
    external_conversion_id: str = Field(min_length=1, max_length=128)
    campaign_id: int | None = None
    occurred_at: datetime
    action_name: str = Field(min_length=1, max_length=255)
    value_micros: int = Field(default=0, ge=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)


class JobRunCreate(BaseModel):
    workspace_id: int = Field(default=1, ge=1)
    platform: AdvertisingPlatform
    account_id: int | None = None
    job_name: str = Field(min_length=1, max_length=128)
    status: JobRunStatus = JobRunStatus.PENDING


class NormalizedMetricsBatch(BaseModel):
    metrics: list[DailyMetricCreate] = Field(default_factory=list)
