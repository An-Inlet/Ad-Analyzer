import base64
import json
from collections.abc import Generator
from pathlib import Path

import pytest
from app.api import pubsub
from app.database.session import get_db
from app.main import app
from fastapi.testclient import TestClient


class FakeSession:
    def __init__(self) -> None:
        self.rolled_back = False

    def rollback(self) -> None:
        self.rolled_back = True


class FakeProcessor:
    result = True
    error: Exception | None = None
    payloads: list[dict[str, object]] = []

    def __init__(self, _session: object) -> None:
        pass

    def process(self, payload: dict[str, object]) -> bool:
        self.payloads.append(payload)
        if self.error is not None:
            raise self.error
        return self.result


def event() -> dict[str, object]:
    return {
        "event_id": "evt-push-1",
        "event_type": "lead_created",
        "occurred_at": "2026-07-29T12:00:00Z",
        "crm_lead_id": "lead-fake-1",
        "payload_version": 1,
    }


def envelope(payload: object) -> dict[str, object]:
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": encoded, "messageId": "safe-message-id"}}


@pytest.fixture
def push_client(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[TestClient, FakeSession]]:
    session = FakeSession()
    FakeProcessor.result = True
    FakeProcessor.error = None
    FakeProcessor.payloads = []
    monkeypatch.setattr(pubsub, "CrmEventProcessor", FakeProcessor)
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app, raise_server_exceptions=False), session
    finally:
        app.dependency_overrides.clear()


def test_valid_push_envelope_is_decoded_and_processed(
    push_client: tuple[TestClient, FakeSession],
) -> None:
    client, _ = push_client
    response = client.post("/internal/pubsub/crm-events", json=envelope(event()))

    assert response.status_code == 204
    assert FakeProcessor.payloads == [event()]


def test_invalid_base64_is_rejected(push_client: tuple[TestClient, FakeSession]) -> None:
    client, _ = push_client
    response = client.post(
        "/internal/pubsub/crm-events", json={"message": {"data": "not base64!"}}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_event"}


def test_invalid_normalized_event_is_rejected(push_client: tuple[TestClient, FakeSession]) -> None:
    client, session = push_client
    FakeProcessor.error = ValueError("sensitive raw value")

    response = client.post("/internal/pubsub/crm-events", json=envelope(event()))

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_event"}
    assert session.rolled_back is True


def test_successful_processing_acknowledges_delivery(
    push_client: tuple[TestClient, FakeSession],
) -> None:
    client, _ = push_client
    assert client.post("/internal/pubsub/crm-events", json=envelope(event())).status_code == 204


def test_duplicate_safe_processing_acknowledges_delivery(
    push_client: tuple[TestClient, FakeSession],
) -> None:
    client, _ = push_client
    FakeProcessor.result = False
    assert client.post("/internal/pubsub/crm-events", json=envelope(event())).status_code == 204


def test_processing_failure_is_retryable_and_sanitized(
    push_client: tuple[TestClient, FakeSession],
) -> None:
    client, session = push_client
    secret_payload = "patient-name-and-click-id"
    FakeProcessor.error = RuntimeError(secret_payload)

    response = client.post("/internal/pubsub/crm-events", json=envelope(event()))

    assert response.status_code == 503
    assert response.json() == {"detail": "processing_failed"}
    assert secret_payload not in response.text
    assert session.rolled_back is True


def test_managed_worker_uses_authenticated_push_without_pull_permissions() -> None:
    terraform = Path("infra/gcp/main.tf").read_text()

    push_endpoint = (
        'push_endpoint = "${google_cloud_run_v2_service.worker.uri}/internal/pubsub/crm-events"'
    )
    assert push_endpoint in terraform
    assert "service_account_email = google_service_account.pubsub_push.email" in terraform
    assert 'role     = "roles/run.invoker"' in terraform
    assert 'role               = "roles/iam.serviceAccountTokenCreator"' in terraform
    assert 'command = ["python", "-m", "app.jobs.crm_worker"]' not in terraform
    assert 'resource "google_pubsub_subscription_iam_member" "worker_subscribe"' not in terraform


def test_api_gateway_does_not_expose_internal_push_endpoint() -> None:
    openapi = Path("infra/gcp/openapi.yaml.tftpl").read_text()

    assert "/internal/pubsub/crm-events" not in openapi
    assert set(line.strip() for line in openapi.splitlines() if line.startswith("  /")) == {
        "/health:",
        "/v1/crm/workspaces/{workspace_id}/connections/{connection_id}/events:",
    }
