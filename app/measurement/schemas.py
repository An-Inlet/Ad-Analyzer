from datetime import date, datetime
from decimal import Decimal

from app.measurement.enums import (
    AttributionModel,
    CustomerValueMode,
    MeasurementAuthority,
    MeasurementContractStatus,
    MeasurementEventSource,
    MeasurementSourceOfTruth,
    MeasurementStageCategory,
    MeasurementValueBehavior,
    PlatformConversionRole,
)
from app.measurement.repository import MeasurementContractSnapshot
from app.measurement.service import evaluate_measurement_readiness
from app.measurement.unified import UnifiedOutcomeSnapshot
from pydantic import BaseModel, ConfigDict


class MeasurementApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeasurementStageResponse(MeasurementApiModel):
    stage_key: str
    display_name: str
    position: int
    category: MeasurementStageCategory
    counts_toward_funnel: bool
    accepts_monetary_value: bool
    description: str


class MeasurementEventMappingResponse(MeasurementApiModel):
    event_source: MeasurementEventSource
    source_event_type: str
    stage_key: str
    authority: MeasurementAuthority
    value_behavior: MeasurementValueBehavior


class MeasurementContractResponse(BaseModel):
    workspace_id: int
    version: int
    status: MeasurementContractStatus
    effective_at: datetime | None
    currency_code: str
    source_of_truth: MeasurementSourceOfTruth
    platform_conversion_role: PlatformConversionRole
    attribution_model: AttributionModel
    click_lookback_days: int
    engaged_view_lookback_days: int
    outcome_maturity_days: int
    customer_value_mode: CustomerValueMode
    customer_value_horizon_days: int
    optimization_goal_stage_key: str
    business_value_stage_key: str
    analysis_ready: bool
    blocking_reasons: list[str]
    stages: list[MeasurementStageResponse]
    event_mappings: list[MeasurementEventMappingResponse]

    @classmethod
    def from_snapshot(cls, snapshot: MeasurementContractSnapshot) -> "MeasurementContractResponse":
        readiness = evaluate_measurement_readiness(snapshot)
        contract = snapshot.contract
        return cls(
            workspace_id=contract.workspace_id,
            version=contract.version,
            status=MeasurementContractStatus(contract.status),
            effective_at=contract.effective_at,
            currency_code=contract.currency_code,
            source_of_truth=MeasurementSourceOfTruth(contract.source_of_truth),
            platform_conversion_role=PlatformConversionRole(contract.platform_conversion_role),
            attribution_model=AttributionModel(contract.attribution_model),
            click_lookback_days=contract.click_lookback_days,
            engaged_view_lookback_days=contract.engaged_view_lookback_days,
            outcome_maturity_days=contract.outcome_maturity_days,
            customer_value_mode=CustomerValueMode(contract.customer_value_mode),
            customer_value_horizon_days=contract.customer_value_horizon_days,
            optimization_goal_stage_key=contract.optimization_goal_stage_key,
            business_value_stage_key=contract.business_value_stage_key,
            analysis_ready=readiness.analysis_ready,
            blocking_reasons=list(readiness.blocking_reasons),
            stages=[MeasurementStageResponse.model_validate(stage) for stage in snapshot.stages],
            event_mappings=[
                MeasurementEventMappingResponse.model_validate(mapping)
                for mapping in snapshot.mappings
            ],
        )


class UnifiedSourceCoverageResponse(MeasurementApiModel):
    advertising_metric_days: int
    ad_group_metric_days: int
    ga4_event_count: int
    paid_session_count: int
    crm_event_count: int
    mapped_crm_event_count: int
    attributed_journey_count: int
    unattributed_journey_count: int
    attribution_rate: Decimal | None
    ad_group_attributed_journey_count: int
    ad_group_unattributed_journey_count: int
    ad_group_attribution_rate: Decimal | None
    currency_mismatch_count: int


class OutcomeMetricsResponse(MeasurementApiModel):
    advertising_metric_days: int
    metric_coverage_ratio: Decimal
    impressions: int
    clicks: int
    cost_micros: int
    platform_conversion_count: Decimal
    platform_conversion_value_micros: int
    ga4_event_count: int
    paid_session_count: int
    lead_count: int
    optimization_outcome_count: int
    business_outcome_count: int
    cancelled_outcome_count: int
    observed_revenue_micros: int
    click_through_rate: Decimal | None
    platform_conversion_rate: Decimal | None
    click_to_paid_session_rate: Decimal | None
    paid_session_to_lead_rate: Decimal | None
    optimization_outcome_rate: Decimal | None
    business_outcome_rate: Decimal | None
    lead_to_business_outcome_rate: Decimal | None
    funnel_drop_off_rate: Decimal | None
    cancellation_rate: Decimal | None
    revenue_per_click_micros: int | None
    revenue_per_paid_session_micros: int | None
    revenue_per_lead_micros: int | None
    revenue_per_optimization_outcome_micros: int | None
    revenue_per_business_outcome_micros: int | None
    cost_per_lead_micros: int | None
    cost_per_optimization_outcome_micros: int | None
    cost_per_business_outcome_micros: int | None
    observed_roas: Decimal | None
    median_outcome_lag_days: Decimal | None


class AdGroupOutcomeResponse(MeasurementApiModel):
    ad_group_id: int
    ad_group_name: str
    metrics: OutcomeMetricsResponse


class CampaignOutcomeResponse(MeasurementApiModel):
    account_id: int
    campaign_id: int
    platform: str
    campaign_name: str
    metrics: OutcomeMetricsResponse
    ad_groups: list[AdGroupOutcomeResponse]


class UnifiedOutcomeResponse(BaseModel):
    workspace_id: int
    cohort_date_from: date
    cohort_date_to: date
    mature_through: date | None
    as_of: datetime
    contract_version: int | None
    currency_code: str | None
    optimization_goal_stage_key: str | None
    business_value_stage_key: str | None
    analysis_ready: bool
    blocking_reasons: list[str]
    ad_group_analysis_ready: bool
    ad_group_blocking_reasons: list[str]
    source_coverage: UnifiedSourceCoverageResponse
    totals: OutcomeMetricsResponse | None
    campaigns: list[CampaignOutcomeResponse]

    @classmethod
    def from_snapshot(cls, snapshot: UnifiedOutcomeSnapshot) -> "UnifiedOutcomeResponse":
        return cls(
            workspace_id=snapshot.workspace_id,
            cohort_date_from=snapshot.cohort_date_from,
            cohort_date_to=snapshot.cohort_date_to,
            mature_through=snapshot.mature_through,
            as_of=snapshot.as_of,
            contract_version=snapshot.contract_version,
            currency_code=snapshot.currency_code,
            optimization_goal_stage_key=snapshot.optimization_goal_stage_key,
            business_value_stage_key=snapshot.business_value_stage_key,
            analysis_ready=snapshot.analysis_ready,
            blocking_reasons=list(snapshot.blocking_reasons),
            ad_group_analysis_ready=snapshot.ad_group_analysis_ready,
            ad_group_blocking_reasons=list(snapshot.ad_group_blocking_reasons),
            source_coverage=UnifiedSourceCoverageResponse.model_validate(
                snapshot.source_coverage
            ),
            totals=(
                OutcomeMetricsResponse.model_validate(snapshot.totals)
                if snapshot.totals is not None
                else None
            ),
            campaigns=[CampaignOutcomeResponse.model_validate(item) for item in snapshot.campaigns],
        )
