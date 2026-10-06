"""Measurement retention and erasure; callers hold native/store locks and commit."""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.commerce.ledger import identity_key, retention_floor, revise_days
from app.commerce.models import (
    CommerceDailyRevision,
    CommerceEntry,
    CommerceOrder,
    CommerceSnapshot,
    CommerceSourceLink,
    CommerceStore,
    CommerceSuppression,
)
from app.settings import Settings
from app.shopify.models import ShopifyConnection, ShopifyOrder
from app.shopify.security import ShopifyError, Vault, utc


def store_for_update(session: Session, store_id: str | None) -> CommerceStore | None:
    if store_id is None:
        return None
    from app.commerce.evidence import lock_workspace

    owner = session.scalar(select(CommerceStore.workspace_id).where(CommerceStore.id == store_id))
    if owner is None:
        return None
    lock_workspace(session, owner)
    return session.scalar(
        select(CommerceStore).where(CommerceStore.id == store_id).with_for_update()
    )


def delete_orders(session: Session, store: CommerceStore, keys: list[str]) -> None:
    for offset in range(0, len(keys), 500):
        batch = keys[offset : offset + 500]
        for model in (CommerceSourceLink, CommerceEntry, CommerceOrder):
            session.execute(
                delete(model).where(model.store_id == store.id, model.order_key.in_(batch))
            )


def suppress(session: Session, store: CommerceStore, kind: str, key: str) -> None:
    identity = (store.workspace_id, store.shop_key, kind, key)
    if session.get(CommerceSuppression, identity) is None:
        session.add(
            CommerceSuppression(
                workspace_id=store.workspace_id, shop_key=store.shop_key, kind=kind, object_key=key
            )
        )
        session.flush()


def remove_store(session: Session, store_id: str | None) -> None:
    store = store_for_update(session, store_id)
    if store is None:
        return
    from app.commerce.evidence import invalidate

    invalidate(session, store, datetime.now(UTC))
    # Disconnect has always promised local deletion, including retained measurement facts.
    for model in (
        CommerceSourceLink,
        CommerceEntry,
        CommerceOrder,
        CommerceDailyRevision,
        CommerceSnapshot,
    ):
        session.execute(delete(model).where(model.store_id == store.id))
    store.status, store.covered_from, store.last_sync_at = "revoked", None, None
    store.window_start, store.window_end, store.cursor = None, None, None
    store.revision += 1


def event_keys(
    session: Session,
    store: CommerceStore,
    payload: dict[str, Any],
    topic: str,
    configuration: Settings,
) -> tuple[list[str], str | None]:
    ids = (
        [payload["id"]]
        if topic == "orders/delete"
        else payload[
            "orders_requested" if topic == "customers/data_request" else "orders_to_redact"
        ]
    )
    if not isinstance(ids, list) or len(ids) > 100_000:
        raise ShopifyError("shopify_invalid_event")
    vault = Vault(configuration)
    keys = {identity_key(vault, store, "order", value) for value in ids}
    customer = payload.get("customer")
    customer_key = (
        identity_key(vault, store, "customer", customer["id"])
        if customer and customer.get("id") is not None
        else None
    )
    if customer_key:
        keys.update(
            session.scalars(
                select(CommerceOrder.order_key).where(
                    CommerceOrder.store_id == store.id, CommerceOrder.customer_key == customer_key
                )
            )
        )
    return sorted(keys), customer_key


def process_measurement_event(
    session: Session,
    store: CommerceStore,
    topic: str,
    payload: dict[str, Any],
    configuration: Settings,
    published_at: datetime,
) -> list[str]:
    if topic in {"app/uninstalled", "shop/redact"}:
        if utc(published_at) >= utc(store.connected_at):
            if topic == "shop/redact":
                for key in session.scalars(
                    select(CommerceOrder.order_key).where(CommerceOrder.store_id == store.id)
                ):
                    suppress(session, store, "order", key)
            remove_store(session, store.id)
        return []
    keys, customer_key = event_keys(session, store, payload, topic, configuration)
    if topic == "customers/data_request":
        return keys
    for key in keys:
        suppress(session, store, "order", key)
    if customer_key:
        suppress(session, store, "customer", customer_key)
    for offset in range(0, len(keys), 500):
        batch = keys[offset : offset + 500]
        old_keys = list(
            session.scalars(
                select(CommerceOrder.privacy_key).where(
                    CommerceOrder.store_id == store.id,
                    CommerceOrder.order_key.in_(batch),
                )
            )
        )
        session.execute(
            delete(ShopifyOrder).where(
                ShopifyOrder.workspace_id == store.workspace_id,
                or_(
                    ShopifyOrder.commerce_order_key.in_(batch), ShopifyOrder.order_key.in_(old_keys)
                ),
            )
        )
    session.execute(
        update(ShopifyConnection)
        .where(
            ShopifyConnection.commerce_store_id == store.id,
        )
        .values(
            error_code="shopify_privacy_reconciliation_required",
            last_sync_at=None,
            covered_from=None,
        )
    )
    from app.commerce.evidence import invalidate

    invalidate(session, store, datetime.now(UTC))
    delete_orders(session, store, keys)
    # As-of artifacts cannot retain erased individuals, even indirectly in aggregates.
    session.execute(delete(CommerceSnapshot).where(CommerceSnapshot.store_id == store.id))
    session.execute(delete(CommerceDailyRevision).where(CommerceDailyRevision.store_id == store.id))
    days = {
        utc(value).astimezone(ZoneInfo(store.time_zone)).date()
        for value in session.scalars(
            select(CommerceEntry.happened_at).where(CommerceEntry.store_id == store.id)
        )
    }
    revise_days(session, store, days, datetime.now(UTC))
    return keys


def purge_measurements(session: Session, now: datetime, *, workspace_id: int | None = None) -> None:
    from app.commerce.evidence import invalidate, lock_workspace

    owner_query = select(CommerceStore.workspace_id).distinct().order_by(CommerceStore.workspace_id)
    if workspace_id is not None:
        owner_query = owner_query.where(CommerceStore.workspace_id == workspace_id)
    owners = list(session.scalars(owner_query))
    for owner in owners:
        lock_workspace(session, owner)
    # Native locks precede all stores, matching authenticated privacy events.
    list(
        session.scalars(
            select(ShopifyConnection)
            .where(ShopifyConnection.workspace_id.in_(owners))
            .order_by(ShopifyConnection.workspace_id)
            .with_for_update()
        )
    )
    for store in session.scalars(
        select(CommerceStore)
        .where(CommerceStore.workspace_id.in_(owners))
        .order_by(CommerceStore.workspace_id, CommerceStore.id)
        .with_for_update()
    ):
        floor = retention_floor(now, store.time_zone)
        expiring = any(
            session.scalar(query.limit(1)) is not None
            for query in (
                select(CommerceEntry.entry_key).where(
                    CommerceEntry.store_id == store.id, CommerceEntry.happened_at < floor
                ),
                select(CommerceSnapshot.id).where(
                    CommerceSnapshot.store_id == store.id, CommerceSnapshot.starts_at < floor
                ),
                select(CommerceOrder.order_key).where(
                    CommerceOrder.store_id == store.id,
                    CommerceOrder.created_at < floor,
                    CommerceOrder.source_updated_at < floor,
                ),
                select(CommerceDailyRevision.store_id).where(
                    CommerceDailyRevision.store_id == store.id,
                    CommerceDailyRevision.day < floor.astimezone(ZoneInfo(store.time_zone)).date(),
                ),
            )
        )
        session.execute(
            delete(CommerceEntry).where(
                CommerceEntry.store_id == store.id, CommerceEntry.happened_at < floor
            )
        )
        from app.commerce.models import CommerceMeasurementPublication

        if expiring or (
            session.scalar(
                select(CommerceMeasurementPublication.id)
                .where(
                    CommerceMeasurementPublication.store_id == store.id,
                    CommerceMeasurementPublication.earliest_source_day
                    < floor.astimezone(ZoneInfo(store.time_zone)).date(),
                )
                .limit(1)
            )
            is not None
        ):
            invalidate(session, store, now, clear_history=False)
        local_floor = floor.astimezone(ZoneInfo(store.time_zone)).date()
        session.execute(
            delete(CommerceDailyRevision).where(
                CommerceDailyRevision.store_id == store.id, CommerceDailyRevision.day < local_floor
            )
        )
        session.execute(
            delete(CommerceSnapshot).where(
                CommerceSnapshot.store_id == store.id, CommerceSnapshot.starts_at < floor
            )
        )
        old_keys = list(
            session.scalars(
                select(CommerceOrder.order_key).where(
                    CommerceOrder.store_id == store.id,
                    CommerceOrder.created_at < floor,
                    CommerceOrder.source_updated_at < floor,
                    ~select(CommerceEntry.entry_key)
                    .where(
                        CommerceEntry.store_id == CommerceOrder.store_id,
                        CommerceEntry.order_key == CommerceOrder.order_key,
                    )
                    .exists(),
                )
            )
        )
        delete_orders(session, store, old_keys)
