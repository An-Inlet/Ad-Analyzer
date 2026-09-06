import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign
from app.shopify.models import ShopifyConnection
from app.shopify.security import ShopifyError, Vault, utc

CHANNELS = {
    "google": "google",
    "facebook": "meta",
    "instagram": "meta",
    "meta": "meta",
    "tiktok": "tiktok",
    "email": "email",
    "newsletter": "email",
    "bing": "microsoft",
}
PLATFORMS = {"google": AdvertisingPlatform.GOOGLE_ADS, "meta": AdvertisingPlatform.META_ADS}


def resource_id(value: Any, kind: str) -> str:
    normalized = str(value)
    normalized = normalized.removeprefix(f"gid://shopify/{kind}/")
    if not re.fullmatch(r"[0-9]{1,24}", normalized):
        raise ShopifyError("shopify_invalid_resource")
    return normalized


def order_key(vault: Vault, connection: ShopifyConnection, value: Any) -> str:
    return vault.digest(
        f"order:{connection.workspace_id}:{connection.shop_domain}", resource_id(value, "Order")
    )


def money(value: Any, currency: str, *, signed: bool = False) -> int:
    try:
        amount = Decimal(str(value["shopMoney"]["amount"])) * 1_000_000
        if value["shopMoney"]["currencyCode"] != currency:
            raise ShopifyError("shopify_currency_mismatch")
        minimum = -9_000_000_000_000_000 if signed else 0
        if (
            not amount.is_finite()
            or not minimum <= amount <= 9_000_000_000_000_000
            or amount != amount.to_integral_value()
        ):
            raise ValueError("amount")
        return int(amount)
    except (KeyError, ValueError, TypeError, InvalidOperation):
        raise ShopifyError("shopify_invalid_money") from None


def integer(value: Any, *, maximum: int = 100_000_000) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum:
        raise ShopifyError("shopify_invalid_quantity")
    return value


def normalized_order(
    session: Session, row: ShopifyConnection, data: dict[str, Any], vault: Vault
) -> dict[str, Any]:
    try:
        created = utc(datetime.fromisoformat(str(data["createdAt"]).replace("Z", "+00:00")))
        updated = utc(datetime.fromisoformat(str(data["updatedAt"]).replace("Z", "+00:00")))
        if updated < created or not isinstance(data["test"], bool):
            raise ValueError("dates")
        journey = data.get("customerJourneySummary") or {}
        ready = journey.get("ready") is True
        ordinal = journey.get("customerOrderIndex") if ready else None
        if ordinal is not None:
            ordinal = integer(ordinal)
        visit = journey.get("lastVisit") or {} if ready else {}
        tags = visit.get("utmParameters") or {}
        channel = CHANNELS.get(str(tags.get("source", "")).lower(), "unknown")
        candidate = str(tags.get("campaign", ""))
        campaign_id = None
        if channel in PLATFORMS and re.fullmatch(r"[0-9]{1,24}", candidate):
            matches = list(
                session.scalars(
                    select(Campaign.id)
                    .join(AdvertisingAccount)
                    .where(
                        AdvertisingAccount.workspace_id == row.workspace_id,
                        Campaign.platform == PLATFORMS[channel],
                        Campaign.external_campaign_id == candidate,
                    )
                )
            )
            if len(matches) == 1:
                campaign_id = matches[0]
        lines = data["lineItems"]
        complete = lines["pageInfo"]["hasNextPage"] is False
        products = []
        if complete:
            if not isinstance(lines["nodes"], list) or len(lines["nodes"]) > 10:
                raise ValueError("lines")
            for line in lines["nodes"]:
                variant = line.get("variant") or {}
                product = variant.get("product") or {}
                quantity = integer(line["quantity"])
                current = integer(line["currentQuantity"])
                unit = money(line["originalUnitPriceSet"], row.currency_code)
                if unit * quantity > 9_000_000_000_000_000:
                    raise ValueError("value")
                products.append(
                    {
                        "product_id": resource_id(product["id"], "Product")
                        if product
                        else "unavailable",
                        "title": str(product.get("title", "Unavailable product"))[:240],
                        "ordered_units": quantity,
                        "retained_units": current,
                        "gross_ordered_micros": unit * quantity,
                    }
                )
        return {
            "order_key": order_key(vault, row, data["id"]),
            "created_at": created,
            "source_updated_at": updated,
            "currency_code": row.currency_code,
            "net_collected_micros": money(data["netPaymentSet"], row.currency_code, signed=True),
            "refunded_micros": money(data["totalRefundedSet"], row.currency_code),
            "cancelled": data.get("cancelledAt") is not None,
            "customer_order_index": ordinal,
            "channel": channel,
            "campaign_id": campaign_id,
            "products_complete": complete,
            "products": products,
        }
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        raise ShopifyError("shopify_invalid_order") from None
