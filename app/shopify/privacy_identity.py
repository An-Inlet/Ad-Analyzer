"""Durable minimal legacy erasure markers and explicit unresolved identity state."""

from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.commerce.models import CommerceOrder, CommerceShopAlias, CommerceStore
from app.settings import Settings
from app.shopify.models import (
    ShopifyConnection,
    ShopifyOrder,
    ShopifyPrivacyIdentity,
    ShopifyPrivacyRequest,
    ShopifyTombstone,
)
from app.shopify.normalize import resource_id
from app.shopify.security import ShopifyError, Vault

SCOPE = "0" * 64


def legacy_key(vault: Vault, workspace_id: int, domain: str, kind: str, source_id: object) -> str:
    if kind == "order":
        return vault.digest(f"order:{workspace_id}:{domain}", resource_id(source_id, "Order"))
    return vault.digest(
        f"privacy_customer:{workspace_id}:{domain}", resource_id(source_id, "Customer")
    )


def remember(
    session: Session, workspace_id: int, domain: str, kind: str, key: str
) -> ShopifyPrivacyIdentity:
    marker = session.get(ShopifyPrivacyIdentity, (workspace_id, domain, kind, key))
    if marker is None:
        marker = ShopifyPrivacyIdentity(
            workspace_id=workspace_id, shop_domain=domain, kind=kind, object_key=key
        )
        session.add(marker)
        session.flush()
    return marker


def preserve(session: Session, row: ShopifyConnection) -> None:
    remember(session, row.workspace_id, row.shop_domain, "scope", SCOPE)
    for key in session.scalars(
        select(ShopifyTombstone.order_key).where(ShopifyTombstone.connection_id == row.id)
    ):
        remember(session, row.workspace_id, row.shop_domain, "order", key)


def record_erasure(
    session: Session,
    configuration: Settings,
    workspace_id: int,
    domain: str,
    topic: str,
    payload: dict[str, Any],
) -> ShopifyPrivacyIdentity | None:
    remember(session, workspace_id, domain, "scope", SCOPE)
    if topic not in {"orders/delete", "customers/redact"}:
        return None
    ids = [payload["id"]] if topic == "orders/delete" else payload["orders_to_redact"]
    if not isinstance(ids, list) or len(ids) > 100_000:
        raise ShopifyError("shopify_invalid_event")
    vault = Vault(configuration)
    for source_id in ids:
        remember(
            session,
            workspace_id,
            domain,
            "order",
            legacy_key(vault, workspace_id, domain, "order", source_id),
        )
    customer = payload.get("customer")
    if topic == "customers/redact" and customer and customer.get("id") is not None:
        return remember(
            session,
            workspace_id,
            domain,
            "customer",
            legacy_key(vault, workspace_id, domain, "customer", customer["id"]),
        )
    return None


def domains(session: Session, store: CommerceStore) -> set[str]:
    return {
        store.shop_domain,
        *session.scalars(
            select(CommerceShopAlias.shop_domain).where(CommerceShopAlias.store_id == store.id)
        ),
    }


def markers(session: Session, store: CommerceStore) -> list[ShopifyPrivacyIdentity]:
    # An old domain with erasure history but no verified stable-shop mapping is
    # unresolved; never guess that reconnecting to another domain clears it.
    mapped_domains = (
        select(CommerceShopAlias.shop_domain)
        .join(CommerceStore)
        .where(CommerceStore.workspace_id == store.workspace_id)
    )
    return list(
        session.scalars(
            select(ShopifyPrivacyIdentity).where(
                ShopifyPrivacyIdentity.workspace_id == store.workspace_id,
                ShopifyPrivacyIdentity.kind != "scope",
                or_(
                    ShopifyPrivacyIdentity.shop_domain.in_(domains(session, store)),
                    ~ShopifyPrivacyIdentity.shop_domain.in_(mapped_domains),
                ),
            )
        )
    )


def unclassified(session: Session, row: ShopifyConnection) -> bool:
    if row.commerce_store_id is None:
        return (
            session.scalar(
                select(ShopifyOrder.id).where(ShopifyOrder.connection_id == row.id).limit(1)
            )
            is not None
        )
    if (
        session.scalar(
            select(CommerceOrder.order_key)
            .where(
                CommerceOrder.store_id == row.commerce_store_id,
                CommerceOrder.customer_key.is_(None),
            )
            .limit(1)
        )
        is not None
    ):
        return True
    return (
        session.scalar(
            select(ShopifyOrder.id)
            .outerjoin(
                CommerceOrder,
                (CommerceOrder.store_id == row.commerce_store_id)
                & (CommerceOrder.order_key == ShopifyOrder.commerce_order_key),
            )
            .where(
                ShopifyOrder.connection_id == row.id,
                or_(CommerceOrder.order_key.is_(None), CommerceOrder.customer_key.is_(None)),
            )
            .limit(1)
        )
        is not None
    )


def prepare_source(
    session: Session,
    row: ShopifyConnection,
    store: CommerceStore,
    source: dict[str, Any],
    canonical_key: str,
    configuration: Settings,
) -> tuple[bool, bool]:
    """Bridge identifiable legacy facts before applying financial data or suppression."""
    vault = Vault(configuration)
    key = legacy_key(vault, row.workspace_id, row.shop_domain, "order", source["id"])
    session.execute(
        update(ShopifyOrder)
        .where(ShopifyOrder.connection_id == row.id, ShopifyOrder.order_key == key)
        .values(commerce_order_key=canonical_key)
    )
    customer = source.get("customer")
    if customer:
        customer_key = legacy_key(
            vault, row.workspace_id, row.shop_domain, "customer", customer["id"]
        )
        for request in session.scalars(
            select(ShopifyPrivacyRequest).where(
                ShopifyPrivacyRequest.connection_id == row.id,
                ShopifyPrivacyRequest.customer_key == customer_key,
                ShopifyPrivacyRequest.completed_at.is_(None),
            )
        ):
            request.order_keys = sorted(set(request.order_keys) | {key})
            request.commerce_keys = sorted(set(request.commerce_keys) | {canonical_key})
    erased, unresolved = False, False
    known_domains = domains(session, store)
    for marker in markers(session, store):
        if marker.kind == "unresolved" or marker.shop_domain not in known_domains:
            unresolved = True
        elif marker.kind == "order":
            erased |= marker.object_key == legacy_key(
                vault, row.workspace_id, marker.shop_domain, "order", source["id"]
            )
        elif marker.kind == "customer":
            if not customer:
                unresolved = True
            else:
                erased |= marker.object_key == legacy_key(
                    vault, row.workspace_id, marker.shop_domain, "customer", customer["id"]
                )
    return erased, unresolved


def finish_reconciliation(session: Session, row: ShopifyConnection) -> None:
    pending = unclassified(session, row)
    for request in session.scalars(
        select(ShopifyPrivacyRequest).where(
            ShopifyPrivacyRequest.connection_id == row.id,
            ShopifyPrivacyRequest.resolution_pending.is_(True),
        )
    ):
        if request.customer_key is not None and not pending:
            request.resolution_pending = False
    if not pending:
        store = session.get(CommerceStore, row.commerce_store_id) if row.commerce_store_id else None
        known_domains = domains(session, store) if store is not None else {row.shop_domain}
        session.execute(
            update(ShopifyPrivacyIdentity)
            .where(
                ShopifyPrivacyIdentity.workspace_id == row.workspace_id,
                ShopifyPrivacyIdentity.shop_domain.in_(known_domains),
                ShopifyPrivacyIdentity.kind == "customer",
            )
            .values(pending_legacy=False)
        )


def legacy_erased(session: Session, row: ShopifyConnection, key: str) -> bool:
    return (
        session.get(ShopifyPrivacyIdentity, (row.workspace_id, row.shop_domain, "order", key))
        is not None
    )
