"""Authentication for the operator-only read-only API."""

import re
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.settings import settings

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")


def _is_valid_token(value: str) -> bool:
    """Accept only bounded URL-safe opaque bearer tokens without normalization."""
    return _TOKEN_PATTERN.fullmatch(value) is not None


def authentication_failed() -> HTTPException:
    """Create the single generic response for invalid bearer authentication."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="authentication failed",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _parse_bearer_credential(value: bytes) -> str | None:
    """Parse one raw Authorization field without normalizing its credential."""
    try:
        scheme, credential = value.split(b" ")
        decoded_credential = credential.decode("ascii")
    except (UnicodeDecodeError, ValueError):
        return None
    if scheme.lower() != b"bearer" or not decoded_credential:
        return None
    return decoded_credential


def require_api_token(
    request: Request,
    _credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    """Require the configured bearer token without exposing authentication details."""
    expected_token = settings.denticode_api_token
    if expected_token is None:
        raise HTTPException(status_code=503, detail="service temporarily unavailable")
    expected_value = expected_token.get_secret_value()
    if not _is_valid_token(expected_value):
        raise HTTPException(status_code=503, detail="service temporarily unavailable")
    authorization_headers: list[bytes] = [
        value for name, value in request.scope["headers"] if name.lower() == b"authorization"
    ]
    if len(authorization_headers) != 1:
        raise authentication_failed()
    presented_value = _parse_bearer_credential(authorization_headers[0])
    if presented_value is None or not _is_valid_token(presented_value):
        raise authentication_failed()
    if not compare_digest(
        presented_value.encode("ascii"), expected_value.encode("ascii")
    ):
        raise authentication_failed()
