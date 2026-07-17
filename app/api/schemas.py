from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.ads.enums import AdvertisingPlatform, JobRunStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse[T](BaseModel):
    items: list[T]
    limit: int
    offset: int
    total: int


class AccountResponse(ApiModel):
    id: int
    platform: AdvertisingPlatform
    external_account_id: str
    name: str
    currency_code: str
    time_zone: str | None
    created_at: datetime
    updated_at: datetime


class AccountRef(ApiModel):
    id: int
    platform: AdvertisingPlatform
    external_account_id: str
    name: str


class CampaignResponse(ApiModel):
    id: int
    account_id: int
    platform: AdvertisingPlatform
    external_campaign_id: str
    name: str
    status: str | None
    channel_type: str | None
    created_at: datetime
    updated_at: datetime


class CampaignDetailResponse(CampaignResponse):
    account: AccountRef


class AdGroupResponse(ApiModel):
    id: int
    campaign_id: int
    platform: AdvertisingPlatform
    external_ad_group_id: str
    name: str
    status: str | None
    created_at: datetime
    updated_at: datetime


class DailyMetricResponse(ApiModel):
    metric_date: date
    impressions: int
    clicks: int
    cost_micros: int
    conversions: Decimal
    conversion_value_micros: int


class AccountMetricSummaryResponse(BaseModel):
    account_id: int
    date_from: date
    date_to: date
    impressions: int
    clicks: int
    cost_micros: int
    conversions: Decimal
    conversion_value_micros: int
    ctr: Decimal
    average_cpc_micros: Decimal
    conversion_rate: Decimal
    cost_per_conversion_micros: Decimal


class JobRunResponse(ApiModel):
    id: int
    platform: AdvertisingPlatform
    account_id: int | None
    job_name: str
    status: JobRunStatus
    started_at: datetime
    finished_at: datetime | None
    records_processed: int
    error_message: str | None = Field(description="Already-sanitized bounded error message.")


class SyncStatusResponse(BaseModel):
    account_id: int
    platform: AdvertisingPlatform
    external_account_id: str
    account_name: str
    latest_job_run_id: int | None
    latest_status: JobRunStatus | None
    latest_started_at: datetime | None
    latest_finished_at: datetime | None
    records_processed: int | None
    last_success_at: datetime | None


class ApiErrorResponse(BaseModel):
    detail: str
