"""Bounded process-local dashboard sessions; bearer tokens stay server-side."""

from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from ipaddress import IPv6Address, ip_address
from secrets import token_urlsafe
from threading import Lock
from typing import Any

from fastapi import HTTPException, Request, status
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token

from app.api.auth import require_api_token
from app.settings import settings as app_settings

COOKIE_NAME = "ad_analyzer_dashboard_session"
CSRF_NAME = "ad_analyzer_dashboard_csrf"
SESSION_TTL = timedelta(hours=8)
MAX_SESSIONS = 1024
_sessions: OrderedDict[str, tuple[datetime, str]] = OrderedDict()
_lock = Lock()
IAP_ISSUER = "https://cloud.google.com/iap"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"


def _purge(now: datetime) -> None:
    for session_id, (expires, _csrf) in list(_sessions.items()):
        if expires <= now:
            del _sessions[session_id]


def _is_loopback(request: Request) -> bool:
    """Trust only the ASGI connection peer, never client-controlled host headers."""
    client = request.scope.get("client")
    if (
        not isinstance(client, (tuple, list))
        or len(client) != 2
        or not isinstance(client[0], str)
        or not client[0]
        or not isinstance(client[1], int)
        or isinstance(client[1], bool)
        or not 0 <= client[1] <= 65535
    ):
        return False
    try:
        peer = ip_address(client[0])
    except ValueError:
        return False
    if isinstance(peer, IPv6Address) and peer.ipv4_mapped is not None:
        return peer.ipv4_mapped.is_loopback
    return peer.is_loopback


def insecure_local_http(request: Request) -> bool:
    return request.url.scheme == "http" and app_settings.dashboard_allow_insecure_local_http


def cookie_secure(request: Request) -> bool:
    if request.url.scheme != "http":
        return True
    if not app_settings.dashboard_allow_insecure_local_http:
        raise HTTPException(status_code=403, detail="dashboard unavailable")
    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="dashboard unavailable")
    return False


def _authentication_failed() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication failed")


def verify_iap_jwt(assertion: str, audience: str) -> dict[str, Any]:
    """Verify an IAP assertion with Google's verifier and IAP public signing keys."""
    try:
        claims = google_id_token.verify_token(
            assertion,
            GoogleAuthRequest(),
            audience=audience,
            certs_url=IAP_CERTS_URL,
        )
    except (GoogleAuthError, ValueError):
        raise _authentication_failed() from None
    if claims.get("iss") != IAP_ISSUER:
        raise _authentication_failed()
    return dict(claims)


def _require_iap_identity(request: Request) -> str:
    audience = app_settings.iap_audience.strip()
    if not audience:
        raise HTTPException(status_code=503, detail="service temporarily unavailable")
    assertions = [
        value
        for name, value in request.scope["headers"]
        if name.lower() == b"x-goog-iap-jwt-assertion"
    ]
    if len(assertions) != 1:
        raise _authentication_failed()
    try:
        assertion = assertions[0].decode("ascii")
    except UnicodeDecodeError:
        raise _authentication_failed() from None
    claims = verify_iap_jwt(assertion, audience)
    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        raise _authentication_failed()
    return email.casefold()


def require_dashboard_session(request: Request) -> None:
    """Use an active opaque session, or authenticate and mark a session for middleware issuance."""
    secure = cookie_secure(request)
    production = app_settings.app_env.casefold() == "production"
    if production:
        # IAP is checked on every request so a session cookie cannot bypass the edge identity.
        request.state.dashboard_identity = _require_iap_identity(request)
    now = datetime.now(UTC)
    presented = request.cookies.get(COOKIE_NAME)
    with _lock:
        _purge(now)
        if presented is not None and presented in _sessions:
            request.state.dashboard_csrf = _sessions[presented][1]
            return
    if not production:
        require_api_token(request, None)
    session_id, csrf = token_urlsafe(32), token_urlsafe(24)
    with _lock:
        _purge(now)
        while len(_sessions) >= MAX_SESSIONS:
            _sessions.popitem(last=False)
        _sessions[session_id] = (now + SESSION_TTL, csrf)
    request.state.dashboard_new_session = session_id
    request.state.dashboard_csrf = csrf
    request.state.dashboard_cookie_secure = secure


def revoke_session(session_id: str | None) -> None:
    with _lock:
        _purge(datetime.now(UTC))
        if session_id is not None:
            _sessions.pop(session_id, None)


def validate_csrf(request: Request) -> None:
    session_id = request.cookies.get(COOKIE_NAME)
    supplied = request.headers.get("X-CSRF-Token")
    if supplied is None:
        form = request.scope.get("_form")
        supplied = form.get("csrf_token") if isinstance(form, dict) else None
    with _lock:
        _purge(datetime.now(UTC))
        session = _sessions.get(session_id or "")
    if session is None or supplied is None or supplied != session[1]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="request rejected")
