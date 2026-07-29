import hashlib
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crm.models import CrmConnection, CrmEventRecord, LeadAttribution
from app.crm.schemas import CrmEvent

logger = logging.getLogger(__name__)
_ATTRIBUTION_FIELDS = (
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


class AcknowledgeableMessage(Protocol):
    data: bytes

    def ack(self) -> None: ...
    def nack(self) -> None: ...


class CrmEventProcessor:
    def __init__(self, session: Session) -> None:
        self.session = session

    def process(self, payload: Mapping[str, object]) -> bool:
        version = payload.get("payload_version")
        event_data = {key: value for key, value in payload.items() if key != "payload_version"}
        event = CrmEvent.model_validate(event_data)
        if version != 1:
            raise ValueError("unsupported payload version")
        connection = self.session.scalar(
            select(CrmConnection).where(CrmConnection.status == "active").order_by(CrmConnection.id)
        )
        if connection is None:
            raise RuntimeError("no active CRM connection")
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
            payload_version=1,
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
        elif event.occurred_at >= attribution.lifecycle_occurred_at:
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
            return False
        return True


def handle_message(message: AcknowledgeableMessage, session: Session) -> None:
    """Acknowledge duplicates/success; nack any failure so Pub/Sub can retry or dead-letter."""
    try:
        payload = json.loads(message.data)
        if not isinstance(payload, dict):
            raise ValueError("event must be an object")
        CrmEventProcessor(session).process(payload)
    except Exception as exc:
        session.rollback()
        logger.warning("CRM event processing failed: %s (payload omitted)", exc.__class__.__name__)
        message.nack()
        return
    message.ack()
