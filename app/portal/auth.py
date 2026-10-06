"""Public, non-secret browser configuration; no provider discovery or network calls."""

import os
import re
from urllib.parse import urlsplit

from fastapi import APIRouter
from pydantic import BaseModel

from app.settings import settings

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])


class BrowserIdentityConfig(BaseModel):
    enabled: bool = False
    providers: list[str] = []
    live_verified: bool = False
    firebase: dict[str, str] | None = None


def browser_identity_config() -> BrowserIdentityConfig:
    project = settings.customer_identity_project_id
    try:
        origin = urlsplit(settings.customer_app_origin)
    except ValueError:
        return BrowserIdentityConfig()
    if (
        not settings.customer_auth_enabled
        or not settings.customer_browser_auth_enabled
        or os.environ.get("FIREBASE_AUTH_EMULATOR_HOST")
        or not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project)
        or not re.fullmatch(r"[A-Za-z0-9_-]{20,100}", settings.customer_identity_web_api_key)
        or not re.fullmatch(r"1:[0-9]+:web:[a-f0-9]+", settings.customer_identity_web_app_id)
        or origin.scheme != "https"
        or not origin.hostname
        or origin.username is not None
        or origin.password is not None
        or origin.path not in ("", "/")
        or origin.query
        or origin.fragment
    ):
        return BrowserIdentityConfig()
    return BrowserIdentityConfig(
        enabled=True,
        providers=["google.com"],
        firebase={
            "projectId": project,
            "authDomain": f"{project}.firebaseapp.com",
            "apiKey": settings.customer_identity_web_api_key,
            "appId": settings.customer_identity_web_app_id,
        },
    )


@router.get("/auth-config", response_model=BrowserIdentityConfig)
def auth_config() -> BrowserIdentityConfig:
    return browser_identity_config()


def customer_content_security_policy() -> str:
    config = browser_identity_config()
    script = "script-src 'self'"
    connect = "connect-src 'self'"
    frame = "frame-src 'none'"
    if config.enabled and config.firebase:
        # Firebase popup resolver bootstraps gapi and one project-bound auth iframe.
        # No caller-supplied origins, wildcard Google domains, inline code or eval.
        script += " https://apis.google.com"
        connect += " https://identitytoolkit.googleapis.com https://securetoken.googleapis.com"
        frame = f"frame-src https://{config.firebase['authDomain']}"
    return (
        f"default-src 'self'; {script}; style-src 'self'; {connect}; {frame}; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
