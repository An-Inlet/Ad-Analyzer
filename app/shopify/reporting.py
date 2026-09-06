"""Store order cohorts, kept separate from advertising attribution and CRM outcomes."""

from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.shopify.models import ShopifyConnection, ShopifyOrder
from app.shopify.security import utc


def totals(rows: list[ShopifyOrder]) -> dict[str, Any]:
    paid = [o for o in rows if o.net_collected_micros + o.refunded_micros > 0]
    net = sum(o.net_collected_micros for o in rows)
    refunds = sum(o.refunded_micros for o in rows)
    new = sum(o.customer_order_index == 1 for o in paid)
    returning = sum((o.customer_order_index or 0) > 1 for o in paid)
    return {
        "orders": len(rows),
        "paid_orders": len(paid),
        "net_collected_micros": net,
        "refunded_micros": refunds,
        "captured_micros": net + refunds,
        "refund_ratio": refunds / (net + refunds) if net + refunds > 0 else None,
        "average_net_per_paid_order_micros": net // len(paid) if paid else None,
        "cancelled_orders": sum(o.cancelled for o in rows),
        "first_orders": new,
        "returning_orders": returning,
        "unknown_orders": len(paid) - new - returning,
        "returning_order_share": returning / (new + returning) if new + returning else None,
    }


def sales_report(
    session: Session, workspace_id: int, *, now: datetime | None = None
) -> dict[str, Any]:
    now = utc(now or datetime.now(UTC))
    row = session.scalar(
        select(ShopifyConnection).where(ShopifyConnection.workspace_id == workspace_id)
    )
    if row is None:
        return {"connected": False, "ready": False, "suggestions": [], "warnings": []}
    zone = ZoneInfo(row.time_zone)
    end = datetime.combine(now.astimezone(zone).date(), time.min, zone).astimezone(UTC)
    start = datetime.combine(
        end.astimezone(zone).date() - timedelta(days=28), time.min, zone
    ).astimezone(UTC)
    previous_start = datetime.combine(
        start.astimezone(zone).date() - timedelta(days=28), time.min, zone
    ).astimezone(UTC)
    orders = list(
        session.scalars(
            select(ShopifyOrder).where(
                ShopifyOrder.connection_id == row.id,
                ShopifyOrder.workspace_id == workspace_id,
                ShopifyOrder.created_at >= previous_start,
                ShopifyOrder.created_at < end,
            )
        )
    )
    current = [
        o for o in orders if utc(o.created_at) >= start and o.currency_code == row.currency_code
    ]
    previous = [
        o for o in orders if utc(o.created_at) < start and o.currency_code == row.currency_code
    ]
    warnings = []
    fresh = bool(
        row.last_sync_at and timedelta(0) <= now - utc(row.last_sync_at) <= timedelta(hours=24)
    )
    covered = bool(row.covered_from and utc(row.covered_from) <= start)
    ready = (
        fresh
        and covered
        and row.window_end is None
        and row.status == "connected"
        and not row.error_code
    )
    if not fresh:
        warnings.append(
            "Complete a sales sync: the latest complete import is missing or "
            "more than 24 hours old."
        )
    if row.window_end:
        warnings.append("An import is still in progress. Figures may change as more pages arrive.")
    if not covered:
        warnings.append("The full current period is not covered by the import.")
    if row.status != "connected" or row.error_code:
        warnings.append(
            "The latest import needs attention. Reconnect if access has "
            "expired, or retry after the displayed delay."
        )
    if any(o.currency_code != row.currency_code for o in orders):
        warnings.append(
            "Orders in a different store currency are excluded; no currency conversion is applied."
        )
        ready = False
    metrics, old = totals(current), totals(previous)
    previous_complete = ready and bool(row.covered_from and utc(row.covered_from) <= previous_start)
    if not previous_complete:
        warnings.append("A complete previous period is unavailable; period change is withheld.")
    products: dict[str, dict[str, Any]] = {}
    channels: dict[str, list[ShopifyOrder]] = defaultdict(list)
    campaign_rows = list(
        session.execute(
            select(Campaign, AdvertisingAccount)
            .join(AdvertisingAccount, Campaign.account_id == AdvertisingAccount.id)
            .where(AdvertisingAccount.workspace_id == workspace_id)
        )
    )
    owned = {c.id: c for c, _a in campaign_rows}
    campaign_orders: dict[int, list[ShopifyOrder]] = defaultdict(list)
    for order in current:
        channels[order.channel].append(order)
        if order.campaign_id is not None and order.campaign_id in owned:
            campaign_orders[order.campaign_id].append(order)
        if order.products_complete:
            for product in order.products:
                key = product["product_id"]
                result = products.setdefault(
                    key,
                    {
                        "title": product["title"],
                        "ordered_units": 0,
                        "retained_units": 0,
                        "gross_ordered_micros": 0,
                    },
                )
                for field in ("ordered_units", "retained_units", "gross_ordered_micros"):
                    result[field] += product[field]
    incomplete_products = sum(not o.products_complete for o in current)
    if incomplete_products:
        warnings.append(
            f"Product breakdown excludes {incomplete_products} orders with more than "
            "10 line items; their order totals are included."
        )
    ads = list(
        session.scalars(
            select(DailyMetric)
            .join(Campaign, DailyMetric.campaign_id == Campaign.id)
            .join(AdvertisingAccount, Campaign.account_id == AdvertisingAccount.id)
            .where(
                AdvertisingAccount.workspace_id == workspace_id,
                DailyMetric.entity_type == "campaign",
                DailyMetric.metric_date >= start.astimezone(zone).date(),
                DailyMetric.metric_date < end.astimezone(zone).date(),
            )
        )
    )
    spend: dict[int, int] = defaultdict(int)
    for metric in ads:
        spend[metric.campaign_id] += metric.cost_micros
    account_by_id = {a.id: a for _c, a in campaign_rows}
    contributing_accounts = {owned[m.campaign_id].account_id for m in ads}
    compatible = bool(ads) and all(
        account_by_id[i].currency_code == row.currency_code
        and account_by_id[i].time_zone == row.time_zone
        for i in contributing_accounts
    )
    # Every imported campaign needs daily coverage, including zero-spend days.
    # Missing dates are never silently treated as zero spend.
    campaign_days: dict[int, set[Any]] = defaultdict(set)
    for m in ads:
        campaign_days[m.campaign_id].add(m.metric_date)
    complete_ads = bool(owned) and all(len(campaign_days[i]) == 28 for i in owned)
    if not compatible or not complete_ads:
        warnings.append(
            "Sales-to-spend ratios need 28 complete ad-data days for each campaign in the same "
            "currency and time zone as the store."
        )
    comparison_ready = ready and compatible and complete_ads
    ad_spend = sum(spend.values()) if compatible else None
    matched = sum(len(v) for v in campaign_orders.values())
    suggestions = []
    if ready and metrics["paid_orders"] >= 20:
        if (metrics["refund_ratio"] or 0) > 0.10:
            suggestions.append(
                "Review the reasons for refunds before increasing acquisition "
                "spend. Refunds exceed 10% of captured value in this order cohort."
            )
        if metrics["orders"] and matched / metrics["orders"] < 0.5:
            suggestions.append(
                "Improve campaign tagging before reallocating budget from these "
                "sales figures. Fewer than half of orders match an imported "
                "advertising campaign."
            )
        if products:
            suggestions.append(
                "Use the leading products below to plan creative tests and "
                "upcoming promotions; check margin and inventory before choosing "
                "an offer."
            )
    elif not ready:
        suggestions.append(
            "Finish or refresh the import before using sales figures for a budget decision."
        )
    else:
        suggestions.append(
            "Collect more paid orders before drawing sales-performance "
            "conclusions; these totals remain useful for monitoring."
        )
    return {
        "connected": True,
        "ready": ready,
        "shop_name": row.shop_name,
        "shop_domain": row.shop_domain,
        "status": row.status,
        "currency_code": row.currency_code,
        "time_zone": row.time_zone,
        "last_sync_at": utc(row.last_sync_at).isoformat() if row.last_sync_at else None,
        "next_attempt_at": utc(row.next_attempt_at).isoformat() if row.next_attempt_at else None,
        "import_in_progress": row.window_end is not None,
        "window": {
            "start": start.astimezone(zone).date().isoformat(),
            "end": (end.astimezone(zone).date() - timedelta(days=1)).isoformat(),
        },
        "previous_window": {
            "start": previous_start.astimezone(zone).date().isoformat(),
            "end": (start.astimezone(zone).date() - timedelta(days=1)).isoformat(),
        },
        "current": metrics,
        "previous": old,
        "previous_complete": previous_complete,
        "net_change_ratio": (metrics["net_collected_micros"] - old["net_collected_micros"])
        / old["net_collected_micros"]
        if previous_complete and old["net_collected_micros"] > 0
        else None,
        "products": sorted(products.values(), key=lambda p: (-p["ordered_units"], p["title"]))[:20],
        "channels": [
            {"channel": name, **totals(values)} for name, values in sorted(channels.items())
        ],
        "matched_orders": matched,
        "tag_coverage": matched / len(current) if current else None,
        "campaigns": [
            {
                "name": owned[cid].name,
                **totals(values),
                "spend_micros": spend.get(cid) if comparison_ready else None,
                "tagged_sales_to_spend": sum(o.net_collected_micros for o in values) / spend[cid]
                if comparison_ready and spend.get(cid, 0) > 0
                else None,
            }
            for cid, values in campaign_orders.items()
        ],
        "ad_spend_micros": ad_spend if comparison_ready else None,
        "blended_sales_to_spend": metrics["net_collected_micros"] / ad_spend
        if comparison_ready and ad_spend
        else None,
        "suggestions": suggestions,
        "warnings": warnings,
        "basis": "Order-date cohorts over 28 completed store-local days. Net "
        "collected is captured payments minus refunds, including tax and "
        "shipping. Refunds are assigned to the original order cohort, not "
        "the refund date. This is neither accounting net sales nor profit.",
        "attribution_basis": "Campaign matching requires a recognized last-visit UTM source and"
        " a numeric utm_campaign matching an imported campaign in this "
        "workspace. All unmatched orders remain in store totals. Tags and "
        "blended sales-to-spend ratios do not establish ad causation or "
        "incremental ROAS.",
    }
