from datetime import date, datetime
from decimal import Decimal

from app.ads.enums import AdvertisingPlatform, MetricEntityType
from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
from app.analysis.granular import PerformanceScopeSnapshot
from app.optimizer.analytics import MetricWindow
from pydantic import BaseModel, ConfigDict, Field


class AnalysisRunResponse(BaseModel):
    """Aggregate-only operator response; no raw analytics or CRM identifiers."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    account_id: int | None
    source_job_run_id: int | None
    cadence: AnalysisCadence
    status: AnalysisRunStatus
    schedule_policy_version: str
    scheduled_for: datetime
    metric_date_from: date
    metric_date_to: date
    outcome_date_from: date
    outcome_date_to: date
    started_at: datetime
    finished_at: datetime | None
    accounts_analyzed: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    high_severity_findings_count: int = Field(ge=0)
    outcome_analysis_ready: bool
    outcome_campaign_count: int = Field(ge=0)
    attributed_journey_count: int = Field(ge=0)
    unattributed_journey_count: int = Field(ge=0)
    blocking_reasons: list[str]
    error_code: str | None


class PerformanceWindowResponse(BaseModel):
    date_from: date
    date_to: date
    window_days: int = Field(ge=1)
    days_with_metric_rows: int = Field(ge=0)
    data_coverage_ratio: Decimal = Field(ge=0, le=1)
    data_coverage: str
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    cost_micros: int = Field(ge=0)
    platform_conversions: Decimal = Field(ge=0)
    platform_conversion_value_micros: int = Field(ge=0)
    click_through_rate: Decimal = Field(ge=0)
    average_cpc_micros: Decimal = Field(ge=0)
    platform_conversion_rate: Decimal = Field(ge=0)
    cost_per_platform_conversion_micros: Decimal = Field(ge=0)
    platform_roas: Decimal = Field(ge=0)

    @classmethod
    def from_window(cls, window: MetricWindow) -> "PerformanceWindowResponse":
        return cls(
            date_from=window.date_from,
            date_to=window.date_to,
            window_days=window.window_days,
            days_with_metric_rows=window.days_with_metric_rows,
            data_coverage_ratio=window.data_coverage_ratio,
            data_coverage=window.coverage_status,
            impressions=window.impressions,
            clicks=window.clicks,
            cost_micros=window.cost_micros,
            platform_conversions=window.conversions,
            platform_conversion_value_micros=window.conversion_value_micros,
            click_through_rate=window.ctr,
            average_cpc_micros=window.average_cpc_micros,
            platform_conversion_rate=window.conversion_rate,
            cost_per_platform_conversion_micros=window.cost_per_conversion_micros,
            platform_roas=window.roas,
        )


class ScopedFindingResponse(BaseModel):
    code: str
    severity: str
    message: str
    supporting_metrics: dict[str, str]


class PerformanceScopeResponse(BaseModel):
    workspace_id: int
    platform: AdvertisingPlatform
    account_id: int
    account_name: str
    campaign_id: int
    campaign_name: str
    entity_type: MetricEntityType
    entity_id: int
    entity_name: str
    status: str | None
    current: PerformanceWindowResponse
    comparison: PerformanceWindowResponse
    findings: list[ScopedFindingResponse]

    @classmethod
    def from_snapshot(cls, snapshot: PerformanceScopeSnapshot) -> "PerformanceScopeResponse":
        return cls(
            workspace_id=snapshot.workspace_id,
            platform=snapshot.platform,
            account_id=snapshot.account_id,
            account_name=snapshot.account_name,
            campaign_id=snapshot.campaign_id,
            campaign_name=snapshot.campaign_name,
            entity_type=snapshot.entity_type,
            entity_id=snapshot.entity_id,
            entity_name=snapshot.entity_name,
            status=snapshot.status,
            current=PerformanceWindowResponse.from_window(snapshot.current),
            comparison=PerformanceWindowResponse.from_window(snapshot.comparison),
            findings=[ScopedFindingResponse(**finding.__dict__) for finding in snapshot.findings],
        )
