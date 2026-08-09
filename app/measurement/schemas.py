from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
