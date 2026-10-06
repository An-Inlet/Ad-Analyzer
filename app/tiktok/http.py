"""Opt-in TikTok v1.3 HTTP reads. No mutation routes or network IO at construction."""

import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import SecretStr

from app.sources.contracts import SourceGrant
from app.tiktok.wire import TikTokReadAdapter

PATHS = {
    ("POST", "/open_api/v1.3/oauth2/access_token/"),
    ("GET", "/open_api/v1.3/advertiser/info/"),
    ("GET", "/open_api/v1.3/campaign/get/"),
    ("GET", "/open_api/v1.3/adgroup/get/"),
    ("GET", "/open_api/v1.3/ad/get/"),
    ("GET", "/open_api/v1.3/report/integrated/get/"),
}


class TikTokReadError(RuntimeError):
    """A provider failure safe to expose without raw bodies or credentials."""


class TikTokTransientError(TikTokReadError):
    """Timeout, rate limit or provider outage; the same page can be retried."""


class TikTokAuthorizationUnavailable(TikTokReadError):
    """The current authenticated advertiser request is no longer authorized."""


class TikTokProviderRejected(TikTokReadError):
    def __init__(self, code: int) -> None:
        if type(code) is not int or not 1 <= code <= 2**31 - 1:
            raise ValueError("invalid provider code")
        self.provider_code = code
        super().__init__("tiktok_provider_rejected")


class TikTokHTTPRead(TikTokReadAdapter):
    mode: Literal["fixture", "provider_read"] = "provider_read"

    def __init__(
        self,
        app_id: str,
        secret: SecretStr,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not re.fullmatch(r"[0-9]{1,32}", app_id) or not secret.get_secret_value():
            raise ValueError("TikTok runtime configuration incomplete")
        self.transport, self.clock = transport, clock
        super().__init__(self._http, app_id, secret)

    def _http(
        self, method: str, path: str, params: dict[str, Any], token: str | None
    ) -> dict[str, Any]:
        if (method, path) not in PATHS:
            raise TikTokReadError("tiktok_endpoint_unavailable")
        headers = {"Access-Token": token} if token else {}
        query = (
            {
                key: json.dumps(value, separators=(",", ":"))
                if isinstance(value, (list, dict, bool))
                else str(value)
                for key, value in params.items()
            }
            if method == "GET"
            else None
        )
        try:
            with (
                httpx.Client(
                    transport=self.transport,
                    timeout=httpx.Timeout(30, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(
                    method,
                    "https://business-api.tiktok.com" + path,
                    params=query,
                    json=params if method == "POST" else None,
                    headers=headers,
                ) as response,
            ):
                if response.status_code in {401, 403} and token is not None:
                    raise TikTokAuthorizationUnavailable("tiktok_authorization_unavailable")
                if response.status_code == 429 or response.status_code >= 500:
                    raise TikTokTransientError("tiktok_read_temporarily_unavailable")
                if not 200 <= response.status_code < 300:
                    raise TikTokReadError("tiktok_read_unavailable")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000:
                        raise TikTokReadError("tiktok_response_exceeds_bounds")
                result = json.loads(raw)
                if (
                    not isinstance(result, dict)
                    or type(result.get("code")) is not int
                    or not 0 <= result["code"] <= 2**31 - 1
                ):
                    raise TikTokReadError("tiktok_response_invalid")
                if result["code"] != 0:
                    raise TikTokProviderRejected(result["code"])
                if not isinstance(result.get("data"), dict):
                    raise TikTokReadError("tiktok_response_invalid")
                return result
        except httpx.HTTPError:
            raise TikTokTransientError("tiktok_read_temporarily_unavailable") from None
        except (ValueError, TypeError):
            raise TikTokReadError("tiktok_response_invalid") from None

    def exchange(self, code: str, redirect_uri: str) -> SourceGrant:
        # Capture optional provider lifetime without inventing a permanent grant.
        grant_data: dict[str, Any] = {}

        def exchange_io(
            method: str, path: str, params: dict[str, Any], token: str | None
        ) -> dict[str, Any]:
            response = self._http(method, path, params, token)
            if path == "/open_api/v1.3/oauth2/access_token/":
                grant_data.update(response["data"])
            return response

        try:
            grant = TikTokReadAdapter(exchange_io, self.app_id, self.secret).exchange(
                code, redirect_uri
            )
            ttl = grant_data.get("expires_in")
            if ttl is not None:
                if type(ttl) is not int or not 0 < ttl <= 366 * 86400:
                    raise TikTokReadError("tiktok_lifetime_invalid")
                grant.expires_at = self.clock() + timedelta(seconds=ttl)
            # No advertiser refresh protocol is qualified here. Do not retain
            # unused creator/unknown refresh material returned by a provider.
            return grant
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            raise TikTokReadError("tiktok_response_invalid") from None

    def read(
        self, account: str, token: str, start: date, end: date, cursor: str | None
    ) -> dict[str, Any]:
        if start > end or (end - start).days > 30 or (cursor and len(cursor) > 4096):
            raise TikTokReadError("tiktok_window_invalid")
        try:
            return super().read(account, token, start, end, cursor)
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            raise TikTokReadError("tiktok_response_invalid") from None
