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
    workspace_id: int
    platform: AdvertisingPlatform
    external_account_id: str
    name: str
    currency_code: str
    time_zone: str | None
    created_at: datetime
    updated_at: datetime


class AccountRef(ApiModel):
    id: int
    workspace_id: int
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
    conversions: Decimal | None
    conversion_value_micros: int | None


class AccountMetricSummaryResponse(BaseModel):
    account_id: int
    date_from: date
    date_to: date
    impressions: int
    clicks: int
    cost_micros: int
    conversions: Decimal | None
    conversion_value_micros: int | None
    ctr: Decimal
    average_cpc_micros: Decimal
    conversion_rate: Decimal | None
    cost_per_conversion_micros: Decimal | None


class JobRunResponse(ApiModel):
    id: int
    workspace_id: int = 1
    platform: AdvertisingPlatform
    account_id: int | None
    job_name: str
    status: JobRunStatus
    started_at: datetime
    finished_at: datetime | None
    records_processed: int
    error_message: str | None = Field(
        default=None,
        max_length=160,
        description="Fixed public failure message; stored diagnostics are never exposed.",
    )


class SyncStatusResponse(BaseModel):
    workspace_id: int
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


class SyncHealthResponse(BaseModel):
    status: str = Field(max_length=16)
    stale: bool
    running: bool
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_failure_summary: str | None = Field(default=None, max_length=120)
    success_age_seconds: int | None = Field(default=None, ge=0)
    stale_after_seconds: int = Field(ge=60, le=604800)


class ApiErrorResponse(BaseModel):
    detail: str


class MetricWindowResponse(BaseModel):
    account_id: int
    date_from: date
    date_to: date
    comparison_date_from: date
    comparison_date_to: date
    window_days: int
    days_with_metric_rows: int
    data_coverage_ratio: Decimal
    comparison_window_days: int
    comparison_days_with_metric_rows: int
    comparison_data_coverage_ratio: Decimal
    impressions: int
    clicks: int
    cost_micros: int
    conversions: Decimal | None
    ctr: Decimal
    average_cpc_micros: Decimal
    conversion_rate: Decimal | None
    cost_per_conversion_micros: Decimal | None
    data_coverage: str
    comparison_data_coverage: str


class FindingResponse(BaseModel):
    workspace_id: int
    advertising_account_id: int
    code: str
    severity: str
    message: str
    supporting_metrics: dict[str, str]


class RecommendationResponse(ApiModel):
    id: int
    workspace_id: int
    account_id: int
    campaign_id: int | None
    source_analysis_run_id: int | None
    platform: AdvertisingPlatform
    recommendation_type: str
    severity: str
    confidence: Decimal
    rationale: str
    supporting_metrics: dict[str, object]
    planned_action: dict[str, object]
    status: str
    generated_at: datetime
    expires_at: datetime


class RecommendationDecisionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=2000)


class ExecutionAuditResponse(ApiModel):
    id: int
    recommendation_id: int
    idempotency_key: str
    status: str
    dry_run: bool
    validation_errors: list[object]
    rollback_instructions: str
    created_at: datetime


class WorkspaceResponse(ApiModel):
    id: int
    slug: str
    name: str
    client_name: str
    status: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class WorkspaceConfigurationResponse(ApiModel):
    workspace_id: int
    analysis: dict[str, object]
    automation: dict[str, object]
    notifications: dict[str, object]
    branding: dict[str, object]


class WorkspaceMembershipResponse(ApiModel):
    id: int
    workspace_id: int
    principal: str
    role: str
    status: str


class WorkspaceIntegrationResponse(BaseModel):
    id: int
    workspace_id: int
    integration_key: str
    provider: str
    display_name: str
    status: str
    configuration: dict[str, object]
    credential_reference_configured: bool
