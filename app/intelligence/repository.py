import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.intelligence.models import IntelligenceRecord, IntelligenceRevision
from app.intelligence.schemas import (
    PAYLOAD_MODELS,
    Creative,
    Decision,
    Experiment,
    RecordKind,
    SaveRecord,
)


class ContextConflict(ValueError):
    pass


class ContextNotFound(ValueError):
    pass


class IntelligenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_records(
        self, workspace_id: int, kind: RecordKind, *, limit: int = 200, offset: int = 0
    ) -> list[IntelligenceRecord]:
        return list(
            self.session.scalars(
                select(IntelligenceRecord)
                .where(
                    IntelligenceRecord.workspace_id == workspace_id,
                    IntelligenceRecord.kind == kind.value,
                )
                .order_by(IntelligenceRecord.updated_at.desc(), IntelligenceRecord.id.desc())
                .limit(min(limit, 500))
                .offset(offset)
            )
        )

    def count(self, workspace_id: int, kind: RecordKind) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(IntelligenceRecord)
                .where(
                    IntelligenceRecord.workspace_id == workspace_id,
                    IntelligenceRecord.kind == kind.value,
                )
            )
            or 0
        )

    def get(self, workspace_id: int, record_id: int) -> IntelligenceRecord:
        record = self.session.scalar(
            select(IntelligenceRecord).where(
                IntelligenceRecord.workspace_id == workspace_id,
                IntelligenceRecord.id == record_id,
            )
        )
        if record is None:
            raise ContextNotFound("Business record not found.")
        return record

    def strategy(self, workspace_id: int) -> IntelligenceRecord | None:
        return self.session.scalar(
            select(IntelligenceRecord).where(
                IntelligenceRecord.workspace_id == workspace_id,
                IntelligenceRecord.kind == RecordKind.STRATEGY.value,
                IntelligenceRecord.record_key == "active",
            )
        )

    def save(
        self,
        workspace_id: int,
        kind: RecordKind,
        command: SaveRecord,
        *,
        actor_role: str,
        record_id: int | None = None,
        restoring: bool = False,
    ) -> IntelligenceRecord:
        if actor_role not in {"platform_admin", "owner", "admin", "operator"}:
            raise PermissionError("Business context changes require an administrator.")
        if len(json.dumps(command.payload)) > 24_000:
            raise ValueError("Business record is too large.")
        payload = PAYLOAD_MODELS[kind].model_validate(command.payload)
        data = payload.model_dump(mode="json")
        record = self.get(workspace_id, record_id) if record_id else None
        if record is None and kind == RecordKind.STRATEGY:
            record = self.strategy(workspace_id)
        if record is not None and record.kind != kind.value:
            raise ContextNotFound("Business record not found.")
        if (record.version if record else 0) != command.expected_version:
            raise ContextConflict("This record changed. Reload before saving.")
        if isinstance(payload, Creative):
            owned = self.session.scalar(
                select(Campaign.id)
                .join(AdvertisingAccount)
                .where(
                    Campaign.id == payload.campaign_id,
                    AdvertisingAccount.workspace_id == workspace_id,
                )
            )
            if owned is None:
                raise ValueError("Campaign is unavailable in this workspace.")
        if record and isinstance(payload, Experiment):
            previous = Experiment.model_validate(record.data)
            if previous.status != "planned":
                design_fields = (
                    "primary_metric",
                    "hypothesis",
                    "starts_on",
                    "ends_on",
                    "measurement_delay_days",
                    "minimum_sample_per_arm",
                    "minimum_lift_bps",
                    "randomized_assignment",
                    "control_description",
                    "treatment_description",
                )
                if any(getattr(previous, f) != getattr(payload, f) for f in design_fields):
                    raise ValueError("Create a new experiment to change a running test design.")
                if payload.status == "planned":
                    raise ValueError("A started experiment cannot return to planned.")
        if isinstance(payload, Decision) and record:
            old = Decision.model_validate(record.data)
            if old.recommendation_key != payload.recommendation_key:
                raise ValueError("A decision must retain its original recommendation.")
            if old.evidence_fingerprint != payload.evidence_fingerprint:
                raise ValueError("A decision must retain its original evidence.")
            if old.evidence_snapshot != payload.evidence_snapshot:
                raise ValueError("A decision must retain its original evidence snapshot.")
        before = dict(record.data) if record else None
        now = datetime.now(UTC)
        with self.session.begin_nested():
            if record is None:
                if command.expected_version:
                    raise ContextConflict("This record changed. Reload before saving.")
                record = IntelligenceRecord(
                    workspace_id=workspace_id,
                    kind=kind.value,
                    record_key=(
                        "active"
                        if kind == RecordKind.STRATEGY
                        else hashlib.sha256(
                            (payload.recommendation_key + payload.evidence_fingerprint).encode()
                        ).hexdigest()
                        if isinstance(payload, Decision)
                        else str(uuid4())
                    ),
                    version=1,
                    data=data,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(record)
                try:
                    self.session.flush()
                except IntegrityError:
                    raise ContextConflict("This record changed. Reload before saving.") from None
            else:
                result = self.session.execute(
                    update(IntelligenceRecord)
                    .where(
                        IntelligenceRecord.id == record.id,
                        IntelligenceRecord.workspace_id == workspace_id,
                        IntelligenceRecord.version == command.expected_version,
                    )
                    .values(data=data, version=command.expected_version + 1, updated_at=now)
                )
                if result.rowcount != 1:  # type: ignore[attr-defined]
                    raise ContextConflict("This record changed. Reload before saving.")
                self.session.refresh(record)
            self.session.add(
                IntelligenceRevision(
                    workspace_id=workspace_id,
                    record_id=record.id,
                    version=record.version,
                    kind=kind.value,
                    action="restore" if restoring else ("update" if before else "create"),
                    actor_role=actor_role,
                    before_data=before,
                    after_data=data,
                    created_at=now,
                )
            )
            self.session.flush()
        return record

    def revisions(self, workspace_id: int, *, limit: int = 100) -> list[IntelligenceRevision]:
        return list(
            self.session.scalars(
                select(IntelligenceRevision)
                .where(
                    IntelligenceRevision.workspace_id == workspace_id,
                )
                .order_by(IntelligenceRevision.created_at.desc(), IntelligenceRevision.id.desc())
                .limit(limit)
            )
        )

    def restore_strategy(
        self,
        workspace_id: int,
        revision_id: int,
        expected_version: int,
        actor_role: str,
    ) -> IntelligenceRecord:
        revision = self.session.scalar(
            select(IntelligenceRevision).where(
                IntelligenceRevision.id == revision_id,
                IntelligenceRevision.workspace_id == workspace_id,
                IntelligenceRevision.kind == RecordKind.STRATEGY.value,
            )
        )
        if revision is None:
            raise ContextNotFound("Strategy revision not found.")
        return self.save(
            workspace_id,
            RecordKind.STRATEGY,
            SaveRecord(expected_version=expected_version, payload=revision.after_data),
            actor_role=actor_role,
            record_id=revision.record_id,
            restoring=True,
        )


def record_dict(record: IntelligenceRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "version": record.version,
        "kind": record.kind,
        "data": record.data,
        "updated_at": record.updated_at.isoformat(),
    }
