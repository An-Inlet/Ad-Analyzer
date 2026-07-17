"""Opaque, short-lived dashboard sessions; API tokens never leave request headers."""

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from fastapi import HTTPException, Request, Response, status

from app.api.auth import require_api_token

_COOKIE = "denticode_dashboard_session"
_TTL = timedelta(hours=8)
_sessions: dict[str, datetime] = {}


def _valid_session(value: str | None) -> bool:
    if value is None:
        return False
    expires = _sessions.get(value)
    if expires is None or expires <= datetime.now(UTC):
        _sessions.pop(value, None)
        return False
    return True


def require_dashboard_session(request: Request, response: Response) -> None:
    """Authenticate a browser request from an existing opaque session or Bearer header."""
    if _valid_session(request.cookies.get(_COOKIE)):
        return
    # This reuses the exact API boundary and deliberately never serializes its credential.
    require_api_token(request, None)
    session_id = token_urlsafe(32)
    _sessions[session_id] = datetime.now(UTC) + _TTL
    response.set_cookie(
        _COOKIE,
        session_id,
        max_age=int(_TTL.total_seconds()),
        httponly=True,
        samesite="strict",
        secure=False,  # Local HTTP development support; it contains only an opaque session id.
        path="/dashboard",
    )


def dashboard_access_denied() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication failed")
