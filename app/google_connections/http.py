"""Bounded Google REST reads. Construction does not perform IO; runtime is opt-in."""

import base64
import json
import re
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import httpx
from pydantic import SecretStr

from app.google_connections.contracts import Account, CampaignRow, Grant, MetricRow, Page


class GoogleReadError(RuntimeError):
    """Sanitized provider failure; raw responses and credentials never escape."""


def account(value: str) -> str:
    if not re.fullmatch(r"[0-9]{10}", value):
        raise GoogleReadError("google_account_invalid")
    return value


class GoogleHTTPRead:
    mode: Literal["google_read"] = "google_read"

    def __init__(
        self,
        client_id: str,
        secret: SecretStr,
        developer: SecretStr,
        version: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not client_id or not secret.get_secret_value() or not developer.get_secret_value():
            raise ValueError("Google runtime configuration incomplete")
        if not re.fullmatch(r"v[1-9][0-9]{1,2}", version):
            raise ValueError("Google API version must be explicitly pinned")
        self.client_id, self.secret, self.developer = client_id, secret, developer
        self.version, self.transport = version, transport

    def _request(
        self,
        url: str,
        *,
        token: str | None = None,
        login: str | None = None,
        data: dict[str, str] | None = None,
        body: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if token:
            headers = {
                "Authorization": f"Bearer {token}",
                "developer-token": self.developer.get_secret_value(),
            }
        if login:
            headers["login-customer-id"] = account(login)
        try:
            with (
                httpx.Client(
                    transport=self.transport,
                    timeout=httpx.Timeout(30, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(
                    "POST" if data is not None or body is not None else "GET",
                    url,
                    headers=headers,
                    data=data,
                    json=body,
                ) as response,
            ):
                if response.status_code in (401, 403):
                    raise GoogleReadError("google_authorization_unavailable")
                if response.status_code == 429:
                    raise GoogleReadError("google_rate_limited")
                if not 200 <= response.status_code < 300:
                    raise GoogleReadError("google_read_unavailable")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 8_000_000:
                        raise GoogleReadError("google_response_exceeds_bounds")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise GoogleReadError("google_response_invalid")
                return result
        except (httpx.HTTPError, ValueError, TypeError):
            raise GoogleReadError("google_read_unavailable") from None

    def _token(self, **fields: str) -> dict[str, Any]:
        result = self._request(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.secret.get_secret_value(),
                **fields,
            },
        )
        if not isinstance(result.get("access_token"), str) or not result["access_token"]:
            raise GoogleReadError("google_token_invalid")
        if str(result.get("token_type", "")).lower() != "bearer":
            raise GoogleReadError("google_token_invalid")
        if (
            "scope" in result
            and "https://www.googleapis.com/auth/adwords" not in str(result["scope"]).split()
        ):
            raise GoogleReadError("google_scope_unavailable")
        return result

    def _search(
        self, token: str, aid: str, login: str | None, query: str, cursor: str = ""
    ) -> tuple[list[dict[str, Any]], str]:
        result = self._request(
            f"https://googleads.googleapis.com/{self.version}/customers/{account(aid)}/googleAds:search",
            token=token,
            login=login,
            body={"query": query, "pageToken": cursor},
        )
        rows, next_token = result.get("results", []), result.get("nextPageToken", "")
        if (
            not isinstance(rows, list)
            or len(rows) > 10000
            or any(not isinstance(row, dict) for row in rows)
            or not isinstance(next_token, str)
            or len(next_token) > 3000
            or (next_token and next_token == cursor)
        ):
            raise GoogleReadError("google_page_invalid")
        for row in rows:
            for entity in ("customer", "campaign"):
                name = row.get(entity, {}).get("resourceName")
                if name and not name.startswith(f"customers/{aid}/") and name != f"customers/{aid}":
                    raise GoogleReadError("google_account_mismatch")
        return rows, next_token

    def exchange(self, code: str, redirect_uri: str) -> Grant:
        try:
            tokens = self._token(
                code=code, redirect_uri=redirect_uri, grant_type="authorization_code"
            )
            refresh = tokens.get("refresh_token")
            if not isinstance(refresh, str) or not refresh or len(refresh) > 8192:
                raise GoogleReadError("google_fresh_consent_required")
            token = tokens["access_token"]
            roots = self._request(
                f"https://googleads.googleapis.com/{self.version}/customers:listAccessibleCustomers",
                token=token,
            ).get("resourceNames", [])
            if not isinstance(roots, list) or len(roots) > 1000:
                raise GoogleReadError("google_discovery_exceeds_bounds")
            queue: list[tuple[str, str | None]] = []
            for name in roots:
                if not isinstance(name, str) or not re.fullmatch(r"customers/[0-9]{10}", name):
                    raise GoogleReadError("google_account_invalid")
                queue.append((name.split("/")[1], None))
            seen: set[str] = set()
            accounts: list[Account] = []
            while queue:
                aid, login = queue.pop(0)
                if aid in seen:
                    continue
                if len(seen) >= 1000:
                    raise GoogleReadError("google_discovery_exceeds_bounds")
                seen.add(aid)
                rows, cursor = self._search(
                    token,
                    aid,
                    login,
                    (
                        "SELECT customer.id, customer.descriptive_name, "
                        "customer.currency_code, customer.time_zone, customer.manager FROM "
                        "customer LIMIT 1"
                    ),
                )
                if len(rows) != 1 or cursor:
                    raise GoogleReadError("google_metadata_invalid")
                customer = rows[0]["customer"]
                if not isinstance(customer.get("manager", False), bool):
                    raise GoogleReadError("google_metadata_invalid")
                if str(customer["id"]) != aid:
                    raise GoogleReadError("google_account_mismatch")
                if customer.get("manager", False):
                    cursor = ""
                    cursors: set[str] = set()
                    while True:
                        children, cursor = self._search(
                            token,
                            aid,
                            login,
                            (
                                "SELECT customer_client.id FROM customer_client WHERE "
                                "customer_client.level = 1"
                            ),
                            cursor,
                        )
                        queue.extend(
                            (account(str(r["customerClient"]["id"])), login or aid)
                            for r in children
                        )
                        if len(queue) > 1000 or cursor in cursors or len(cursors) >= 100:
                            raise GoogleReadError("google_discovery_exceeds_bounds")
                        if not cursor:
                            break
                        cursors.add(cursor)
                else:
                    accounts.append(
                        Account(
                            external_id=aid,
                            login_customer_id=login,
                            name=customer.get("descriptiveName") or aid,
                            currency=customer["currencyCode"],
                            time_zone=customer["timeZone"],
                        )
                    )
                    if len(accounts) > 100:
                        raise GoogleReadError("google_discovery_exceeds_bounds")
            return Grant(refresh_token=SecretStr(refresh), accounts=accounts)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise GoogleReadError("google_response_invalid") from None

    def page(
        self,
        refresh_token: str,
        account_id: str,
        start: date,
        end: date,
        cursor: str | None,
        login_customer_id: str | None = None,
    ) -> Page:
        try:
            account(account_id)
            if login_customer_id:
                account(login_customer_id)
            if start > end:
                raise ValueError("window")
            phase, page_token = "campaigns", ""
            if cursor:
                if len(cursor) > 4096:
                    raise ValueError("cursor")
                phase, encoded = cursor.split(":", 1)
                page_token = base64.b64decode(encoded, altchars=b"-_", validate=True).decode()
            if phase not in {"campaigns", "metrics"}:
                raise ValueError("phase")
            token = self._token(refresh_token=refresh_token, grant_type="refresh_token")[
                "access_token"
            ]
            query = (
                "SELECT campaign.id, campaign.name, campaign.status, "
                "campaign.advertising_channel_type FROM campaign"
            )
            if phase == "metrics":
                query = (
                    "SELECT campaign.id, segments.date, metrics.impressions, "
                    "metrics.clicks, metrics.cost_micros, metrics.conversions, "
                    "metrics.conversions_value FROM campaign WHERE segments.date BETWEEN "
                ) + f"'{start.isoformat()}' AND '{end.isoformat()}'"
            rows, following = self._search(token, account_id, login_customer_id, query, page_token)
            campaigns, metrics = [], []
            for row in rows:
                campaign = row["campaign"]
                if phase == "campaigns":
                    campaigns.append(
                        CampaignRow(
                            external_id=str(campaign["id"]),
                            name=campaign["name"],
                            status=campaign["status"],
                            channel=campaign["advertisingChannelType"],
                        )
                    )
                else:
                    m = row.get("metrics", {})
                    metrics.append(
                        MetricRow(
                            campaign_external_id=str(campaign["id"]),
                            day=row["segments"]["date"],
                            impressions=m.get("impressions", 0),
                            clicks=m.get("clicks", 0),
                            cost_micros=m.get("costMicros", 0),
                            conversions=format(
                                Decimal(str(m.get("conversions", 0))).quantize(Decimal("0.000001")),
                                "f",
                            ),
                            conversion_value_micros=int(
                                Decimal(str(m.get("conversionsValue", 0))) * 1_000_000
                            ),
                        )
                    )
            next_cursor = (
                phase + ":" + base64.urlsafe_b64encode(following.encode()).decode()
                if following
                else ("metrics:" if phase == "campaigns" else None)
            )
            return Page(
                external_account_id=account_id,
                campaigns=campaigns,
                metrics=metrics,
                next_cursor=next_cursor,
            )
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            raise GoogleReadError("google_response_invalid") from None
