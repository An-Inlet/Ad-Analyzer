import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, delete, or_, select
from sqlalchemy.orm import Session

from app.automation import AutomationControlKey, AutomationControlService
from app.settings import Settings, settings
from app.shopify.client import ShopifyClient
from app.shopify.models import ShopifyAudit, ShopifyConnection, ShopifyOrder, ShopifyTombstone
from app.shopify.normalize import normalized_order, order_key
from app.shopify.security import ShopifyError, Vault, configuration_ready, utc
from app.shopify.service import ConnectionService


def syncing_allowed(session: Session, workspace_id: int) -> bool:
    controls = AutomationControlService(session)
    return controls.master_enabled(
        AutomationControlKey.ALL_DATA_SYNCS
    ) and controls.effective_enabled(workspace_id, AutomationControlKey.SHOPIFY_SALES_SYNC)


class ShopifySyncService:
    def __init__(
        self, session: Session, configuration: Settings, client: ShopifyClient | None = None
    ) -> None:
        self.session, self.settings = session, configuration
        self.client = client or ShopifyClient(configuration)

    def page(
        self, workspace_id: int, *, now: datetime | None = None, manual: bool = False
    ) -> dict[str, Any]:
        now = utc(now or datetime.now(UTC))
        if not configuration_ready(self.settings) or not syncing_allowed(
            self.session, workspace_id
        ):
            return {"status": "disabled", "imported": 0}
        row = self.session.scalar(
            select(ShopifyConnection)
            .where(ShopifyConnection.workspace_id == workspace_id)
            .with_for_update(skip_locked=True)
        )
        if row is None or row.status != "connected":
            return {"status": "not_connected_or_busy", "imported": 0}
        if row.next_attempt_at and utc(row.next_attempt_at) > now:
            return {"status": "retry_later", "imported": 0}
        if (
            not manual
            and not row.window_end
            and row.last_sync_at
            and utc(row.last_sync_at)
            > now - timedelta(minutes=self.settings.shopify_sync_interval_minutes)
        ):
            return {"status": "up_to_date", "imported": 0}
        floor = now - timedelta(days=59)
        if row.window_end is None or row.window_start is None or utc(row.window_end) < floor:
            row.cursor, row.window_end = None, now
            row.window_start = (
                max(floor, utc(row.last_sync_at) - timedelta(days=7)) if row.last_sync_at else floor
            )
        row.last_attempt_at = now
        try:
            token = ConnectionService(self.session, self.settings, self.client).access_token(
                row, now
            )
            # A savepoint rolls back a failed page while retaining the row lock and
            # any rotated credentials until the outer transaction commits.
            with self.session.begin_nested():
                query = (
                    f"updated_at:>='{utc(row.window_start).isoformat()}' "
                    f"updated_at:<='{utc(row.window_end).isoformat()}' "
                    f"created_at:>='{(utc(row.window_end) - timedelta(days=59)).isoformat()}'"
                )
                page = self.client.orders(row.shop_domain, token, row.cursor, query)
                nodes, info = page["nodes"], page["pageInfo"]
                if (
                    not isinstance(nodes, list)
                    or len(nodes) > 10
                    or not isinstance(info["hasNextPage"], bool)
                ):
                    raise ShopifyError("shopify_invalid_page")
                next_cursor = info.get("endCursor")
                if info["hasNextPage"] and (
                    not isinstance(next_cursor, str)
                    or not next_cursor
                    or next_cursor == row.cursor
                    or len(next_cursor) > 4096
                ):
                    raise ShopifyError("shopify_invalid_cursor")
                vault = Vault(self.settings)
                count = 0
                for source in nodes:
                    key = order_key(vault, row, source["id"])
                    existing = self.session.scalar(
                        select(ShopifyOrder).where(
                            ShopifyOrder.connection_id == row.id, ShopifyOrder.order_key == key
                        )
                    )
                    tombstone = self.session.get(ShopifyTombstone, (row.id, key))
                    if source.get("test") is True or tombstone:
                        if existing:
                            self.session.delete(existing)
                        continue
                    values = normalized_order(self.session, row, source, vault)
                    if existing and utc(existing.source_updated_at) > values["source_updated_at"]:
                        continue
                    if existing is None:
                        existing = ShopifyOrder(
                            connection_id=row.id, workspace_id=row.workspace_id, **values
                        )
                        self.session.add(existing)
                    else:
                        for field, value in values.items():
                            setattr(existing, field, value)
                    count += 1
                self.session.execute(
                    delete(ShopifyOrder)
                    .execution_options(synchronize_session="fetch")
                    .where(ShopifyOrder.connection_id == row.id, ShopifyOrder.created_at < floor)
                )
                row.covered_from = max(utc(row.covered_from), floor) if row.covered_from else floor
                row.error_code, row.next_attempt_at = None, None
                row.cursor = next_cursor if info["hasNextPage"] else None
                status = "syncing" if info["hasNextPage"] else "complete"
                if status == "complete":
                    row.last_sync_at = row.window_end
                    row.window_start, row.window_end = None, None
                self.session.add(
                    ShopifyAudit(
                        workspace_id=workspace_id,
                        action="sync_page",
                        actor_role="operator" if manual else "scheduler",
                        record_count=count,
                    )
                )
            self.session.commit()
            return {"status": status, "imported": count}
        except (ShopifyError, KeyError, TypeError, ValueError) as exc:
            code = exc.code if isinstance(exc, ShopifyError) else "shopify_invalid_response"
            row.error_code, row.last_attempt_at = code, now
            row.next_attempt_at = now + timedelta(
                seconds=exc.retry_after if isinstance(exc, ShopifyError) else 60
            )
            if code == "shopify_reconnect_required":
                row.status = "reconnect_required"
            self.session.add(
                ShopifyAudit(
                    workspace_id=workspace_id,
                    action=code,
                    actor_role="operator" if manual else "scheduler",
                )
            )
            self.session.commit()
            return {"status": code, "imported": 0}


def run_shopify_tick(engine: Engine) -> None:
    if not configuration_ready(settings):
        return
    now = datetime.now(UTC)
    with Session(engine) as session:
        ids = list(
            session.scalars(
                select(ShopifyConnection.workspace_id)
                .where(
                    ShopifyConnection.status == "connected",
                    or_(
                        ShopifyConnection.next_attempt_at.is_(None),
                        ShopifyConnection.next_attempt_at <= now,
                    ),
                    or_(
                        ShopifyConnection.last_sync_at.is_(None),
                        ShopifyConnection.window_end.is_not(None),
                        ShopifyConnection.last_sync_at
                        <= now - timedelta(minutes=settings.shopify_sync_interval_minutes),
                    ),
                )
                .order_by(ShopifyConnection.last_sync_at.asc().nullsfirst())
                .limit(10)
            )
        )
    for workspace_id in ids:
        for _page in range(settings.shopify_sync_pages):
            with Session(engine) as session:
                try:
                    result = ShopifySyncService(session, settings).page(workspace_id)
                except Exception:
                    session.rollback()
                    logging.getLogger(__name__).warning("shopify_sync_failed")
                    break
            if result["status"] != "syncing":
                break
