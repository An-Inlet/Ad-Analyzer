"""Bounded Shopify agreement pagination; no customer data outside opaque IDs."""

import re
from typing import Any

from app.commerce import queries
from app.shopify.client import ShopifyClient
from app.shopify.security import ShopifyError


def gid(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"gid://shopify/[A-Za-z]+/[0-9]{1,24}", value
    ):
        raise ShopifyError("commerce_invalid_identity")
    return value


def connection_page(value: Any) -> tuple[list[dict[str, Any]], str | None]:
    try:
        nodes, info = value["nodes"], value["pageInfo"]
        if (
            not isinstance(nodes, list)
            or len(nodes) > 50
            or not all(isinstance(n, dict) for n in nodes)
        ):
            raise ValueError()
        more = info["hasNextPage"]
        if type(more) is not bool:
            raise ValueError()
        cursor = info.get("endCursor") if more else None
        if more and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 4096):
            raise ValueError()
        return nodes, cursor
    except (KeyError, TypeError, ValueError):
        raise ShopifyError("commerce_incomplete_source") from None


class MeasurementClient(ShopifyClient):
    def measurement_orders(
        self,
        shop: str,
        token: str,
        cursor: str | None,
        query: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        result = self._query(shop, token, queries.ORDERS, {"after": cursor, "query": query})
        return connection_page(result.get("orders"))

    def agreements(self, shop: str, token: str, order_id: str) -> list[dict[str, Any]]:
        order_id = gid(order_id)
        result: list[dict[str, Any]] = []
        cursor = None
        seen: set[str] = set()
        requests = 0
        while True:
            response = self._query(
                shop, token, queries.AGREEMENTS, {"id": order_id, "after": cursor}
            )
            nodes, after = connection_page((response.get("order") or {}).get("agreements"))
            requests += 1
            for agreement in nodes:
                agreement_id = gid(agreement["id"])
                sales, sale_cursor = connection_page(agreement["sales"])
                sales_seen: set[str] = set()
                while sale_cursor:
                    if requests >= 50 or sale_cursor in sales_seen:
                        raise ShopifyError("commerce_source_page_limit")
                    sales_seen.add(sale_cursor)
                    response = self._query(
                        shop,
                        token,
                        queries.SALES,
                        {
                            "order": order_id,
                            "agreementBefore": cursor,
                            "after": sale_cursor,
                        },
                    )
                    matches = (response.get("order") or {}).get("agreements", {}).get("nodes", [])
                    if len(matches) != 1 or matches[0].get("id") != agreement_id:
                        raise ShopifyError("commerce_incomplete_source")
                    extra, sale_cursor = connection_page(matches[0].get("sales"))
                    sales.extend(extra)
                    requests += 1
                result.append(
                    {"id": agreement_id, "happenedAt": agreement["happenedAt"], "sales": sales}
                )
            if after is None:
                return result
            if requests >= 50 or after in seen:
                raise ShopifyError("commerce_source_page_limit")
            seen.add(after)
            cursor = after
