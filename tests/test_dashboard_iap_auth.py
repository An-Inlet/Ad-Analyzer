from collections.abc import Iterator
from typing import Any

import pytest
from app.dashboard import auth
from app.settings import settings
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from google.oauth2 import id_token as google_id_token
from pydantic import SecretStr

TOKEN = "a" * 43
AUDIENCE = "/projects/123/global/backendServices/456"
ALLOWED_EMAIL = "operator@example.com"


@pytest.fixture(autouse=True)
def dashboard_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "iap_audience", AUDIENCE)
    monkeypatch.setattr(settings, "platform_admin_emails_csv", ALLOWED_EMAIL)
    monkeypatch.setattr(settings, "dashboard_allow_insecure_local_http", False)
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(TOKEN))
    with auth._lock:
        auth._sessions.clear()
    yield
    with auth._lock:
        auth._sessions.clear()


def auth_app() -> FastAPI:
    test_app = FastAPI()

    @test_app.get("/dashboard", dependencies=[Depends(auth.require_dashboard_session)])
    def dashboard(request: Request) -> dict[str, str]:
        return {"identity": request.state.dashboard_identity}

    return test_app


def iap_header(assertion: str = "signed-assertion") -> dict[str, str]:
    return {"x-goog-iap-jwt-assertion": assertion}


def test_valid_iap_jwt_allows_approved_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth,
        "verify_iap_jwt",
        lambda assertion, audience: {
            "iss": auth.IAP_ISSUER,
            "email": ALLOWED_EMAIL,
            "aud": audience,
        },
    )

    response = TestClient(auth_app(), base_url="https://testserver").get(
        "/dashboard", headers=iap_header()
    )

    assert response.status_code == 200
    assert response.json() == {"identity": ALLOWED_EMAIL}


def test_valid_iap_jwt_authenticates_identity_before_workspace_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth,
        "verify_iap_jwt",
        lambda _assertion, _audience: {
            "iss": auth.IAP_ISSUER,
            "email": "unapproved@example.com",
        },
    )

    response = TestClient(auth_app(), base_url="https://testserver").get(
        "/dashboard", headers=iap_header()
    )

    assert response.status_code == 200
    assert response.json() == {"identity": "unapproved@example.com"}


@pytest.mark.parametrize("failure", ["invalid signature", "wrong audience", "expired JWT"])
def test_google_verifier_rejections_are_generic(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    def reject(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise ValueError(failure)

    monkeypatch.setattr(google_id_token, "verify_token", reject)

    response = TestClient(auth_app(), base_url="https://testserver").get(
        "/dashboard", headers=iap_header(failure)
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication failed"}


def test_verifier_uses_expected_audience_and_rejects_wrong_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def verify(_token: str, _request: object, **kwargs: object) -> dict[str, str]:
        observed.update(kwargs)
        return {"iss": "https://accounts.google.com", "email": ALLOWED_EMAIL}

    monkeypatch.setattr(google_id_token, "verify_token", verify)

    with pytest.raises(HTTPException) as raised:
        auth.verify_iap_jwt("assertion", AUDIENCE)

    assert raised.value.status_code == 401
    assert observed == {"audience": AUDIENCE, "certs_url": auth.IAP_CERTS_URL}


def test_missing_iap_header_is_rejected_in_production() -> None:
    response = TestClient(auth_app(), base_url="https://testserver").get("/dashboard")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication failed"}


def test_local_dashboard_retains_bearer_token_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    local_app = FastAPI()

    @local_app.get("/dashboard", dependencies=[Depends(auth.require_dashboard_session)])
    def dashboard() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(local_app, base_url="https://testserver")
    assert client.get("/dashboard").status_code == 401
    response = client.get("/dashboard", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_api_v1_still_requires_bearer_token_when_iap_header_is_present() -> None:
    from app.main import app

    response = TestClient(app).get("/api/v1/accounts", headers=iap_header())

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication failed"}
