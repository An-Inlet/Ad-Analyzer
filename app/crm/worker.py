import hashlib
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crm.models import CrmEventRecord, LeadAttribution
from app.crm.ownership import connection_for_scope
from app.crm.schemas import CrmEvent
from app.imports.models import ImportRejection
from app.imports.scope import ImportScopeError
from app.workspaces.models import WorkspaceIntegration

logger = logging.getLogger(__name__)
_ATTRIBUTION_FIELDS = (
    "analytics_pseudonymous_id",
    "gclid",
    "gbraid",
    "wbraid",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "landing_page",
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AcknowledgeableMessage(Protocol):
    data: bytes

    def ack(self) -> None: ...
    def nack(self) -> None: ...


class CrmEventProcessor:
    def __init__(self, session: Session) -> None:
        self.session = session

    def process(self, payload: Mapping[str, object]) -> bool:
        version = payload.get("payload_version")
        workspace_id, connection_id = payload.get("workspace_id"), payload.get("connection_id")
        if type(version) is not int or version != 2:
            raise ImportScopeError("unsupported CRM envelope")
        if (
            type(workspace_id) is not int
            or type(connection_id) is not int
            or workspace_id < 1
            or connection_id < 1
        ):
            raise ImportScopeError("invalid CRM scope")
        connection = connection_for_scope(self.session, workspace_id, connection_id)
        integration = self.session.get(WorkspaceIntegration, connection_id)
        if integration is None or payload.get("provider") != integration.provider:
            raise ImportScopeError("CRM provider mismatch")
        event_data = {
            key: value
            for key, value in payload.items()
            if key not in {"payload_version", "workspace_id", "connection_id", "provider"}
        }
        event = CrmEvent.model_validate(event_data)
        existing = self.session.scalar(
            select(CrmEventRecord).where(
                CrmEventRecord.connection_id == connection.id,
                CrmEventRecord.external_event_id == event.event_id,
            )
        )
        if existing is not None:
            return False
        canonical = event.model_dump(mode="json", exclude_none=True)
        payload_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        record = CrmEventRecord(
            connection_id=connection.id,
            external_event_id=event.event_id,
            event_type=event.event_type.value,
            occurred_at=event.occurred_at,
            crm_lead_id=event.crm_lead_id,
            payload_version=2,
            payload_hash=payload_hash,
            normalized_payload=canonical,
            processing_status="processed",
            processed_at=datetime.now(UTC),
        )
        attribution = self.session.scalar(
            select(LeadAttribution).where(
                LeadAttribution.connection_id == connection.id,
                LeadAttribution.crm_lead_id == event.crm_lead_id,
            )
        )
        attrs = {key: canonical[key] for key in _ATTRIBUTION_FIELDS if key in canonical}
        if attribution is None:
            attribution = LeadAttribution(
                connection_id=connection.id,
                crm_lead_id=event.crm_lead_id,
                lifecycle_state=event.event_type.value,
                lifecycle_occurred_at=event.occurred_at,
                attribution_data=attrs,
            )
            self.session.add(attribution)
        elif _utc(event.occurred_at) >= _utc(attribution.lifecycle_occurred_at):
            attribution.lifecycle_state = event.event_type.value
            attribution.lifecycle_occurred_at = event.occurred_at
            attribution.attribution_data = {**attribution.attribution_data, **attrs}
        attribution.crm_opportunity_id = event.crm_opportunity_id or attribution.crm_opportunity_id
        attribution.value = event.value
        attribution.currency = event.currency
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            duplicate = self.session.scalar(
                select(CrmEventRecord.id).where(
                    CrmEventRecord.connection_id == connection.id,
                    CrmEventRecord.external_event_id == event.event_id,
                )
            )
            if duplicate is None:
                raise
            return False
        return True


def record_scope_rejection(session: Session, data: bytes) -> None:
    session.rollback()
    fingerprint = hashlib.sha256(data).hexdigest()
    if session.get(ImportRejection, fingerprint) is None:
        session.add(ImportRejection(digest=fingerprint, reason="crm_scope_rejected"))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()


def handle_message(message: AcknowledgeableMessage, session: Session) -> None:
    """Acknowledge duplicates/success; nack any failure so Pub/Sub can retry or dead-letter."""
    try:
        payload = json.loads(message.data)
        if not isinstance(payload, dict):
            raise ValueError("event must be an object")
        CrmEventProcessor(session).process(payload)
    except ImportScopeError:
        try:
            record_scope_rejection(session, message.data)
        except Exception:
            session.rollback()
            logger.warning("CRM quarantine index unavailable; delivery will retry")
        logger.warning("CRM scope rejected; payload omitted; dead-letter delivery required")
        message.nack()
        return
    except Exception as exc:
        session.rollback()
        logger.warning("CRM event processing failed: %s (payload omitted)", exc.__class__.__name__)
        message.nack()
        return
    message.ack()
