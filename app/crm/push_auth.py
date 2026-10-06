"""Application identity boundary for Pub/Sub push, independent of customer/admin auth."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request
from google.oauth2 import id_token

from app.settings import settings

CERTIFICATES = "https://www.googleapis.com/oauth2/v1/certs"


@dataclass(frozen=True)
class CertificateResponse:
    status: int
    data: bytes
    headers: dict[str, str]


def certificate_request(url: str, method: str = "GET") -> CertificateResponse:
    """Google verifier transport with one fixed public endpoint and bounded resources."""
    if url != CERTIFICATES or method != "GET":
        raise ValueError("certificate request unavailable")
    with (
        httpx.Client(timeout=httpx.Timeout(5), follow_redirects=False, trust_env=False) as client,
        client.stream("GET", CERTIFICATES) as response,
    ):
        if response.status_code != 200:
            raise ValueError("certificate response unavailable")
        raw = bytearray()
        for chunk in response.iter_bytes(chunk_size=16384):
            raw.extend(chunk)
            if len(raw) > 262144:
                raise ValueError("certificate response unavailable")
        return CertificateResponse(response.status_code, bytes(raw), dict(response.headers))


def require_crm_push_identity(request: Request) -> None:
    audience = settings.crm_push_oidc_audience
    email = settings.crm_push_service_account_email
    try:
        parsed = urlsplit(audience)
    except ValueError:
        raise HTTPException(503, "push authentication unavailable") from None
    if (
        not audience
        or len(audience) > 2048
        or any(ord(c) < 33 or ord(c) > 126 for c in audience)
        or len(email) > 254
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not re.fullmatch(
            r"[a-z0-9][a-z0-9._-]{0,127}@[a-z0-9][a-z0-9.-]{0,127}\.gserviceaccount\.com",
            email,
        )
    ):
        raise HTTPException(503, "push authentication unavailable")
    headers = request.headers.getlist("authorization")
    if (
        len(headers) != 1
        or len(headers[0]) > 8192
        or re.fullmatch(r"Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", headers[0])
        is None
    ):
        raise HTTPException(401, "push authentication required")
    try:
        verify = cast(Callable[..., dict[str, Any]], id_token.verify_oauth2_token)
        claims = verify(
            headers[0][7:], certificate_request, audience=audience, clock_skew_in_seconds=0
        )
        now = int(time.time())
        if (
            claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}
            or claims.get("aud") != audience
            or claims.get("email") != email
            or claims.get("email_verified") is not True
            or type(claims.get("iat")) is not int
            or type(claims.get("exp")) is not int
            or not claims["iat"] <= now < claims["exp"]
            or not isinstance(claims.get("sub"), str)
            or not 1 <= len(claims["sub"]) <= 255
        ):
            raise ValueError("invalid identity")
    except Exception:
        # Provider errors may include claims or tokens. Never surface/log their text.
        raise HTTPException(401, "push authentication required") from None
