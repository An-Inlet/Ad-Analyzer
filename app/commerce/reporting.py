from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.ledger import DEFINITION, lock_store, retention_floor
from app.commerce.models import CommerceEntry, CommerceOrder, CommerceSnapshot, CommerceSuppression
from app.shopify.security import utc


class MeasurementWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: date
    end: date  # exclusive; never infer cumulative from monthly wording
    time_basis: Literal["calendar_month", "cumulative"]
    currency: str
    time_zone: str

    @model_validator(mode="after")
    def valid_window(self) -> "MeasurementWindow":
        try:
            ZoneInfo(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("invalid time zone") from None
        if self.start >= self.end or (self.end - self.start).days > 400:
            raise ValueError("invalid measurement interval")
        if self.time_basis == "calendar_month":
            next_month = (self.start.replace(day=28) + timedelta(days=4)).replace(day=1)
            if self.start.day != 1 or self.end != next_month:
                raise ValueError("calendar_month requires exactly one local calendar month")
        return self


def measurement(
    session: Session,
    workspace_id: int,
    store_id: str,
    window: MeasurementWindow,
    *,
    now: datetime | None = None,
    snapshot: bool = False,
) -> dict[str, Any]:
    now = utc(now or datetime.now(UTC))
    store = lock_store(session, store_id, workspace_id)
    if window.currency != store.currency or window.time_zone != store.time_zone:
        raise ValueError("measurement basis does not match verified store")
    zone = ZoneInfo(window.time_zone)
    start = datetime.combine(window.start, time.min, zone).astimezone(UTC)
    end = datetime.combine(window.end, time.min, zone).astimezone(UTC)
    reasons = []
    if start < retention_floor(now, store.time_zone):
        reasons.append("outside_retention")
    if store.covered_from is None or utc(store.covered_from) > start:
        reasons.append("missing_history")
    if store.last_sync_at is None or utc(store.last_sync_at) < end:
        reasons.append("incomplete_window")
    if store.last_sync_at is None or not timedelta(0) <= now - utc(store.last_sync_at) <= timedelta(
        hours=24
    ):
        reasons.append("stale_source")
    if store.window_end is not None:
        reasons.append("import_in_progress")
    if store.error_code:
        reasons.append("source_error")
    if (
        session.scalar(
            select(CommerceOrder.order_key)
            .where(
                CommerceOrder.store_id == store.id,
                CommerceOrder.quality != "complete",
            )
            .limit(1)
        )
        is not None
    ):
        reasons.append("unreconciled_source")
    if (
        session.scalar(
            select(CommerceSuppression.object_key)
            .where(
                CommerceSuppression.workspace_id == store.workspace_id,
                CommerceSuppression.shop_key == store.shop_key,
            )
            .limit(1)
        )
        is not None
    ):
        reasons.append("privacy_suppressed_source")
    from app.shopify.privacy_identity import markers

    if markers(session, store) and "privacy_suppressed_source" not in reasons:
        reasons.append("privacy_suppressed_source")
    entries = list(
        session.scalars(
            select(CommerceEntry).where(
                CommerceEntry.store_id == store.id,
                CommerceEntry.happened_at >= start,
                CommerceEntry.happened_at < end,
            )
        )
    )
    amount = sum(e.net_micros for e in entries)
    orders = list(
        session.scalars(
            select(CommerceOrder).where(
                CommerceOrder.store_id == store.id,
                CommerceOrder.created_at >= start,
                CommerceOrder.created_at < end,
            )
        )
    )
    customer_keys = {o.customer_key for o in orders if o.customer_key is not None}
    unknown = sum(o.customer_key is None for o in orders)
    result: dict[str, Any] = {
        "source": "shopify",
        "store_id": store.id,
        "definition": DEFINITION,
        "currency": store.currency,
        "time_zone": store.time_zone,
        "window": window.model_dump(mode="json"),
        "as_of": now.isoformat(),
        "source_watermark": utc(store.last_sync_at).isoformat() if store.last_sync_at else None,
        "revision": store.revision,
        "quality": "complete" if not reasons else "unavailable",
        "reasons": reasons,
        "net_sales_micros": amount if not reasons else None,
        "observed_net_sales_micros": amount if "outside_retention" not in reasons else None,
        "orders": len(orders) if not reasons else None,
        "distinct_customers": len(customer_keys) if not reasons and not unknown else None,
        "known_distinct_customers": len(customer_keys) if not reasons else None,
        "orders_without_customer_identity": unknown if not reasons else None,
        "customer_quality": "unavailable" if reasons or unknown else "complete",
    }
    if snapshot:
        identifier = uuid4().hex
        session.add(
            CommerceSnapshot(
                id=identifier,
                store_id=store.id,
                starts_at=start,
                ends_at=end,
                as_of=now,
                revision=store.revision,
                result=result,
            )
        )
        session.flush()
        result = {**result, "snapshot_id": identifier}
    return result
