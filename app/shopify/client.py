import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.settings import Settings
from app.shopify.queries import ORDERS_QUERY, SHOP_QUERY
from app.shopify.security import API_VERSION, ShopifyError, shop_domain


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


class ShopifyClient:
    """Fixed Shopify HTTPS destinations and fixed read-only GraphQL operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _request(
        self, shop: str, path: str, payload: dict[str, Any], token: str | None = None
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["X-Shopify-Access-Token"] = token
        request = Request(
            f"https://{shop_domain(shop)}{path}",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=15) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ShopifyError("shopify_response_too_large")
                data = json.loads(raw)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise ShopifyError("shopify_reconnect_required") from None
            if exc.code == 429:
                delay = str(exc.headers.get("Retry-After", "60"))
                raise ShopifyError(
                    "shopify_throttled", retry_after=int(delay) if delay.isdigit() else 60
                ) from None
            raise ShopifyError("shopify_unavailable") from None
        except (URLError, OSError, TimeoutError, ValueError):
            raise ShopifyError("shopify_unavailable") from None
        if not isinstance(data, dict):
            raise ShopifyError("shopify_invalid_response")
        return data

    def token(
        self, shop: str, *, code: str | None = None, refresh: str | None = None
    ) -> dict[str, Any]:
        if not self.settings.shopify_client_secret:
            raise ShopifyError("shopify_configuration_required")
        payload = {
            "client_id": self.settings.shopify_client_id,
            "client_secret": self.settings.shopify_client_secret.get_secret_value(),
        }
        if code:
            payload.update(code=code, expiring="1")
        elif refresh:
            payload.update(grant_type="refresh_token", refresh_token=refresh)
        else:
            raise ShopifyError("shopify_reconnect_required")
        return self._request(shop, "/admin/oauth/access_token", payload)

    def _query(
        self, shop: str, token: str, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        response = self._request(
            shop,
            f"/admin/api/{API_VERSION}/graphql.json",
            {"query": query, "variables": variables},
            token,
        )
        if response.get("errors"):
            codes = {
                str(e.get("extensions", {}).get("code", ""))
                for e in response["errors"]
                if isinstance(e, dict)
            }
            if "THROTTLED" in codes:
                raise ShopifyError("shopify_throttled")
            if "ACCESS_DENIED" in codes:
                raise ShopifyError("shopify_scope_or_data_access_required")
            raise ShopifyError("shopify_query_failed")
        if not isinstance(response.get("data"), dict):
            raise ShopifyError("shopify_invalid_response")
        return dict(response["data"])

    def shop(self, shop: str, token: str) -> dict[str, Any]:
        return self._query(shop, token, SHOP_QUERY, {})

    def orders(self, shop: str, token: str, cursor: str | None, query: str) -> dict[str, Any]:
        data = self._query(shop, token, ORDERS_QUERY, {"after": cursor, "query": query})
        if not isinstance(data.get("orders"), dict):
            raise ShopifyError("shopify_invalid_response")
        return dict(data["orders"])
