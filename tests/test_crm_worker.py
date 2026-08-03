import json
from datetime import UTC, datetime

from app.crm.models import CrmConnection, CrmEventRecord, LeadAttribution
from app.crm.worker import CrmEventProcessor, handle_message
from app.database.session import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def event() -> dict[str, object]:
    return {
        "event_id": "evt-1",
        "event_type": "lead_created",
        "occurred_at": datetime.now(UTC).isoformat(),
        "crm_lead_id": "lead-1",
        "utm_source": "google",
        "payload_version": 1,
    }


def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    result = Session(engine)
    result.add(
        CrmConnection(
            name="fake", status="active", secret_manager_reference="projects/fake/secrets/crm"
        )
    )
    result.commit()
    return result


def test_worker_is_idempotent_and_updates_attribution() -> None:
    db = session()
    processor = CrmEventProcessor(db)
    assert processor.process(event()) is True
    assert processor.process(event()) is False
    assert len(list(db.scalars(select(CrmEventRecord)))) == 1
    attribution = db.scalar(select(LeadAttribution))
    assert attribution is not None
    assert attribution.lifecycle_state == "lead_created"
    assert attribution.attribution_data == {"utm_source": "google"}


class Message:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.acked = False
        self.nacked = False

    def ack(self) -> None:
        self.acked = True

    def nack(self) -> None:
        self.nacked = True


def test_worker_acknowledges_success() -> None:
    message = Message(json.dumps(event()).encode())
    handle_message(message, session())
    assert message.acked and not message.nacked


def test_worker_nacks_failure_for_retry() -> None:
    message = Message(b"not-json")
    handle_message(message, session())
    assert message.nacked and not message.acked

