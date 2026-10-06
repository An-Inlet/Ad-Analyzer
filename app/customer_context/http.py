"""Opt-in read-only CRM HTTP adapters; construction never performs network IO.

Only account proof and minimal current profile context are exposed. No events,
revenue, customer identity matching, persistence or campaign write endpoints.
"""

import base64
import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from urllib.parse import quote, urlencode, urlsplit

import httpx
from pydantic import SecretStr

from app.customer_context.contracts import ContextPage, CustomerProvider
from app.customer_context.wire import KLAVIYO_REVISION, OMNISEND_REVISION, ProfileReader
from app.sources.contracts import SourceAccount, SourceGrant


class CRMHTTPLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        arguments = record.args if isinstance(record.args, tuple) else ()
        if any(
            isinstance(value, httpx.URL)
            and value.host
            in {
                "a.klaviyo.com",
                "api.hubspot.com",
                "api.hubapi.com",
                "api.omnisend.com",
                "app.omnisend.com",
            }
            for value in arguments
        ):
            # Opaque pagination cursors may still encode identifiers. Suppress
            # httpx's URL/query diagnostic; never print provider payloads instead.
            record.msg, record.args = "CRM HTTP request completed (details redacted)", ()
        return True


class CRMReadError(RuntimeError):
    """Sanitized error; never include credentials, raw payloads or customer identifiers."""


class CRMAuthenticationUnavailable(CRMReadError):
    """The current credential lacks authentication or required access; do not retry as 429."""

    def __init__(self) -> None:
        super().__init__("crm_authorization_unavailable")


class CRMRateLimited(CRMReadError):
    """Bounded scheduling hint, never a revocation signal."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("crm_rate_limited")
        self.retry_after = retry_after


def retry_seconds(value: str | None, now: datetime) -> int:
    try:
        if value is None or len(value) > 128:
            return 60
        seconds = (
            int(value)
            if re.fullmatch(r"[0-9]{1,10}", value)
            else int((parsedate_to_datetime(value) - now).total_seconds()) + 1
        )
        return max(5, min(seconds, 86400))
    except (ValueError, TypeError, OverflowError):
        return 60


def bounded(value: object, maximum: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or any(ord(c) < 33 or ord(c) == 127 for c in value)
    ):
        raise CRMReadError("crm_value_invalid")
    return value


def oauth_parameters(state: str, redirect: str, provider: CustomerProvider) -> None:
    parsed = urlsplit(redirect)
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{43}", state)
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or parsed.path != f"/api/customer/v1/sources/{provider}/callback"
        or parsed.query
        or parsed.fragment
    ):
        raise CRMReadError("crm_authorization_invalid")


class CRMHTTP:
    mode: Literal["fixture", "provider_read"] = "provider_read"
    provider: CustomerProvider
    endpoints: frozenset[tuple[str, str]]

    def __init__(
        self,
        client_id: str,
        secret: SecretStr,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", client_id):
            raise ValueError("CRM client configuration unavailable")
        bounded(secret.get_secret_value())
        self.client_id, self.secret = client_id, secret
        self.transport, self.clock = transport, clock
        logger = logging.getLogger("httpx")
        if not any(isinstance(item, CRMHTTPLogFilter) for item in logger.filters):
            logger.addFilter(CRMHTTPLogFilter())

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        empty: bool = False,
    ) -> dict[str, Any]:
        if (method, url) not in self.endpoints:
            raise CRMReadError("crm_endpoint_unavailable")
        try:
            with (
                httpx.Client(
                    transport=self.transport,
                    timeout=httpx.Timeout(20, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(method, url, headers=headers, params=params, data=data) as response,
            ):
                if response.status_code in {401, 403}:
                    raise CRMAuthenticationUnavailable()
                if response.status_code == 429:
                    raise CRMRateLimited(
                        retry_seconds(response.headers.get("Retry-After"), self.clock())
                    )
                if not 200 <= response.status_code < 300:
                    raise CRMReadError("crm_read_unavailable")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000:
                        raise CRMReadError("crm_response_exceeds_bounds")
                if empty and not raw:
                    return {}
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise CRMReadError("crm_response_invalid")
                return value
        except (httpx.HTTPError, ValueError, TypeError, OverflowError):
            raise CRMReadError("crm_read_unavailable") from None

    def get(self, path: str, headers: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
        return self._request("GET", path, headers=headers, params=params)

    def account(self, token: str) -> SourceAccount:
        raise NotImplementedError

    def page(self, account_id: str, token: str, cursor: str | None, now: datetime) -> ContextPage:
        bounded(token)
        if cursor is not None:
            bounded(cursor)
        # Account ownership is proved from the token for every page, never echoed
        # from caller input or a profile property. No mutable shared identity cache.
        if self.account(token).external_id != account_id:
            raise CRMReadError("crm_account_mismatch")
        try:
            page = ProfileReader(self.provider, self).page(account_id, token, cursor, now)
            if cursor is not None and page.next_cursor == cursor:
                raise CRMReadError("crm_cursor_repeated")
            return page
        except (ValueError, KeyError, TypeError, AttributeError):
            raise CRMReadError("crm_profile_response_invalid") from None

    def read(
        self, account: str, token: str, start: date, end: date, cursor: str | None
    ) -> dict[str, Any]:
        if start > end:
            raise CRMReadError("crm_window_invalid")
        # These providers expose current profiles, not historical sales over this range.
        return self.page(account, token, cursor, self.clock()).model_dump(mode="json")

    def grant(self, payload: dict[str, Any], *, expected_account: str | None = None) -> SourceGrant:
        try:
            token = bounded(payload.get("access_token"))
            refresh = bounded(payload.get("refresh_token"))
            lifetime = payload.get("expires_in")
            if (
                str(payload.get("token_type", "")).lower() != "bearer"
                or type(lifetime) is not int
                or not 0 < lifetime <= 10_000_000_000
            ):
                raise CRMReadError("crm_grant_invalid")
            account = self.account(token)
            if expected_account is not None and account.external_id != expected_account:
                raise CRMReadError("crm_account_mismatch")
            return SourceGrant(
                access_token=SecretStr(token),
                refresh_token=SecretStr(refresh),
                expires_at=self.clock() + timedelta(seconds=lifetime),
                accounts=[account],
            )
        except (ValueError, TypeError, OverflowError):
            raise CRMReadError("crm_grant_invalid") from None


class KlaviyoHTTPRead(CRMHTTP):
    provider: CustomerProvider = "klaviyo"
    scopes = frozenset({"accounts:read", "profiles:read"})
    endpoints = frozenset(
        {
            ("POST", "https://a.klaviyo.com/oauth/token"),
            ("POST", "https://a.klaviyo.com/oauth/revoke"),
            ("GET", "https://a.klaviyo.com/api/accounts"),
            ("GET", "https://a.klaviyo.com/api/profiles"),
        }
    )

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        raise CRMReadError("klaviyo_pkce_required")

    def exchange(self, code: str, redirect_uri: str) -> SourceGrant:
        raise CRMReadError("klaviyo_pkce_required")

    def authorize_url_pkce(self, state: str, redirect_uri: str, code_challenge: str) -> str:
        oauth_parameters(state, redirect_uri, self.provider)
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", code_challenge):
            raise CRMReadError("klaviyo_pkce_invalid")
        return "https://www.klaviyo.com/oauth/authorize?" + urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(sorted(self.scopes)),
                "state": state,
                "code_challenge_method": "S256",
                "code_challenge": code_challenge,
            }
        )

    def _oauth(self, path: str, data: dict[str, str], *, empty: bool = False) -> dict[str, Any]:
        basic = base64.b64encode(
            f"{self.client_id}:{self.secret.get_secret_value()}".encode()
        ).decode()
        return self._request(
            "POST",
            "https://a.klaviyo.com/oauth/" + path,
            headers={"Authorization": "Basic " + basic},
            data=data,
            empty=empty,
        )

    def _grant(self, payload: dict[str, Any], expected_account: str | None = None) -> SourceGrant:
        scope = payload.get("scope")
        if not isinstance(scope, str) or set(scope.split()) != self.scopes:
            raise CRMReadError("crm_scope_mismatch")
        return self.grant(payload, expected_account=expected_account)

    def exchange_pkce(self, code: str, redirect_uri: str, code_verifier: str) -> SourceGrant:
        oauth_parameters("a" * 43, redirect_uri, self.provider)
        if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", code_verifier):
            raise CRMReadError("klaviyo_pkce_invalid")
        return self._grant(
            self._oauth(
                "token",
                {
                    "grant_type": "authorization_code",
                    "code": bounded(code),
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
            )
        )

    def account(self, token: str) -> SourceAccount:
        payload = self.get(
            "https://a.klaviyo.com/api/accounts",
            {"Authorization": "Bearer " + bounded(token), "revision": KLAVIYO_REVISION},
            {"fields[account]": "id"},
        )
        try:
            rows = payload["data"]
            if not isinstance(rows, list) or len(rows) != 1 or rows[0]["type"] != "account":
                raise CRMReadError("crm_account_unavailable")
            return SourceAccount(external_id=rows[0]["id"], name="Klaviyo Account")
        except (KeyError, TypeError, ValueError):
            raise CRMReadError("crm_account_unavailable") from None

    def refresh(self, refresh_token: str, account_id: str) -> SourceGrant:
        return self._grant(
            self._oauth(
                "token", {"grant_type": "refresh_token", "refresh_token": bounded(refresh_token)}
            ),
            account_id,
        )

    def revoke(self, refresh_token: str) -> None:
        self._oauth(
            "revoke",
            {"token_type_hint": "refresh_token", "token": bounded(refresh_token)},
            empty=True,
        )


class HubSpotHTTPRead(CRMHTTP):
    provider: CustomerProvider = "hubspot"
    scopes = frozenset({"oauth", "crm.objects.contacts.read"})
    endpoints = frozenset(
        {
            ("POST", "https://api.hubspot.com/oauth/v3/token"),
            ("POST", "https://api.hubspot.com/oauth/v3/token/introspect"),
            ("GET", "https://api.hubapi.com/crm/v3/objects/contacts"),
        }
    )

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        oauth_parameters(state, redirect_uri, self.provider)
        return "https://app.hubspot.com/oauth/authorize?" + urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(sorted(self.scopes)),
                "state": state,
            }
        )

    def _oauth(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        return self._request(
            "POST",
            "https://api.hubspot.com/oauth/v3/" + path,
            data={
                **data,
                "client_id": self.client_id,
                "client_secret": self.secret.get_secret_value(),
            },
        )

    def exchange(self, code: str, redirect_uri: str) -> SourceGrant:
        oauth_parameters("a" * 43, redirect_uri, self.provider)
        return self.grant(
            self._oauth(
                "token",
                {
                    "grant_type": "authorization_code",
                    "code": bounded(code),
                    "redirect_uri": redirect_uri,
                },
            )
        )

    def account(self, token: str) -> SourceAccount:
        payload = self._oauth(
            "token/introspect", {"token_type_hint": "access_token", "access_token": bounded(token)}
        )
        scopes, hub = payload.get("scopes"), payload.get("hub_id")
        if (
            payload.get("active") is not True
            or payload.get("token") != token
            or type(payload.get("expires_in")) is not int
            or payload["expires_in"] <= 0
            or payload.get("client_id") != self.client_id
            or payload.get("token_use") != "access_token"
            or type(hub) is not int
            or hub <= 0
            or not isinstance(scopes, list)
            or not all(isinstance(scope, str) for scope in scopes)
            or set(scopes) != self.scopes
        ):
            raise CRMReadError("crm_account_unavailable")
        return SourceAccount(external_id=str(hub), name="HubSpot Account")

    def refresh(self, refresh_token: str, account_id: str) -> SourceGrant:
        return self.grant(
            self._oauth(
                "token", {"grant_type": "refresh_token", "refresh_token": bounded(refresh_token)}
            ),
            expected_account=account_id,
        )


class OmnisendHTTPRead(CRMHTTP):
    """Read-only 2026-03-15 contract pinned to the official Omnisend WordPress SDK."""

    provider: CustomerProvider = "omnisend"
    scopes = frozenset({"brands.read", "contacts.read"})
    endpoints = frozenset(
        {
            ("POST", "https://app.omnisend.com/oauth2/token"),
            ("GET", "https://api.omnisend.com/api/brands/current"),
            ("GET", "https://api.omnisend.com/api/contacts"),
        }
    )

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        oauth_parameters(state, redirect_uri, self.provider)
        return "https://app.omnisend.com/oauth2/authorize?" + urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(sorted(self.scopes)),
                "state": state,
            },
            quote_via=quote,
        )

    def _oauth(self, data: dict[str, str]) -> dict[str, Any]:
        return self._request(
            "POST",
            "https://app.omnisend.com/oauth2/token",
            data={
                **data,
                "client_id": self.client_id,
                "client_secret": self.secret.get_secret_value(),
            },
        )

    def _grant(
        self,
        payload: dict[str, Any],
        *,
        expected_account: str | None = None,
        previous_refresh: str | None = None,
    ) -> SourceGrant:
        scope = payload.get("scope")
        # Initial exchange must affirm the exact requested read permissions. For
        # renewal, omitted scope retains the original OAuth grant (RFC 6749 6);
        # an explicitly supplied differing scope always fails closed.
        if not (previous_refresh is not None and "scope" not in payload) and (
            not isinstance(scope, str) or set(scope.split()) != self.scopes
        ):
            raise CRMReadError("crm_scope_mismatch")
        token = bounded(payload.get("access_token"))
        refresh = payload.get("refresh_token", previous_refresh)
        if "refresh_token" in payload or refresh is not None:
            refresh = bounded(refresh)
        lifetime = payload.get("expires_in")
        if str(payload.get("token_type", "")).lower() != "bearer" or (
            lifetime is not None
            and (type(lifetime) is not int or not 0 < lifetime <= 10_000_000_000)
        ):
            raise CRMReadError("crm_grant_invalid")
        try:
            account = self.account(token)
            if expected_account is not None and account.external_id != expected_account:
                raise CRMReadError("crm_account_mismatch")
            return SourceGrant(
                access_token=SecretStr(token),
                refresh_token=SecretStr(refresh) if refresh else None,
                expires_at=self.clock() + timedelta(seconds=lifetime)
                if lifetime is not None
                else None,
                accounts=[account],
            )
        except (ValueError, TypeError, OverflowError):
            raise CRMReadError("crm_grant_invalid") from None

    def exchange(self, code: str, redirect_uri: str) -> SourceGrant:
        oauth_parameters("a" * 43, redirect_uri, self.provider)
        return self._grant(
            self._oauth(
                {
                    "grant_type": "authorization_code",
                    "code": bounded(code),
                    "redirect_uri": redirect_uri,
                }
            )
        )

    def account(self, token: str) -> SourceAccount:
        payload = self.get(
            "https://api.omnisend.com/api/brands/current",
            {"Authorization": "Bearer " + bounded(token), "Omnisend-Version": OMNISEND_REVISION},
            {},
        )
        try:
            return SourceAccount(external_id=payload["brandID"], name="Omnisend Brand")
        except (KeyError, TypeError, ValueError):
            raise CRMReadError("crm_account_unavailable") from None

    def get(self, path: str, headers: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
        payload = super().get(path, headers, params)
        if path == "https://api.omnisend.com/api/contacts":
            paging = payload.get("paging")
            if not isinstance(paging, dict) or type(paging.get("hasMore")) is not bool:
                raise CRMReadError("crm_profile_response_invalid")
        return payload

    def refresh(self, refresh_token: str, account_id: str) -> SourceGrant:
        previous = bounded(refresh_token)
        return self._grant(
            self._oauth({"grant_type": "refresh_token", "refresh_token": previous}),
            expected_account=account_id,
            previous_refresh=previous,
        )
