"""Google Cloud Identity Platform adapter; no provider calls until explicitly enabled."""

import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol, cast

import firebase_admin  # type: ignore[import-untyped]
from fastapi import HTTPException
from firebase_admin import auth

from app.settings import settings


def denied() -> HTTPException:
    return HTTPException(status_code=401, detail="authentication failed")


def unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="customer authentication unavailable")


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    email: str
    authenticated_at: int
    expires_at: int


class IdentityProvider(Protocol):
    @property
    def issuer(self) -> str: ...

    def verify(self, token: str) -> VerifiedIdentity: ...

    def check_active(self, subject: str, authenticated_at: int) -> None: ...


def verified_identity(claims: dict[str, Any], project: str, now: int) -> VerifiedIdentity:
    issuer = f"https://securetoken.google.com/{project}"
    subject, email = claims.get("sub"), claims.get("email")
    auth_time, issued, expires = (claims.get(k) for k in ("auth_time", "iat", "exp"))
    firebase = claims.get("firebase", {})
    if (
        claims.get("iss") != issuer
        or claims.get("aud") != project
        or not isinstance(subject, str)
        or not 1 <= len(subject) <= 128
        or not isinstance(email, str)
        or not 1 <= len(email) <= 320
        or claims.get("email_verified") is not True
        or not isinstance(firebase, dict)
        or firebase.get("tenant") is not None
        or any(type(value) is not int for value in (auth_time, issued, expires))
    ):
        raise denied()
    auth_time, issued, expires = (cast(int, value) for value in (auth_time, issued, expires))
    if not (0 <= auth_time <= issued <= now < expires and now - auth_time <= 300):
        raise denied()
    return VerifiedIdentity(issuer, subject, email, auth_time, expires)


@lru_cache(maxsize=1)
def _admin_app(project: str) -> Any:
    # Application default credentials/workload identity only; no keys in Inlet configuration.
    return firebase_admin.initialize_app(
        options={"projectId": project, "httpTimeout": 5}, name=f"inlet-{project}"
    )


class GoogleIdentityProvider:
    def __init__(self, project: str) -> None:
        self.project = project

    @property
    def issuer(self) -> str:
        return f"https://securetoken.google.com/{self.project}"

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            claims = auth.verify_id_token(token, app=_admin_app(self.project), check_revoked=True)
        except auth.CertificateFetchError:
            raise unavailable() from None
        except (
            auth.InvalidIdTokenError,
            auth.RevokedIdTokenError,
            auth.UserDisabledError,
            auth.UserNotFoundError,
            ValueError,
        ):
            raise denied() from None
        except Exception:
            # Provider/network/ADC failures must not expose responses or silently allow login.
            raise unavailable() from None
        return verified_identity(claims, self.project, int(time.time()))

    def check_active(self, subject: str, authenticated_at: int) -> None:
        try:
            user = auth.get_user(subject, app=_admin_app(self.project))
        except auth.UserNotFoundError:
            raise denied() from None
        except Exception:
            raise unavailable() from None
        if user.disabled or not user.email_verified:
            raise denied()
        if authenticated_at * 1000 < user.tokens_valid_after_timestamp:
            raise denied()


def get_identity_provider() -> IdentityProvider:
    if (
        not settings.customer_auth_enabled
        or not settings.customer_identity_project_id
        or os.environ.get("FIREBASE_AUTH_EMULATOR_HOST")
    ):
        raise unavailable()
    return GoogleIdentityProvider(settings.customer_identity_project_id)
