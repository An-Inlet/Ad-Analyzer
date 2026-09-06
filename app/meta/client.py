"""Bounded transport using fixed read-only Graph endpoints; no provider bodies in errors."""

import hashlib
import hmac
import json
import re
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.meta.security import API_VERSION, MetaError, identifier
from app.settings import Settings

PAGE_SIZE = 100


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def graph_error(data: dict[str, Any]) -> None:
    error = data.get("error")
    if error:
        code = error.get("code") if isinstance(error, dict) else None
        if code in {102, 190, 10, 200, 294}:
            raise MetaError("meta_reconnect_required")
        if code in {4, 17, 32, 613, 80004}:
            raise MetaError("meta_throttled", retry_after=300)
        raise MetaError("meta_query_failed")


def unpack_page(
    data: dict[str, Any], previous: str | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    graph_error(data)
    items = data.get("data")
    if (
        not isinstance(items, list)
        or len(items) > PAGE_SIZE
        or any(not isinstance(x, dict) for x in items)
    ):
        raise MetaError("meta_invalid_page")
    paging = data.get("paging", {})
    if not isinstance(paging, dict):
        raise MetaError("meta_invalid_page")
    # Provider-generated next URLs can include credentials. Never store or follow them.
    more = bool(paging.get("next"))
    cursor = (
        paging.get("cursors", {}).get("after")
        if isinstance(paging.get("cursors", {}), dict)
        else None
    )
    if more and (
        not isinstance(cursor, str)
        or not re.fullmatch(r"[A-Za-z0-9_=+/-]{1,4096}", cursor)
        or cursor == previous
    ):
        raise MetaError("meta_invalid_cursor")
    return items, cursor if more else None


class MetaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _request(
        self, path: str, params: dict[str, str], token: str | None = None
    ) -> dict[str, Any]:
        if not re.fullmatch(
            r"(?:oauth/access_token|me/(?:permissions|adaccounts)|act_[0-9]{1,32}(?:/(?:campaigns|adsets|insights))?)",
            path,
        ):
            raise MetaError("meta_invalid_path")
        headers = {"Accept": "application/json"}
        query = dict(params)
        if token:
            headers["Authorization"] = "Bearer " + token
            if not self.settings.meta_client_secret:
                raise MetaError("meta_configuration_required")
            query["appsecret_proof"] = hmac.new(
                self.settings.meta_client_secret.get_secret_value().encode(),
                token.encode(),
                hashlib.sha256,
            ).hexdigest()
        request = Request(
            f"https://graph.facebook.com/{API_VERSION}/{path}?" + urlencode(query),
            headers=headers,
            method="GET",
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=12) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise MetaError("meta_response_too_large")
                data = json.loads(raw)
        except HTTPError as exc:
            # Graph often uses HTTP 400 for expired tokens. Parse only the bounded
            # numeric error code; discard all text and never expose an upstream URL.
            try:
                failure = json.loads(exc.read(64_001))
                if isinstance(failure, dict):
                    graph_error(failure)
            except (ValueError, OSError):
                pass
            if exc.code in {401, 403}:
                raise MetaError("meta_reconnect_required") from None
            if exc.code == 429:
                raise MetaError("meta_throttled", retry_after=300) from None
            raise MetaError("meta_unavailable") from None
        except (URLError, OSError, TimeoutError, ValueError):
            raise MetaError("meta_unavailable") from None
        if not isinstance(data, dict):
            raise MetaError("meta_invalid_response")
        graph_error(data)
        return data

    def token(
        self, *, code: str | None = None, exchange_token: str | None = None
    ) -> dict[str, Any]:
        if not self.settings.meta_client_secret:
            raise MetaError("meta_configuration_required")
        params = {
            "client_id": self.settings.meta_client_id,
            "client_secret": self.settings.meta_client_secret.get_secret_value(),
        }
        if code:
            params.update(code=code, redirect_uri=self.settings.meta_redirect_uri)
        elif exchange_token:
            params.update(grant_type="fb_exchange_token", fb_exchange_token=exchange_token)
        else:
            raise MetaError("meta_reconnect_required")
        return self._request("oauth/access_token", params)

    def permissions(self, token: str) -> dict[str, Any]:
        return self._request("me/permissions", {"limit": "100"}, token)

    def accounts(self, token: str, cursor: str | None = None) -> dict[str, Any]:
        params = {"fields": "account_id,name,currency,timezone_name,account_status", "limit": "100"}
        if cursor:
            params["after"] = cursor
        return self._request("me/adaccounts", params, token)

    def account(self, account_id: str, token: str) -> dict[str, Any]:
        return self._request(
            "act_" + identifier(account_id),
            {"fields": "account_id,name,currency,timezone_name,account_status"},
            token,
        )

    def page(
        self,
        account_id: str,
        token: str,
        phase: str,
        cursor: str | None,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        params = {"limit": str(PAGE_SIZE)}
        if phase == "campaigns":
            params["fields"] = "id,account_id,name,status,objective"
        elif phase == "adsets":
            params["fields"] = "id,account_id,campaign_id,name,status"
        elif phase == "insights":
            params.update(
                fields="account_id,campaign_id,campaign_name,date_start,date_stop,account_currency,impressions,clicks,spend,actions,action_values",
                level="campaign",
                time_increment="1",
                time_range=json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
            )
        else:
            raise MetaError("meta_invalid_path")
        if cursor:
            params["after"] = cursor
        return self._request("act_" + identifier(account_id) + "/" + phase, params, token)
