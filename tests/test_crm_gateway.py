import hashlib
import hmac
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from app.crm.dependencies import get_publisher, get_replay_guard
from app.crm.publisher import FakeEventPublisher
from app.crm.replay import InMemoryReplayGuard
from app.main import app
from app.settings import settings
from fastapi.testclient import TestClient
from pydantic import SecretStr

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
    old = settings.crm_webhook_secret
    settings.crm_webhook_secret = SecretStr(SECRET)
    try:
        yield TestClient(app, raise_server_exceptions=False), publisher
    finally:
        settings.crm_webhook_secret = old
        app.dependency_overrides.clear()


def signed_request(
    data: dict[str, object], *, age: timedelta = timedelta(), signature: str | None = None
) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(data, separators=(",", ":")).encode()
    timestamp = str(int((datetime.now(UTC) - age).timestamp()))
    digest = hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
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
    response = client.post("/v1/crm/events", content=body, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["receipt_id"].startswith("rcpt_")
    assert publisher.events[0]["payload_version"] == 1


def test_invalid_signature(crm_client: tuple[TestClient, FakeEventPublisher]) -> None:
    client, _ = crm_client
    body, headers = signed_request(payload(), signature="0" * 64)
    response = client.post("/v1/crm/events", content=body, headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_authentication"}


def test_expired_timestamp(crm_client: tuple[TestClient, FakeEventPublisher]) -> None:
    client, _ = crm_client
    body, headers = signed_request(payload(), age=timedelta(minutes=6))
    assert client.post("/v1/crm/events", content=body, headers=headers).status_code == 401


def test_missing_headers(crm_client: tuple[TestClient, FakeEventPublisher]) -> None:
    client, _ = crm_client
    response = client.post("/v1/crm/events", json=payload())
    assert response.status_code == 401
    assert response.json() == {"detail": "authentication_required"}


def test_duplicate_event(crm_client: tuple[TestClient, FakeEventPublisher]) -> None:
    client, publisher = crm_client
    body, headers = signed_request(payload())
    assert client.post("/v1/crm/events", content=body, headers=headers).status_code == 202
    assert client.post("/v1/crm/events", content=body, headers=headers).status_code == 409
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
    response = client.post("/v1/crm/events", content=body, headers=headers)
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_event"}
    assert not publisher.events


def test_publication_failure_is_sanitized_and_retryable() -> None:
    publisher = FakeEventPublisher(fail=True)
    guard = InMemoryReplayGuard()
    app.dependency_overrides[get_publisher] = lambda: publisher
    app.dependency_overrides[get_replay_guard] = lambda: guard
    old = settings.crm_webhook_secret
    settings.crm_webhook_secret = SecretStr(SECRET)
    try:
        body, headers = signed_request(payload())
        response = TestClient(app, raise_server_exceptions=False).post(
            "/v1/crm/events", content=body, headers=headers
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "service_unavailable"}
    finally:
        settings.crm_webhook_secret = old
        app.dependency_overrides.clear()


def test_health_endpoint_remains_public_and_minimal(
    crm_client: tuple[TestClient, FakeEventPublisher],
) -> None:
    client, _ = crm_client
    assert client.get("/health").json() == {"status": "ok"}
