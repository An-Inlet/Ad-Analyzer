from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.measurement.models import (
    MeasurementContract,
    MeasurementEventMapping,
    MeasurementStageDefinition,
)


@dataclass(frozen=True)
class MeasurementContractSnapshot:
    contract: MeasurementContract
    stages: tuple[MeasurementStageDefinition, ...]
    mappings: tuple[MeasurementEventMapping, ...]


class MeasurementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_workspace(self, workspace_id: int) -> MeasurementContractSnapshot | None:
        contract = self.session.get(MeasurementContract, workspace_id)
        if contract is None:
            return None
        stages = tuple(
            self.session.scalars(
                select(MeasurementStageDefinition)
                .where(MeasurementStageDefinition.workspace_id == workspace_id)
                .order_by(
                    MeasurementStageDefinition.position.asc(),
                    MeasurementStageDefinition.id.asc(),
                )
            ).all()
        )
        mappings = tuple(
            self.session.scalars(
                select(MeasurementEventMapping)
                .where(MeasurementEventMapping.workspace_id == workspace_id)
                .order_by(
                    MeasurementEventMapping.event_source.asc(),
                    MeasurementEventMapping.source_event_type.asc(),
                    MeasurementEventMapping.id.asc(),
                )
            ).all()
        )
        return MeasurementContractSnapshot(contract=contract, stages=stages, mappings=mappings)
