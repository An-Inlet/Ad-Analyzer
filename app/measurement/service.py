from dataclasses import dataclass

from app.measurement.enums import (
    MeasurementAuthority,
    MeasurementContractStatus,
)
from app.measurement.repository import MeasurementContractSnapshot


@dataclass(frozen=True)
class MeasurementReadiness:
    analysis_ready: bool
    blocking_reasons: tuple[str, ...]


def evaluate_measurement_readiness(
    snapshot: MeasurementContractSnapshot,
) -> MeasurementReadiness:
    """Validate structural readiness without reading or contacting external systems."""
    contract = snapshot.contract
    stage_keys = {stage.stage_key for stage in snapshot.stages}
    reasons: list[str] = []
    if contract.status != MeasurementContractStatus.ACTIVE.value:
        reasons.append("measurement_contract_not_active")
    if contract.optimization_goal_stage_key not in stage_keys:
        reasons.append("optimization_goal_stage_missing")
    if contract.business_value_stage_key not in stage_keys:
        reasons.append("business_value_stage_missing")
    if not any(
        mapping.event_source == contract.source_of_truth
        and mapping.authority == MeasurementAuthority.AUTHORITATIVE.value
        for mapping in snapshot.mappings
    ):
        reasons.append("authoritative_outcome_mapping_missing")
    return MeasurementReadiness(
        analysis_ready=not reasons,
        blocking_reasons=tuple(reasons),
    )
