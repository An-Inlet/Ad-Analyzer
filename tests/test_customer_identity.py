"""Customer trust-boundary acceptance on independent app replicas and shared SQL."""

import os
import time
from collections.abc import Generator
from typing import Any
from uuid import uuid4

import pytest
from app.api.customer import router
from app.api.v1 import router as operator_router
from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, digest
from app.customers.identity import (
    GoogleIdentityProvider,
    VerifiedIdentity,
    denied,
    get_identity_provider,
    verified_identity,
)
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.main import app as platform_app  # noqa: F401
from app.settings import settings
from app.workspaces.models import Workspace, WorkspaceMembership
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ORIGIN = "https://inlet.example"
PROJECT = "inlet-test-project"
ISSUER = f"https://securetoken.google.com/{PROJECT}"


class FakeProvider:
    issuer = ISSUER

    def __init__(self) -> None:
        self.disabled: set[str] = set()
        self.revoked: set[str] = set()
        self.fail = False
        self.email = "same@example.test"

    def verify(self, token: str) -> VerifiedIdentity:
        subject = token.split(":", 1)[0]
        self.check_active(subject, int(time.time()))
        return VerifiedIdentity(
            self.issuer, subject, self.email, int(time.time()), int(time.time()) + 3600
        )

    def check_active(self, subject: str, authenticated_at: int) -> None:
        if self.fail:
            raise HTTPException(503, "customer authentication unavailable")
        if subject in self.disabled | self.revoked:
            raise denied()


@pytest.fixture(params=["sqlite", "postgres"])
def customer_engine(request: pytest.FixtureRequest) -> Generator[Engine, None, None]:
    if request.param == "sqlite":
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()
        return
    url = os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
    if not url or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true":
        pytest.skip("explicit disposable PostgreSQL configuration required")
    schema = "inlet_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture()
def replicas(
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, TestClient, FakeProvider]:
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    provider = FakeProvider()
    factory = sessionmaker(customer_engine)

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    def make_replica() -> TestClient:
        app = FastAPI()
        app.include_router(router)
        app.include_router(operator_router)
        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_identity_provider] = lambda: provider
        return TestClient(app, base_url=ORIGIN)

    return make_replica(), make_replica(), provider


def login(client: TestClient, identity: str) -> str:
    response = client.post(
        "/api/customer/v1/session",
        json={"id_token": identity},
        headers={"Origin": ORIGIN, "X-Inlet-Request": "1"},
    )
    assert response.status_code == 200, response.status_code
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    assert all(
        "Secure" in v and "SameSite=strict" in v and "Domain=" not in v
        for v in response.headers.get_list("set-cookie")
    )
    user_id = response.json()["user_id"]
    assert isinstance(user_id, str)
    return user_id


def test_cross_identity_cross_replica_revocation_and_scoped_membership(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    alice, bob, _ = replicas
    alice_id, bob_id = login(alice, "alice:1"), login(bob, "bob:1")
    assert alice_id != bob_id  # Same verified email is never an identity key.
    with Session(customer_engine) as db:
        a = Workspace(slug="alice", name="Alice", client_name="Alice", status="active")
        b = Workspace(slug="bob", name="Bob", client_name="Bob", status="active")
        db.add_all([a, b])
        db.flush()
        a_id, b_id = a.id, b.id
        db.add_all(
            [
                CustomerMembership(user_id=alice_id, workspace_id=a.id, role="owner"),
                CustomerMembership(user_id=bob_id, workspace_id=b.id, role="owner"),
                WorkspaceMembership(workspace_id=b.id, principal="same@example.test", role="owner"),
            ]
        )
        db.commit()
    assert alice.get(f"/api/customer/v1/workspaces/{b_id}").status_code == 404
    assert bob.get(f"/api/customer/v1/workspaces/{a_id}").status_code == 404
    assert [w["id"] for w in alice.get("/api/customer/v1/workspaces").json()] == [a_id]
    # A second app instance sees the same session; no process-local authorization state.
    bob.cookies.clear()
    bob.cookies.update(alice.cookies)
    assert bob.get("/api/customer/v1/session").json()["user_id"] == alice_id
    assert alice.delete("/api/customer/v1/session").status_code == 403
    response = alice.delete(
        "/api/customer/v1/session",
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": alice.cookies[CSRF_COOKIE],
        },
    )
    assert response.status_code == 204
    assert bob.get("/api/customer/v1/session").status_code == 401


@pytest.mark.parametrize("invalid", ["expired", "revoked", "suspended", "provider", "outage"])
def test_current_state_invalidates_existing_session(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
    invalid: str,
) -> None:
    client, _, provider = replicas
    user_id = login(client, "alice:1")
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, digest(client.cookies[SESSION_COOKIE]))
        user = db.get(CustomerUser, user_id)
        assert session is not None and user is not None
        if invalid == "expired":
            session.expires_at = int(time.time()) - 1
        if invalid == "revoked":
            session.revoked_at = int(time.time())
        if invalid == "suspended":
            user.status = "suspended"
        db.commit()
    if invalid == "provider":
        provider.disabled.add("alice")
    if invalid == "outage":
        provider.fail = True
    assert client.get("/api/customer/v1/session").status_code == (
        503 if invalid == "outage" else 401
    )


def test_replay_rotation_contact_change_and_project_change(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    first, second, provider = replicas
    user_id = login(first, "alice:1")
    second.cookies.update(first.cookies)
    replay = second.post(
        "/api/customer/v1/session",
        json={"id_token": "alice:1"},
        headers={"Origin": ORIGIN, "X-Inlet-Request": "1"},
    )
    assert replay.status_code == 401
    provider.email = "changed@example.test"
    assert login(first, "alice:2") == user_id
    assert second.get("/api/customer/v1/session").status_code == 401
    assert first.get("/api/customer/v1/session").json()["email"] == provider.email
    with Session(customer_engine) as db:
        rows = db.scalars(select(CustomerSession)).all()
        assert all(row.digest != first.cookies[SESSION_COOKIE] for row in rows)
        assert all(row.csrf_digest != first.cookies[CSRF_COOKIE] for row in rows)
    provider.issuer = "https://securetoken.google.com/other-project"
    assert first.get("/api/customer/v1/session").status_code == 401


def test_untrusted_login_and_membership_suspension(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    client, _, _ = replicas
    for headers in [
        {},
        {"Origin": "https://evil.example", "X-Inlet-Request": "1"},
        {"Origin": ORIGIN},
    ]:
        assert (
            client.post(
                "/api/customer/v1/session", json={"id_token": "alice:1"}, headers=headers
            ).status_code
            == 403
        )
    user_id = login(client, "alice:1")
    with Session(customer_engine) as db:
        workspace = Workspace(slug="suspended", name="s", client_name="s", status="active")
        db.add(workspace)
        db.flush()
        membership = CustomerMembership(user_id=user_id, workspace_id=workspace.id, role="viewer")
        db.add(membership)
        db.commit()
        workspace_id = workspace.id
    assert client.get(f"/api/customer/v1/workspaces/{workspace_id}").status_code == 200
    with Session(customer_engine) as db:
        current_membership = db.get(CustomerMembership, (user_id, workspace_id))
        assert current_membership is not None
        current_membership.status = "suspended"
        db.commit()
    assert client.get(f"/api/customer/v1/workspaces/{workspace_id}").status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [
        ("iss", "untrusted"),
        ("aud", "other-project"),
        ("sub", ""),
        ("email_verified", False),
        ("exp", 1000),
        ("auth_time", 1),
        ("auth_time", True),
        ("iat", 2001),
        ("firebase", {"tenant": "other"}),
    ],
)
def test_verified_claims_fail_closed(field: str, value: object) -> None:
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": PROJECT,
        "sub": "alice",
        "email": "alice@example.test",
        "email_verified": True,
        "auth_time": 1990,
        "iat": 1995,
        "exp": 3000,
    }
    assert verified_identity(claims, PROJECT, 2000).subject == "alice"
    claims[field] = value
    with pytest.raises(HTTPException) as error:
        verified_identity(claims, PROJECT, 2000)
    assert error.value.status_code == 401


def test_provider_uses_revocation_check_and_sanitizes_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.customers import identity
    from firebase_admin import auth  # type: ignore[import-untyped]

    def invalid(token: str, *, app: object, check_revoked: bool) -> dict[str, Any]:
        assert check_revoked is True
        raise auth.InvalidIdTokenError("sensitive token or provider response")

    monkeypatch.setattr(identity, "_admin_app", lambda project: object())
    monkeypatch.setattr(auth, "verify_id_token", invalid)
    with pytest.raises(HTTPException) as error:
        GoogleIdentityProvider(PROJECT).verify("synthetic-invalid-token")
    assert error.value.status_code == 401
    assert error.value.detail == "authentication failed"


def test_disabled_configuration_and_emulator_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "customer_auth_enabled", False)
    with pytest.raises(HTTPException):
        get_identity_provider()
    monkeypatch.setattr(settings, "customer_auth_enabled", True)
    monkeypatch.setattr(settings, "customer_identity_project_id", PROJECT)
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    with pytest.raises(HTTPException):
        get_identity_provider()


def test_customer_cookie_cannot_authenticate_operator_api(
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    client, other, _ = replicas
    login(client, "alice:1")
    assert client.get("/api/v1/accounts").status_code in (401, 503)
    assert (
        other.get(
            "/api/customer/v1/session",
            headers={
                "Authorization": "Bearer synthetic-operator-token",
                "X-Goog-Iap-Jwt-Assertion": "synthetic-iap-assertion",
            },
        ).status_code
        == 401
    )


def test_same_token_concurrent_exchange_has_one_winner(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    if customer_engine.dialect.name != "postgresql":
        return  # SQLite StaticPool cannot model concurrent connections/unique-index waits.
    first, second, _ = replicas
    login(first, "alice:seed")

    def exchange(client: TestClient) -> int:
        return client.post(
            "/api/customer/v1/session",
            json={"id_token": "alice:race"},
            headers={"Origin": ORIGIN, "X-Inlet-Request": "1"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(exchange, (first, second)))
    assert sorted(statuses) == [200, 401]


def test_csrf_bound_to_current_identity_and_origin(
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    first, second, _ = replicas
    login(first, "alice:1")
    login(second, "bob:1")
    wrong = second.cookies[CSRF_COOKIE]
    assert (
        first.delete(
            "/api/customer/v1/session",
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": wrong,
            },
        ).status_code
        == 403
    )
    assert (
        first.delete(
            "/api/customer/v1/session",
            headers={
                "Origin": "https://evil.example",
                "X-CSRF-Token": first.cookies[CSRF_COOKIE],
            },
        ).status_code
        == 403
    )
    assert first.get("/api/customer/v1/session").status_code == 200
