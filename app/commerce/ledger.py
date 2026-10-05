"""Canonical identities and revisioned Shopify merchandise facts; callers own transactions."""

import calendar
import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.commerce.models import (
    CommerceDailyRevision,
    CommerceEntry,
    CommerceOrder,
    CommerceShopAlias,
    CommerceSourceLink,
    CommerceStore,
    CommerceSuppression,
)
from app.commerce.source import gid
from app.settings import Settings
from app.shopify.models import ShopifyConnection
from app.shopify.normalize import money, order_key, resource_id
from app.shopify.security import ShopifyError, Vault, utc
from app.workspaces.models import Workspace, WorkspaceIntegration

DEFINITION = "shopify_merchandise_net_sales_v1"
MEASUREMENT_SCOPES = frozenset(
    {"read_orders", "read_products", "read_all_orders", "read_customers"}
)


def retention_floor(now: datetime, zone: str = "UTC") -> datetime:
    local = utc(now).astimezone(ZoneInfo(zone))
    month_index = local.year * 12 + local.month - 1 - 13
    year, month = divmod(month_index, 12)
    day = min(local.day, calendar.monthrange(year, month + 1)[1])
    return datetime(year, month + 1, day, tzinfo=ZoneInfo(zone)).astimezone(UTC)


def identity_key(vault: Vault, store: CommerceStore, kind: str, source_id: object) -> str:
    expected = {"order": "Order", "customer": "Customer"}.get(kind)
    value = resource_id(source_id, expected) if expected else gid(source_id)
    return vault.digest(f"commerce:{store.workspace_id}:{store.shop_key}:{kind}", value)


def lock_store(session: Session, store_id: str, workspace_id: int) -> CommerceStore:
    store = session.scalar(
        select(CommerceStore)
        .where(
            CommerceStore.id == store_id,
            CommerceStore.workspace_id == workspace_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    workspace = session.get(Workspace, workspace_id)
    connection = session.get(WorkspaceIntegration, store.connection_id) if store else None
    if (
        store is None
        or store.status != "active"
        or workspace is None
        or workspace.status != "active"
        or connection is None
        or connection.status != "active"
        or connection.workspace_id != workspace_id
        or connection.provider != "shopify"
    ):
        raise ShopifyError("commerce_ownership_unavailable")
    return store


def legacy_store(session: Session, row: ShopifyConnection) -> CommerceStore | None:
    from app.shopify.models import ShopifyPrivacyIdentity

    if (
        session.scalar(
            select(ShopifyPrivacyIdentity.object_key)
            .where(
                ShopifyPrivacyIdentity.workspace_id == row.workspace_id,
                ShopifyPrivacyIdentity.shop_domain == row.shop_domain,
                or_(
                    ShopifyPrivacyIdentity.pending_legacy.is_(True),
                    ShopifyPrivacyIdentity.kind.in_(["customer", "unresolved"]),
                ),
            )
            .limit(1)
        )
        is not None
    ):
        raise ShopifyError("shopify_privacy_reconciliation_required")
    if row.commerce_store_id is None:
        return None
    store = lock_store(session, row.commerce_store_id, row.workspace_id)
    from app.shopify.privacy_identity import markers

    if markers(session, store):
        raise ShopifyError("shopify_privacy_reconciliation_required")
    if store.connection_id != row.workspace_integration_id:
        raise ShopifyError("commerce_ownership_unavailable")
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
        # The legacy query has no customer identity, so cannot safely reconcile
        # customer erasure on its own. Never replay suppressed data through it.
        raise ShopifyError("shopify_privacy_reconciliation_required")
    return store


def bind_store(
    session: Session,
    row: ShopifyConnection,
    shop_id: object,
    configuration: Settings,
    now: datetime,
) -> CommerceStore:
    from app.shopify.privacy_identity import preserve

    preserve(session, row)
    vault = Vault(configuration)
    key = vault.digest("commerce_shop", resource_id(shop_id, "Shop"))
    store = session.scalar(
        select(CommerceStore)
        .where(
            CommerceStore.workspace_id == row.workspace_id,
            CommerceStore.shop_key == key,
        )
        .with_for_update()
    )
    if row.workspace_integration_id is None:
        raise ShopifyError("commerce_ownership_unavailable")
    if store is None:
        store = CommerceStore(
            id=uuid4().hex,
            workspace_id=row.workspace_id,
            shop_key=key,
            shop_domain=row.shop_domain,
            connection_id=row.workspace_integration_id,
            currency=row.currency_code,
            time_zone=row.time_zone,
            connected_at=now,
        )
        session.add(store)
        session.flush()
    elif store.currency != row.currency_code or store.time_zone != row.time_zone:
        # Never silently reinterpret historical amounts or local calendar boundaries.
        raise ShopifyError("commerce_measurement_basis_changed")
    for domain in {store.shop_domain, row.shop_domain}:
        if session.get(CommerceShopAlias, (domain, store.id)) is None:
            session.add(CommerceShopAlias(shop_domain=domain, store_id=store.id))
    store.shop_domain, store.connection_id = row.shop_domain, row.workspace_integration_id
    store.status, store.connected_at = "active", now
    store.window_start, store.window_end, store.cursor = None, None, None
    store.next_attempt_at, store.error_code = None, None
    store.last_sync_at = None  # Reconnect must reconcile before reporting current completeness.
    row.commerce_store_id = store.id
    return store


def timestamp(value: object) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return utc(result)
    except (ValueError, TypeError):
        raise ShopifyError("commerce_invalid_timestamp") from None


def normalized_entries(
    agreements: list[dict[str, Any]],
    store: CommerceStore,
    vault: Vault,
) -> tuple[dict[str, dict[str, Any]], str]:
    entries: dict[str, dict[str, Any]] = {}
    quality = "complete" if agreements else "unavailable"
    excluded = {"SHIPPING", "DUTY", "FEE", "ADDITIONAL_FEE", "TIP", "GIFT_CARD"}
    supported = {
        "OrderAgreement": ("ORDER", {"ORDER"}),
        "OrderEditAgreement": ("ORDER_EDIT", {"ORDER", "UPDATE"}),
        "RefundAgreement": ("REFUND", {"RETURN"}),
    }
    for agreement in agreements:
        basis = supported.get(str(agreement.get("__typename")))
        if basis is None or agreement.get("reason") != basis[0]:
            # Return/exchange intent can reverse sales before refund processing.
            quality = "unreconciled"
            continue
        if agreement["__typename"] == "RefundAgreement":
            processed = (agreement.get("refund") or {}).get("processedAt")
            if not processed:
                quality = "unreconciled"
                continue
            happened = timestamp(processed)
        else:
            happened = timestamp(agreement["happenedAt"])
        for sale in agreement["sales"]:
            if sale["lineType"] in excluded:
                continue
            if sale["lineType"] != "PRODUCT" or sale["actionType"] not in basis[1]:
                quality = "unreconciled"
                continue
            gross = money(sale["totalAmount"], store.currency, signed=True)
            tax = money(sale["totalTaxAmount"], store.currency, signed=True)
            if gross * tax < 0 or abs(tax) > abs(gross):
                quality = "unreconciled"
                continue
            amount = gross - tax
            if sale["actionType"] == "RETURN":
                amount = -abs(amount)
            elif sale["actionType"] == "ORDER" and amount < 0:
                quality = "unreconciled"
                continue
            key = identity_key(vault, store, "sale", sale["id"])
            value = {
                "happened_at": happened,
                "currency": store.currency,
                "net_micros": amount,
                "action": sale["actionType"],
            }
            if key in entries and entries[key] != value:
                raise ShopifyError("commerce_conflicting_sale")
            entries[key] = value
    return entries, quality


def revise_days(session: Session, store: CommerceStore, days: set[date], now: datetime) -> None:
    store.revision += 1
    session.flush()
    zone = ZoneInfo(store.time_zone)
    all_entries = list(
        session.scalars(select(CommerceEntry).where(CommerceEntry.store_id == store.id))
    )
    for day in sorted(days):
        amount = sum(
            e.net_micros for e in all_entries if utc(e.happened_at).astimezone(zone).date() == day
        )
        session.add(
            CommerceDailyRevision(
                store_id=store.id,
                day=day,
                revision=store.revision,
                currency=store.currency,
                time_zone=store.time_zone,
                net_micros=amount,
                as_of=now,
            )
        )


def apply_order(
    session: Session,
    store: CommerceStore,
    row: ShopifyConnection,
    source: dict[str, Any],
    agreements: list[dict[str, Any]],
    configuration: Settings,
    now: datetime,
) -> bool:
    store = lock_store(session, store.id, row.workspace_id)
    if row.commerce_store_id != store.id or row.workspace_integration_id != store.connection_id:
        raise ShopifyError("commerce_ownership_unavailable")
    vault = Vault(configuration)
    key = identity_key(vault, store, "order", source["id"])
    customer = source.get("customer")
    customer_key = identity_key(vault, store, "customer", customer["id"]) if customer else None
    from app.commerce.privacy import process_measurement_event
    from app.shopify.privacy_identity import prepare_source

    erased, unresolved = prepare_source(session, row, store, source, key, configuration)
    for kind, object_key in [("order", key), ("customer", customer_key)]:
        if object_key and session.get(
            CommerceSuppression, (store.workspace_id, store.shop_key, kind, object_key)
        ):
            erased = True
    if erased:
        process_measurement_event(
            session, store, "orders/delete", {"id": source["id"]}, configuration, now
        )
        return False
    if unresolved or (
        customer_key is None
        and session.scalar(
            select(CommerceSuppression.object_key)
            .where(
                CommerceSuppression.workspace_id == store.workspace_id,
                CommerceSuppression.shop_key == store.shop_key,
                CommerceSuppression.kind == "customer",
            )
            .limit(1)
        )
        is not None
    ):
        return False
    if source.get("test") is not False:
        raise ShopifyError("commerce_test_order")
    created, updated = timestamp(source["createdAt"]), timestamp(source["updatedAt"])
    if updated < created or updated > utc(now):
        raise ShopifyError("commerce_invalid_timestamp")
    entries, quality = normalized_entries(agreements, store, vault)
    floor = retention_floor(now, store.time_zone)
    if any(v["happened_at"] > utc(now) for v in entries.values()):
        raise ShopifyError("commerce_invalid_timestamp")
    fingerprint = hashlib.sha256(
        json.dumps(
            {"entries": entries, "customer": customer_key, "created": created, "quality": quality},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    entries = {k: v for k, v in entries.items() if floor <= v["happened_at"]}
    order = session.get(CommerceOrder, (store.id, key))
    if order is not None:
        if utc(order.source_updated_at) > updated:
            return False
        if utc(order.source_updated_at) == updated:
            if order.fingerprint == fingerprint:
                return False
            raise ShopifyError("commerce_conflicting_revision")
    else:
        order = CommerceOrder(store_id=store.id, order_key=key, workspace_id=store.workspace_id)
        session.add(order)
    order.privacy_key = order_key(vault, row, source["id"])
    order.created_at, order.source_updated_at = created, updated
    order.customer_key, order.fingerprint, order.quality = customer_key, fingerprint, quality
    session.flush()
    previous = list(
        session.scalars(
            select(CommerceEntry).where(
                CommerceEntry.store_id == store.id,
                CommerceEntry.order_key == key,
            )
        )
    )
    days = {utc(e.happened_at).astimezone(ZoneInfo(store.time_zone)).date() for e in previous}
    session.execute(
        delete(CommerceEntry).where(
            CommerceEntry.store_id == store.id, CommerceEntry.order_key == key
        )
    )
    for entry_key, value in entries.items():
        conflict = session.get(CommerceEntry, (store.id, entry_key))
        if conflict is not None:
            raise ShopifyError("commerce_sale_identity_conflict")
        session.add(CommerceEntry(store_id=store.id, order_key=key, entry_key=entry_key, **value))
        days.add(value["happened_at"].astimezone(ZoneInfo(store.time_zone)).date())
    revise_days(session, store, days, now)
    return True


def link_verified_order(
    session: Session,
    workspace_id: int,
    connection_id: int,
    source_order_id: str,
    store_id: str,
    shopify_order_id: str,
    configuration: Settings,
) -> CommerceSourceLink:
    """Adapter-only: authenticated source must supply a verified Shopify order identifier.

    No amount or person-merging input exists. Future B12 adapters own evidence validation.
    """
    connection = session.scalar(
        select(WorkspaceIntegration)
        .where(
            WorkspaceIntegration.id == connection_id,
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.status == "active",
            WorkspaceIntegration.provider.in_(["klaviyo", "hubspot", "omnisend"]),
        )
        .with_for_update()
    )
    if connection is None or not 1 <= len(source_order_id) <= 255:
        raise ShopifyError("commerce_ownership_unavailable")
    store = lock_store(session, store_id, workspace_id)
    vault = Vault(configuration)
    order_key_value = identity_key(vault, store, "order", shopify_order_id)
    if session.get(CommerceOrder, (store.id, order_key_value)) is None:
        raise ShopifyError("commerce_order_unresolved")
    source_key = vault.digest(f"commerce_link:{workspace_id}:{connection_id}", source_order_id)
    link = session.get(CommerceSourceLink, (connection_id, source_key))
    if link and (link.store_id != store.id or link.order_key != order_key_value):
        raise ShopifyError("commerce_link_conflict")
    if link is None:
        link = CommerceSourceLink(
            connection_id=connection_id,
            source_key=source_key,
            workspace_id=workspace_id,
            store_id=store.id,
            order_key=order_key_value,
        )
        session.add(link)
    session.flush()
    return link
