"""Real Google token verification with ephemeral synthetic certs; no provider network."""

import json
import time
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
import pytest
from app.api import pubsub
from app.crm import push_auth
from app.customers.identity import get_identity_provider
from app.database.session import get_db
from app.main import app
from app.settings import settings
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from google.auth import crypt, jwt
from httpx import Client as HTTPClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_crm_pubsub_push import FakeProcessor, FakeSession, envelope, event
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine

AUDIENCE = "https://inlet-worker-fixture.run.app"
EMAIL = "inlet-push@fixture-project.iam.gserviceaccount.com"
PATH = "/internal/pubsub/crm-events"


@pytest.fixture(scope="module")
def signing_material() -> tuple[crypt.RSASigner, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic Offline Certificate")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    signer = cast(Callable[..., crypt.RSASigner], crypt.RSASigner.from_string)(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        key_id="offline-key",
    )
    return signer, json.dumps(
        {"offline-key": cert.public_bytes(serialization.Encoding.PEM).decode()}
    ).encode()


def token(signer: crypt.RSASigner, **changes: Any) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": AUDIENCE,
        "email": EMAIL,
        "email_verified": True,
        "sub": "12345678901234567890",
        "iat": now - 10,
        "exp": now + 300,
        **changes,
    }
    return cast(Callable[..., bytes], jwt.encode)(signer, claims).decode()


@pytest.fixture
def authenticated_push(
    monkeypatch: pytest.MonkeyPatch, signing_material: tuple[crypt.RSASigner, bytes]
) -> Generator[tuple[TestClient, crypt.RSASigner, list[str]], None, None]:
    signer, cert = signing_material
    monkeypatch.setattr(settings, "crm_push_oidc_audience", AUDIENCE)
    monkeypatch.setattr(settings, "crm_push_service_account_email", EMAIL)
    FakeProcessor.error, FakeProcessor.payloads = None, []
    monkeypatch.setattr(pubsub, "CrmEventProcessor", FakeProcessor)
    monkeypatch.setattr(app, "dependency_overrides", {get_db: lambda: FakeSession()})
    calls: list[str] = []
    real_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert str(request.url) == push_auth.CERTIFICATES and request.method == "GET"
        assert "authorization" not in request.headers
        return httpx.Response(200, content=cert)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(respond)),
    )
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, signer, calls


def test_real_signature_verified_identity_processes_and_preserves_redelivery(
    authenticated_push: tuple[TestClient, crypt.RSASigner, list[str]],
) -> None:
    client, signer, calls = authenticated_push
    headers = {"Authorization": "Bearer " + token(signer)}
    assert client.post(PATH, headers=headers, json=envelope(event())).status_code == 204
    assert client.post(PATH, headers=headers, json=envelope(event())).status_code == 204
    assert FakeProcessor.payloads == [event(), event()]
    assert calls == [push_auth.CERTIFICATES] * 2


@pytest.mark.parametrize(
    "changes",
    [
        {"aud": "https://foreign-worker.run.app"},
        {"aud": [AUDIENCE]},
        {"iss": "https://attacker.invalid"},
        {"email": "other@fixture-project.iam.gserviceaccount.com"},
        {"email_verified": False},
        {"email_verified": "true"},
        {"email_verified": 1},
        {"exp": 1},
        {"iat": 4102444800, "exp": 4102444900},
        {"iat": True},
        {"sub": ""},
        {"exp": "4102444900"},
    ],
)
def test_signed_invalid_claims_never_reach_processor(
    authenticated_push: tuple[TestClient, crypt.RSASigner, list[str]],
    changes: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, signer, _ = authenticated_push
    bearer = token(signer, **changes)
    response = client.post(
        PATH, headers={"Authorization": "Bearer " + bearer}, json=envelope(event())
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "push authentication required"}
    assert not FakeProcessor.payloads and bearer not in caplog.text


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("Authorization", "Bearer a.b.c"), ("Authorization", "Bearer a.b.c")],
        [("Authorization", "Basic a.b.c")],
        [("Authorization", "Bearer a.b.c, Bearer x.y.z")],
        [("Authorization", "Bearer " + "a" * 8192)],
        [("Authorization", "Bearer  a.b.c")],
        [("X-Goog-IAP-JWT-Assertion", "a.b.c")],
        [("X-Serverless-Authorization", "Bearer a.b.c")],
    ],
)
def test_missing_malformed_duplicate_and_proxy_headers_reject_without_certificate_io(
    authenticated_push: tuple[TestClient, crypt.RSASigner, list[str]],
    headers: list[tuple[str, str]],
) -> None:
    client, _, calls = authenticated_push
    assert client.post(PATH, headers=headers, json=envelope(event())).status_code == 401
    assert not calls and not FakeProcessor.payloads


def test_tampered_signature_and_unknown_key_fail_closed(
    authenticated_push: tuple[TestClient, crypt.RSASigner, list[str]],
) -> None:
    client, signer, _ = authenticated_push
    valid = token(signer)
    parts = valid.split(".")
    parts[-1] = ("A" if parts[-1][0] != "A" else "B") + parts[-1][1:]
    assert (
        client.post(
            PATH, headers={"Authorization": "Bearer " + ".".join(parts)}, json=envelope(event())
        ).status_code
        == 401
    )
    unknown = cast(Callable[..., bytes], jwt.encode)(
        signer, {"iss": "https://accounts.google.com", "aud": AUDIENCE}, key_id="unknown"
    ).decode()
    assert (
        client.post(
            PATH, headers={"Authorization": "Bearer " + unknown}, json=envelope(event())
        ).status_code
        == 401
    )
    assert not FakeProcessor.payloads


@pytest.mark.parametrize(
    "audience,email",
    [
        ("", EMAIL),
        (AUDIENCE, ""),
        ("http://worker.invalid", EMAIL),
        ("https://[invalid", EMAIL),
        ("https://worker.invalid\n", EMAIL),
        (AUDIENCE, "customer@example.invalid"),
        ("https://worker.invalid?other=1", EMAIL),
    ],
)
def test_unconfigured_worker_never_verifies_or_processes(
    authenticated_push: tuple[TestClient, crypt.RSASigner, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    audience: str,
    email: str,
) -> None:
    client, signer, calls = authenticated_push
    monkeypatch.setattr(settings, "crm_push_oidc_audience", audience)
    monkeypatch.setattr(settings, "crm_push_service_account_email", email)
    assert (
        client.post(
            PATH, headers={"Authorization": "Bearer " + token(signer)}, json=envelope(event())
        ).status_code
        == 503
    )
    assert not calls and not FakeProcessor.payloads


def test_actual_customer_login_and_operator_token_do_not_authorize_worker(
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(settings, "crm_push_oidc_audience", AUDIENCE)
    monkeypatch.setattr(settings, "crm_push_service_account_email", EMAIL)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {get_db: database, get_identity_provider: lambda: FakeProvider()},
    )

    def forbidden(_: object) -> None:
        pytest.fail("unauthorized request constructed processor")

    monkeypatch.setattr(pubsub, "CrmEventProcessor", forbidden)
    with TestClient(app, base_url=ORIGIN) as client:
        login(client, "customer:worker-denial")
        assert client.get("/api/customer/v1/session").status_code == 200
        for headers in [
            {},
            {"Authorization": "Bearer operator-token"},
            {"X-Goog-IAP-JWT-Assertion": "operator-assertion"},
        ]:
            assert client.post(PATH, headers=headers, json=envelope(event())).status_code == 401


@pytest.mark.parametrize("failure", ["redirect", "oversize", "invalid", "network", "stream"])
def test_certificate_failures_are_bounded_closed_and_sanitized(
    authenticated_push: tuple[TestClient, crypt.RSASigner, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, signer, _ = authenticated_push
    clients: list[HTTPClient] = []
    calls: list[str] = []

    class Interrupted(httpx.SyncByteStream):
        closed = False

        def __iter__(self) -> Generator[bytes, None, None]:
            yield b'{"offline-key":'
            raise httpx.ReadError("private synthetic certificate detail")

        def close(self) -> None:
            self.closed = True

    body = Interrupted()

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if failure == "network":
            raise httpx.ConnectError("private synthetic network detail")
        if failure == "stream":
            return httpx.Response(200, stream=body)
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://attacker.invalid"})
        return httpx.Response(200, content=b"x" * 262145 if failure == "oversize" else b"invalid")

    def factory(**kwargs: Any) -> HTTPClient:
        result = HTTPClient(**kwargs, transport=httpx.MockTransport(respond))
        clients.append(result)
        return result

    monkeypatch.setattr(httpx, "Client", factory)
    response = client.post(
        PATH, headers={"Authorization": "Bearer " + token(signer)}, json=envelope(event())
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "push authentication required"}
    assert not FakeProcessor.payloads and "private synthetic" not in caplog.text
    assert calls == [push_auth.CERTIFICATES]
    assert all(c.is_closed for c in clients)
    if failure == "stream":
        assert body.closed


def test_certificate_transport_rejects_arbitrary_urls_and_methods() -> None:
    for url, method in [("https://attacker.invalid", "GET"), (push_auth.CERTIFICATES, "POST")]:
        with pytest.raises(ValueError, match="unavailable"):
            push_auth.certificate_request(url, method)


def test_worker_configuration_defaults_and_no_resource_self_reference() -> None:
    from pathlib import Path

    from app.settings import Settings

    defaults = Settings(_env_file=None)
    assert defaults.crm_push_oidc_audience == "" and defaults.crm_push_service_account_email == ""
    terraform = Path("infra/gcp/main.tf").read_text()
    worker = terraform.split('resource "google_cloud_run_v2_service" "worker"', 1)[1].split(
        "\nresource ", 1
    )[0]
    assert 'name  = "AD_ANALYZER_CRM_PUSH_OIDC_AUDIENCE"' in worker
    assert "value = var.worker_push_oidc_audience" in worker
    assert "value = google_service_account.pubsub_push.email" in worker
    assert "google_cloud_run_v2_service.worker.uri" not in worker
    assert "audience              = google_cloud_run_v2_service.worker.uri" in terraform
