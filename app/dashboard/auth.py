"""Bounded process-local dashboard sessions; bearer tokens stay server-side."""

from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from threading import Lock

from fastapi import HTTPException, Request, status

from app.api.auth import require_api_token
from app.settings import settings

COOKIE_NAME = "denticode_dashboard_session"
CSRF_NAME = "denticode_dashboard_csrf"
SESSION_TTL = timedelta(hours=8)
MAX_SESSIONS = 1024
_sessions: OrderedDict[str, tuple[datetime, str]] = OrderedDict()
_lock = Lock()


def _purge(now: datetime) -> None:
    for session_id, (expires, _csrf) in list(_sessions.items()):
        if expires <= now:
            del _sessions[session_id]


def _is_loopback(request: Request) -> bool:
    return request.url.hostname in {"127.0.0.1", "::1", "localhost"}


def insecure_local_http(request: Request) -> bool:
    return request.url.scheme == "http" and settings.denticode_dashboard_allow_insecure_local_http


def cookie_secure(request: Request) -> bool:
    if request.url.scheme != "http":
        return True
    if not settings.denticode_dashboard_allow_insecure_local_http:
        raise HTTPException(status_code=403, detail="dashboard unavailable")
    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="dashboard unavailable")
    return False


def require_dashboard_session(request: Request) -> None:
    """Use an active opaque session, or authenticate and mark a session for middleware issuance."""
    now = datetime.now(UTC)
    presented = request.cookies.get(COOKIE_NAME)
    with _lock:
        _purge(now)
        if presented is not None and presented in _sessions:
            request.state.dashboard_csrf = _sessions[presented][1]
            return
    require_api_token(request, None)
    secure = cookie_secure(request)
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
