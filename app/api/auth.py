"""Authentication for the operator-only read-only API."""

from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.settings import settings

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def authentication_failed() -> HTTPException:
    """Create the single generic response for invalid bearer authentication."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="authentication failed",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_api_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    """Require the configured bearer token without exposing authentication details."""
    expected_token = settings.denticode_api_token
    if expected_token is None:
        raise HTTPException(status_code=503, detail="service temporarily unavailable")
    expected_value = expected_token.get_secret_value()
    if not expected_value or not expected_value.isascii():
        raise HTTPException(status_code=503, detail="service temporarily unavailable")
    if credentials is None or not credentials.credentials.isascii():
        raise authentication_failed()
    if not compare_digest(
        credentials.credentials.encode("ascii"), expected_value.encode("ascii")
    ):
        raise authentication_failed()
