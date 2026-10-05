"""Minimize and erase local facts from Shopify's authenticated cloud event bus."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, delete, or_, select
from sqlalchemy.orm import Session

from app.imports.native import revoke_native_integration
from app.settings import Settings, settings
from app.shopify.models import (
    ShopifyAudit,
    ShopifyConnection,
    ShopifyOAuthState,
    ShopifyOrder,
    ShopifyPrivacyRequest,
    ShopifyTombstone,
)
from app.shopify.normalize import order_key, resource_id
from app.shopify.security import ShopifyError, Vault, shop_domain, utc

TOPICS = {
    "orders/delete",
    "customers/redact",
    "customers/data_request",
    "shop/redact",
    "app/uninstalled",
}
logger = logging.getLogger(__name__)


def process_event(
    session: Session,
    configuration: Settings,
    topic: str,
    shop: str,
    payload: dict[str, Any],
    published_at: datetime,
) -> None:
    if topic not in TOPICS:
        raise ShopifyError("shopify_unknown_event")
    shop = shop_domain(shop)
    row = session.scalar(
        select(ShopifyConnection).where(ShopifyConnection.shop_domain == shop).with_for_update()
    )
    if payload.get("shop_domain") and shop_domain(str(payload["shop_domain"])) != shop:
        raise ShopifyError("shopify_event_shop_mismatch")
    from app.commerce.models import CommerceShopAlias, CommerceStore
    from app.commerce.privacy import process_measurement_event

    matching_stores = select(CommerceStore.id).where(
        or_(
            CommerceStore.shop_domain == shop,
            CommerceStore.id.in_(
                select(CommerceShopAlias.store_id).where(CommerceShopAlias.shop_domain == shop)
            ),
        )
    )
    if row is None:
        # Keep native -> store lock order when a delayed event uses a verified old domain.
        row = session.scalar(
            select(ShopifyConnection)
            .where(
                ShopifyConnection.commerce_store_id.in_(matching_stores),
            )
            .with_for_update()
        )
    commerce_keys = []
    stores = list(
        session.scalars(
            select(CommerceStore)
            .where(
                CommerceStore.id.in_(matching_stores),
            )
            .with_for_update()
        )
    )
    for store in stores:
        keys_for_store = process_measurement_event(
            session, store, topic, payload, configuration, published_at
        )
        if row is not None and row.commerce_store_id == store.id:
            commerce_keys.extend(keys_for_store)
    if row is None:
        session.commit()
        return
    if topic in {"shop/redact", "app/uninstalled"}:
        if utc(published_at) < utc(row.connected_at):
            return  # An event from a previous installation must not erase a new authorization.
        session.execute(
            delete(ShopifyOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyOAuthState.shop_domain == shop)
        )
        session.add(
            ShopifyAudit(
                workspace_id=row.workspace_id, action="store_removed", actor_role="shopify"
            )
        )
        revoke_native_integration(session, row.workspace_integration_id)
        session.delete(row)
    else:
        vault = Vault(configuration)
        if topic == "orders/delete":
            raw_ids = [payload["id"]]
        else:
            raw_ids = payload[
                "orders_to_redact" if topic == "customers/redact" else "orders_requested"
            ]
        if not isinstance(raw_ids, list) or len(raw_ids) > 100_000:
            raise ShopifyError("shopify_invalid_event")
        keys = sorted({order_key(vault, row, value) for value in raw_ids})
        if topic == "customers/data_request":
            for offset in range(0, len(commerce_keys), 500):
                keys.extend(
                    session.scalars(
                        select(ShopifyOrder.order_key).where(
                            ShopifyOrder.connection_id == row.id,
                            ShopifyOrder.commerce_order_key.in_(
                                commerce_keys[offset : offset + 500]
                            ),
                        )
                    )
                )
            keys = sorted(set(keys))
            request_key = vault.digest(
                f"privacy:{shop}", resource_id(payload["data_request"]["id"], "DataRequest")
            )
            existing = session.scalar(
                select(ShopifyPrivacyRequest.id).where(
                    ShopifyPrivacyRequest.connection_id == row.id,
                    ShopifyPrivacyRequest.request_key == request_key,
                )
            )
            if existing is None:
                session.add(
                    ShopifyPrivacyRequest(
                        connection_id=row.id,
                        workspace_id=row.workspace_id,
                        request_key=request_key,
                        order_keys=keys,
                        commerce_keys=commerce_keys,
                        requested_at=utc(published_at),
                    )
                )
        else:
            for offset in range(0, len(keys), 500):
                batch = keys[offset : offset + 500]
                session.execute(
                    delete(ShopifyOrder)
                    .execution_options(synchronize_session="fetch")
                    .where(ShopifyOrder.connection_id == row.id, ShopifyOrder.order_key.in_(batch))
                )
                existing_keys = set(
                    session.scalars(
                        select(ShopifyTombstone.order_key).where(
                            ShopifyTombstone.connection_id == row.id,
                            ShopifyTombstone.order_key.in_(batch),
                        )
                    )
                )
                for key in batch:
                    if key not in existing_keys:
                        session.add(
                            ShopifyTombstone(
                                connection_id=row.id, workspace_id=row.workspace_id, order_key=key
                            )
                        )
            session.add(
                ShopifyAudit(
                    workspace_id=row.workspace_id,
                    action="orders_erased",
                    actor_role="shopify",
                    record_count=len(keys),
                )
            )
    session.commit()  # Acknowledge the event only after the database commit succeeds.


def run_privacy_tick(engine: Engine) -> None:
    # Privacy handling continues when imports or integration enablement are switched off.
    if not settings.shopify_webhook_subscription or not settings.shopify_identifier_hash_key:
        return
    import google.cloud.pubsub_v1 as pubsub_v1  # type: ignore[import-untyped]

    with pubsub_v1.SubscriberClient() as subscriber:
        response = subscriber.pull(
            request={"subscription": settings.shopify_webhook_subscription, "max_messages": 50},
            timeout=10,
        )
        for received in response.received_messages:
            try:
                message = received.message
                if len(message.data) > 10_000_000:
                    raise ShopifyError("shopify_event_too_large")
                # Native Shopify Pub/Sub delivery: metadata plus the webhook payload.
                event = json.loads(message.data)
                metadata = {
                    str(k).lower(): v for k, v in event.get("metadata", message.attributes).items()
                }
                with Session(engine) as session:
                    process_event(
                        session,
                        settings,
                        metadata["x-shopify-topic"],
                        metadata["x-shopify-shop-domain"],
                        event.get("payload", event),
                        datetime.fromisoformat(
                            metadata["x-shopify-triggered-at"].replace("Z", "+00:00")
                        )
                        if metadata.get("x-shopify-triggered-at")
                        else message.publish_time,
                    )
                subscriber.acknowledge(
                    request={
                        "subscription": settings.shopify_webhook_subscription,
                        "ack_ids": [received.ack_id],
                    },
                    timeout=10,
                )
            except Exception:
                # Retry through the configured dead-letter policy; never log payloads.
                logger.warning("shopify_privacy_event_failed")


def purge_expired_facts(engine: Engine, *, now: datetime | None = None) -> None:
    now = utc(now or datetime.now(UTC))
    with Session(engine) as session:
        from app.commerce.privacy import purge_measurements

        purge_measurements(session, now)
        # Retention applies even while imports are paused or access has been revoked.
        session.execute(
            delete(ShopifyOrder)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyOrder.created_at < now - timedelta(days=59))
        )
        session.execute(
            delete(ShopifyTombstone)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyTombstone.created_at < now - timedelta(days=61))
        )
        session.execute(
            delete(ShopifyOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyOAuthState.expires_at < now)
        )
        session.execute(
            delete(ShopifyPrivacyRequest)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyPrivacyRequest.completed_at < now - timedelta(days=30))
        )
        session.execute(
            delete(ShopifyAudit)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyAudit.created_at < now - timedelta(days=90))
        )
        session.commit()
