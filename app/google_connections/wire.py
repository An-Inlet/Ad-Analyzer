"""Google read request/response adapter, exercised only with injected offline IO.

No runtime factory constructs this adapter. Provider clients must be supplied by a
separately authorized release; this module neither loads credentials nor opens sockets.
"""

import base64
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import SecretStr

from app.google_connections.contracts import Account, CampaignRow, Grant, MetricRow, Page


class GoogleSDK(Protocol):
    login_customer_id: str | None

    def get_service(self, name: str) -> Any: ...


class GoogleReadWireAdapter:
    mode: Literal["fixture"] = "fixture"

    def __init__(
        self, exchange: Callable[[str, str], dict[str, Any]], client: Callable[[str], GoogleSDK]
    ) -> None:
        self.exchange_token, self.client = exchange, client

    def exchange(self, code: str, redirect_uri: str) -> Grant:
        tokens = self.exchange_token(code, redirect_uri)
        refresh = tokens.get("refresh_token")
        if not isinstance(refresh, str) or not refresh or len(refresh) > 8192:
            raise ValueError("fresh offline consent required")
        if (
            "scope" in tokens
            and "https://www.googleapis.com/auth/adwords" not in str(tokens["scope"]).split()
        ):
            raise ValueError("required scope unavailable")
        client = self.client(refresh)
        accessible = client.get_service("CustomerService").list_accessible_customers()
        queue: list[tuple[str, str | None]] = [
            (str(name).removeprefix("customers/"), None) for name in accessible.resource_names
        ]
        seen: set[str] = set()
        accounts: list[Account] = []
        while queue:
            account_id, manager_login = queue.pop(0)
            client.login_customer_id = manager_login
            if account_id in seen:
                continue
            if not account_id.isdigit() or len(account_id) != 10 or len(seen) >= 1000:
                raise ValueError("account discovery exceeds bounds")
            seen.add(account_id)
            # The injected client carries any required manager login context. A future
            # runtime factory must qualify this against the actual authorized hierarchy.
            rows = client.get_service("GoogleAdsService").search(
                customer_id=account_id,
                query=(
                    "SELECT customer.id, customer.descriptive_name, customer.currency_code, "
                    "customer.time_zone, customer.manager FROM customer LIMIT 1"
                ),
            )
            rows = list(rows)
            if len(rows) != 1:
                raise ValueError("account metadata unavailable")
            customer = rows[0].customer
            if str(customer.id) != account_id:
                raise ValueError("account metadata mismatch")
            if customer.manager:
                children = client.get_service("GoogleAdsService").search(
                    customer_id=account_id,
                    query=(
                        "SELECT customer_client.id FROM customer_client "
                        "WHERE customer_client.level = 1"
                    ),
                )
                for child in children:
                    queue.append((str(child.customer_client.id), manager_login or account_id))
                    if len(queue) > 1000:
                        raise ValueError("account discovery exceeds bounds")
            else:
                accounts.append(
                    Account(
                        external_id=account_id,
                        login_customer_id=manager_login,
                        name=customer.descriptive_name or account_id,
                        currency=customer.currency_code,
                        time_zone=customer.time_zone,
                    )
                )
        return Grant(refresh_token=SecretStr(refresh), accounts=accounts)

    def page(
        self,
        refresh_token: str,
        account_id: str,
        start: date,
        end: date,
        cursor: str | None,
        login_customer_id: str | None = None,
    ) -> Page:
        phase, token = "campaigns", ""
        if cursor:
            phase, encoded = cursor.split(":", 1)
            if phase not in {"campaigns", "metrics"}:
                raise ValueError("invalid read phase")
            token = base64.urlsafe_b64decode(encoded.encode()).decode()
        if not account_id.isdigit() or len(account_id) != 10 or start > end:
            raise ValueError("invalid account window")
        query = (
            "SELECT campaign.id, campaign.name, campaign.status, "
            "campaign.advertising_channel_type FROM campaign"
        )
        if phase == "metrics":
            query = (
                "SELECT campaign.id, segments.date, metrics.impressions, metrics.clicks, "
                "metrics.cost_micros, "
                "metrics.conversions, metrics.conversions_value FROM campaign "
                "WHERE segments.date BETWEEN "
                f"'{start.isoformat()}' AND '{end.isoformat()}'"
            )
        client = self.client(refresh_token)
        client.login_customer_id = login_customer_id
        response = client.get_service("GoogleAdsService").search(
            request={"customer_id": account_id, "query": query, "page_token": token}
        )
        # Process exactly one SDK response page, not the auto-paging iterator.
        raw = next(iter(response.pages))
        campaigns, metrics = [], []
        for row in raw.results:
            if phase == "campaigns":
                campaigns.append(
                    CampaignRow(
                        external_id=str(row.campaign.id),
                        name=row.campaign.name,
                        status=row.campaign.status.name,
                        channel=row.campaign.advertising_channel_type.name,
                    )
                )
            else:
                metrics.append(
                    MetricRow(
                        campaign_external_id=str(row.campaign.id),
                        day=row.segments.date,
                        impressions=row.metrics.impressions,
                        clicks=row.metrics.clicks,
                        cost_micros=row.metrics.cost_micros,
                        conversions=format(
                            Decimal(str(row.metrics.conversions)).quantize(Decimal("0.000001")), "f"
                        ),
                        conversion_value_micros=int(
                            Decimal(str(row.metrics.conversions_value)) * 1_000_000
                        ),
                    )
                )
        next_cursor = None
        if raw.next_page_token:
            next_cursor = (
                phase + ":" + base64.urlsafe_b64encode(raw.next_page_token.encode()).decode()
            )
        elif phase == "campaigns":
            next_cursor = "metrics:"
        return Page(
            external_account_id=account_id,
            campaigns=campaigns,
            metrics=metrics,
            next_cursor=next_cursor,
        )


class OAuthCodeExchange:
    """Fixed Google token endpoint; injected HTTP call allows offline request assertions."""

    def __init__(
        self,
        post: Callable[[str, dict[str, str]], dict[str, Any]],
        client_id: str,
        client_secret: SecretStr,
    ) -> None:
        self.post, self.client_id, self.client_secret = post, client_id, client_secret

    def __call__(self, code: str, redirect_uri: str) -> dict[str, Any]:
        return self.post(
            "https://oauth2.googleapis.com/token",
            {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret.get_secret_value(),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
