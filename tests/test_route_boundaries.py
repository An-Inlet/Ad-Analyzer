"""Authentication coverage against the assembled application, including hidden routes."""

import re
from collections.abc import Callable, Generator
from typing import Any

import pytest
from app.api.auth import require_api_token
from app.crm.push_auth import require_crm_push_identity
from app.customers.access import CSRF_COOKIE, require_customer, require_origin
from app.customers.identity import get_identity_provider
from app.dashboard import auth as dashboard_auth
from app.database.session import get_db
from app.main import app
from app.settings import settings
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine

# Public routes carry no customer data. Callback GETs serve inert bridge documents;
# callback POSTs remain authenticated. Webhooks below have separate signature checks.
PUBLIC = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/app"),
    ("GET", "/app/"),
    ("GET", "/app/settings"),
    ("GET", "/app/campaign-review"),
    ("GET", "/app/workspace-export"),
    ("GET", "/app/activity"),
    ("GET", "/app/workspace-closure"),
    ("GET", "/app/workspace-closure/{workspace_id}/{request_id}"),
    ("GET", "/api/customer/v1/auth-config"),
    ("GET", "/api/customer/v1/google/callback"),
    ("GET", "/api/customer/v1/meta/callback"),
    ("GET", "/api/customer/v1/shopify/callback"),
    ("GET", "/api/customer/v1/sources/{provider}/callback"),
}
SIGNED_INGRESS = {
    ("POST", "/api/billing/stripe/events"),
    ("POST", "/v1/crm/workspaces/{workspace_id}/connections/{connection_id}/events"),
}
STATIC_AND_DOCS = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/app/assets",
    "/dashboard/assets",
}


def routes() -> list[Any]:
    """Include FastAPI's pinned lazy include contexts, not merely OpenAPI paths."""
    result = []
    for entry in app.routes:
        if isinstance(entry, APIRoute):
            result.append(entry)
        elif hasattr(entry, "effective_route_contexts"):
            result.extend(entry.effective_route_contexts())
        else:
            path = getattr(entry, "path", None)
            assert path in STATIC_AND_DOCS, f"Unclassified non-API route: {path}"
    return result


def dependencies(dependant: Any) -> set[Any]:
    result = {dependant.call}
    for child in dependant.dependencies:
        result.update(dependencies(child))
    return result


def operator_routes() -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    expected: Callable[..., None]
    for route in routes():
        if route.path.startswith("/api/v1/"):
            authority, expected = "operator", require_api_token
        elif route.path == "/dashboard" or route.path.startswith("/dashboard/"):
            authority, expected = "dashboard", dashboard_auth.require_dashboard_session
        elif route.path.startswith("/internal/"):
            authority, expected = "worker", require_crm_push_identity
        else:
            continue
        assert expected in dependencies(route.dependant), route.path
        result.extend((method, route.path, authority) for method in sorted(route.methods))
    return sorted(result)


def test_every_assembled_route_has_an_explicit_boundary() -> None:
    guarded = {(method, path) for method, path, _ in operator_routes()}
    observed = set()
    for route in routes():
        checks = dependencies(route.dependant)
        for method in route.methods:
            key = method, route.path
            observed.add(key)
            if key in guarded | PUBLIC | SIGNED_INGRESS:
                continue
            if key == ("POST", "/v1/crm/events"):
                continue  # Permanently rejects unscoped events; tested below.
            if key == ("POST", "/api/customer/v1/session"):
                assert require_origin in checks
            else:
                assert route.path.startswith("/api/customer/v1/") and require_customer in checks, (
                    key
                )
    assert observed >= PUBLIC | SIGNED_INGRESS
    assert {kind for _, _, kind in operator_routes()} == {"operator", "dashboard", "worker"}


@pytest.mark.parametrize(
    "mode", ["production", "missing_configuration", "development_local", "development_missing"]
)
def test_customer_session_cannot_cross_any_operator_or_worker_boundary(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    missing = mode in {"missing_configuration", "development_missing"}
    local = mode.startswith("development")
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(settings, "app_env", "development" if local else "production")
    monkeypatch.setattr(settings, "dashboard_allow_insecure_local_http", True)
    monkeypatch.setattr(settings, "api_token", None if missing else SecretStr("o" * 43))
    monkeypatch.setattr(
        settings,
        "iap_audience",
        "" if missing else "/projects/123/global/backendServices/456",
    )
    monkeypatch.setattr(
        settings,
        "crm_push_oidc_audience",
        "" if missing else "https://worker.example.invalid",
    )
    monkeypatch.setattr(
        settings,
        "crm_push_service_account_email",
        "" if missing else "push@fixture.iam.gserviceaccount.com",
    )

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    def forbidden_database() -> None:
        raise AssertionError("Customer identity crossed the operator/worker boundary")

    def forbidden_verifier(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Unsigned customer request must not invoke the IAP verifier")

    monkeypatch.setattr(dashboard_auth, "verify_iap_jwt", forbidden_verifier)
    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {get_db: database, get_identity_provider: lambda: FakeProvider()},
    )
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 12345)) as client:
        login(client, "boundary-customer:1")
        assert client.get("/api/customer/v1/session").status_code == 200
        csrf = client.cookies[CSRF_COOKIE]
        # A legitimate customer session, CSRF and Origin confer no operator authority.
        app.dependency_overrides[get_db] = forbidden_database
        for method, template, authority in operator_routes():
            path = re.sub(r"\{[^}]+\}", "1", template)
            # Explicitly present the real session even on the permitted local HTTP
            # development transport; Secure cookie omission must not explain denial.
            headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
            if local:
                headers["Cookie"] = "; ".join(
                    f"{key}={value}" for key, value in client.cookies.items()
                )
                path = ORIGIN.replace("https://", "http://") + path
            response = client.request(
                method,
                path,
                headers=headers,
                json={} if method != "GET" else None,
            )
            expected = 503 if missing else 401
            assert response.status_code == expected, (
                method,
                template,
                authority,
                response.status_code,
            )
        assert client.post("/v1/crm/events").status_code == 422
        app.dependency_overrides[get_db] = database
        assert client.get("/api/customer/v1/session").status_code == 200
