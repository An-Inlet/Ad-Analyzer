import base64
import hashlib
import hmac
import json
import time
from collections.abc import Generator

from app.api.crm import router as crm_router
from app.api.pubsub import router as push_router
from app.crm.dependencies import get_ingress_db, get_publisher, get_replay_guard
from app.crm.models import CrmEventRecord
from app.crm.ownership import get_secret_reader
from app.crm.publisher import FakeEventPublisher
from app.crm.replay import InMemoryReplayGuard
from app.database.session import get_db
from app.imports.models import ImportRejection
from app.workspaces.models import WorkspaceIntegration
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_import_ownership import owned_engine as owned_engine

TEST_SECRET = "synthetic-test-signing-material-only-0001"


def signed_event(
    workspace_id: int, connection_id: int, event_id: str
) -> tuple[bytes, dict[str, str]]:
    payload = {
        "event_id": event_id,
        "event_type": "lead_created",
        "crm_lead_id": "same-lead",
        "occurred_at": "2026-10-05T00:00:00Z",
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signed = f"v2:{workspace_id}:{connection_id}:{timestamp}.".encode() + body
    signature = hmac.new(TEST_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return body, {
        "X-AnInlet-Event-Id": event_id,
        "X-AnInlet-Timestamp": timestamp,
        "X-AnInlet-Signature": signature,
        "Content-Type": "application/json",
    }


def push_envelope(payload: dict[str, object]) -> dict[str, object]:
    return {"message": {"data": base64.b64encode(json.dumps(payload).encode()).decode()}}


def test_signed_ingress_to_worker_preserves_connection_and_workspace(owned_engine: Engine) -> None:
    publisher = FakeEventPublisher()
    guard = InMemoryReplayGuard()
    app = FastAPI()
    app.include_router(crm_router)
    app.include_router(push_router)

    def database() -> Generator[Session, None, None]:
        with Session(owned_engine) as db:
            yield db

    class FakeSecretReader:
        def read(self, reference: str) -> str:
            assert reference in {f"projects/fake/secrets/{i}/versions/1" for i in (102, 103, 202)}
            # Even accidentally shared provider secrets cannot authorize replay across routes.
            return TEST_SECRET

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_ingress_db] = database
    app.dependency_overrides[get_publisher] = lambda: publisher
    app.dependency_overrides[get_replay_guard] = lambda: guard
    app.dependency_overrides[get_secret_reader] = FakeSecretReader
    client = TestClient(app)
    for workspace_id, connection_id in [(10, 102), (10, 103), (20, 202)]:
        body, headers = signed_event(workspace_id, connection_id, "same-event")
        path = f"/v1/crm/workspaces/{workspace_id}/connections/{connection_id}/events"
        assert client.post(path, content=body, headers=headers).status_code == 202
        assert client.post(path, content=body, headers=headers).status_code == 409
    assert [(p["workspace_id"], p["connection_id"]) for p in publisher.events] == [
        (10, 102),
        (10, 103),
        (20, 202),
    ]
    for payload in publisher.events:
        assert (
            client.post("/internal/pubsub/crm-events", json=push_envelope(payload)).status_code
            == 204
        )
        assert (
            client.post("/internal/pubsub/crm-events", json=push_envelope(payload)).status_code
            == 204
        )
    with Session(owned_engine) as db:
        assert db.scalar(select(func.count()).select_from(CrmEventRecord)) == 3
    # A correctly signed request for A is invalid on B, even with identical secret bytes.
    body, headers = signed_event(10, 102, "wrong-route")
    assert (
        client.post(
            "/v1/crm/workspaces/10/connections/103/events", content=body, headers=headers
        ).status_code
        == 401
    )
    # Revoke after publication: the worker must recheck instead of trusting the envelope.
    body, headers = signed_event(10, 102, "queued-before-revocation")
    assert (
        client.post(
            "/v1/crm/workspaces/10/connections/102/events", content=body, headers=headers
        ).status_code
        == 202
    )
    with Session(owned_engine) as db:
        connection = db.get(WorkspaceIntegration, 102)
        assert connection is not None
        connection.status = "revoked"
        db.commit()
    response = client.post("/internal/pubsub/crm-events", json=push_envelope(publisher.events[-1]))
    assert response.status_code == 400 and response.json() == {"detail": "scope_rejected"}
    legacy = {"payload_version": 1, "event_id": "legacy-private-message"}
    assert client.post("/internal/pubsub/crm-events", json=push_envelope(legacy)).status_code == 400
    with Session(owned_engine) as db:
        assert db.scalar(select(func.count()).select_from(CrmEventRecord)) == 3
        assert db.scalar(select(func.count()).select_from(ImportRejection)) == 2
