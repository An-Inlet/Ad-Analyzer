import hashlib
import hmac
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from app.crm.dependencies import get_publisher, get_replay_guard
from app.crm.models import CrmConnection
from app.crm.ownership import get_secret_reader
from app.crm.publisher import FakeEventPublisher
from app.crm.replay import InMemoryReplayGuard
from app.database.session import Base, get_db
from app.main import app
from app.workspaces.models import Workspace, WorkspaceIntegration
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

SECRET = "fake-local-test-secret"


def payload(**updates: object) -> dict[str, object]:
    data: dict[str, object] = {
        "event_id": "evt-test-1",
        "event_type": "lead_created",
        "occurred_at": "2026-07-29T12:00:00Z",
        "crm_lead_id": "lead-fake-1",
        "gclid": "fake-click-id",
        "utm_source": "google",
    }
    data.update(updates)
    return data


@pytest.fixture
def crm_client() -> Generator[tuple[TestClient, FakeEventPublisher]]:
    publisher = FakeEventPublisher()
    guard = InMemoryReplayGuard()
    app.dependency_overrides[get_publisher] = lambda: publisher
    app.dependency_overrides[get_replay_guard] = lambda: guard
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Workspace(id=1, slug="brand", name="Brand", client_name="Brand"))
    db.flush()
    db.add(
        WorkspaceIntegration(
            id=1,
            workspace_id=1,
            integration_key="crm-test",
            provider="hubspot",
            display_name="CRM",
            status="active",
            configuration={},
        )
    )
    db.flush()
    db.add(
        CrmConnection(
            id=1,
            workspace_id=1,
            workspace_integration_id=1,
            name="CRM",
            status="active",
            secret_manager_reference="projects/fake/secrets/crm/versions/1",
        )
    )
    db.commit()

    class FakeSecretReader:
        def read(self, reference: str) -> str:
            assert reference == "projects/fake/secrets/crm/versions/1"
            return SECRET

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_secret_reader] = FakeSecretReader
    try:
        yield TestClient(app, raise_server_exceptions=False), publisher
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def signed_request(
    data: dict[str, object], *, age: timedelta = timedelta(), signature: str | None = None
) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(data, separators=(",", ":")).encode()
    timestamp = str(int((datetime.now(UTC) - age).timestamp()))
    digest = hmac.new(
        SECRET.encode(), f"v2:1:1:{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return body, {
        "X-AnInlet-Event-Id": str(data.get("event_id", "evt-test-1")),
        "X-AnInlet-Timestamp": timestamp,
        "X-AnInlet-Signature": signature or digest,
        "Content-Type": "application/json",
    }


def test_valid_event_is_published_and_returns_safe_receipt(
    crm_client: tuple[TestClient, FakeEventPublisher],
) -> None:
    client, publisher = crm_client
    body, headers = signed_request(payload())
    response = client.post(
        "/v1/crm/workspaces/1/connections/1/events", content=body, headers=headers
    )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["receipt_id"].startswith("rcpt_")
    assert publisher.events[0]["payload_version"] == 2


def test_invalid_signature(crm_client: tuple[TestClient, FakeEventPublisher]) -> None:
    client, _ = crm_client
    body, headers = signed_request(payload(), signature="0" * 64)
    response = client.post(
        "/v1/crm/workspaces/1/connections/1/events", content=body, headers=headers
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_authentication"}


def test_expired_timestamp(crm_client: tuple[TestClient, FakeEventPublisher]) -> None:
    client, _ = crm_client
    body, headers = signed_request(payload(), age=timedelta(minutes=6))
    assert (
        client.post(
            "/v1/crm/workspaces/1/connections/1/events", content=body, headers=headers
        ).status_code
        == 401
    )


def test_missing_headers(crm_client: tuple[TestClient, FakeEventPublisher]) -> None:
    client, _ = crm_client
    response = client.post("/v1/crm/workspaces/1/connections/1/events", json=payload())
    assert response.status_code == 401
    assert response.json() == {"detail": "authentication_required"}


def test_duplicate_event(crm_client: tuple[TestClient, FakeEventPublisher]) -> None:
    client, publisher = crm_client
    body, headers = signed_request(payload())
    assert (
        client.post(
            "/v1/crm/workspaces/1/connections/1/events", content=body, headers=headers
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/v1/crm/workspaces/1/connections/1/events", content=body, headers=headers
        ).status_code
        == 409
    )
    assert len(publisher.events) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"event_type": "patient_seen"},
        {"unexpected": "no"},
        {"email": "fake@example.invalid"},
        {"diagnosis": "prohibited"},
    ],
)
def test_strict_schema_rejects_invalid_unknown_and_phi_fields(
    crm_client: tuple[TestClient, FakeEventPublisher], change: dict[str, object]
) -> None:
    client, publisher = crm_client
    body, headers = signed_request(payload(**change))
    response = client.post(
        "/v1/crm/workspaces/1/connections/1/events", content=body, headers=headers
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_event"}
    assert not publisher.events


def test_publication_failure_is_sanitized_and_retryable(
    crm_client: tuple[TestClient, FakeEventPublisher],
) -> None:
    client, publisher = crm_client
    publisher.fail = True
    body, headers = signed_request(payload())
    response = client.post(
        "/v1/crm/workspaces/1/connections/1/events", content=body, headers=headers
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "service_unavailable"}


def test_health_endpoint_remains_public_and_minimal(
    crm_client: tuple[TestClient, FakeEventPublisher],
) -> None:
    client, _ = crm_client
    assert client.get("/health").json() == {"status": "ok"}


def test_legacy_unscoped_gateway_is_rejected(
    crm_client: tuple[TestClient, FakeEventPublisher],
) -> None:
    client, publisher = crm_client
    body, headers = signed_request(payload())
    assert client.post("/v1/crm/events", content=body, headers=headers).status_code == 422
    assert publisher.events == []
