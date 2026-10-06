import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, or_, select
from sqlalchemy.orm import Session

from app.automation import AutomationControlKey, AutomationControlService
from app.automation.models import WorkspaceAutomationControl
from app.commerce.ledger import MEASUREMENT_SCOPES, apply_order, lock_store, retention_floor
from app.commerce.models import CommerceStore
from app.commerce.source import MeasurementClient
from app.imports.native import bind_shopify
from app.imports.scope import ImportScopeError
from app.settings import Settings
from app.shopify.models import ShopifyAudit, ShopifyConnection
from app.shopify.security import ShopifyError, Vault, configuration_ready, utc
from app.shopify.service import ConnectionService
from app.shopify.sync import syncing_allowed
from app.workspaces.models import Workspace, WorkspaceIntegration


class CommerceSyncService:
    def __init__(
        self, session: Session, configuration: Settings, client: MeasurementClient | None = None
    ) -> None:
        self.session, self.settings = session, configuration
        self.client = client or MeasurementClient(configuration)

    def page(self, workspace_id: int, *, now: datetime | None = None) -> dict[str, Any]:
        now = utc(now or datetime.now(UTC))
        if (
            not self.settings.shopify_measurement_enabled
            or not configuration_ready(self.settings)
            or not syncing_allowed(self.session, workspace_id)
        ):
            return {"status": "disabled", "imported": 0}
        from app.commerce.evidence import lock_workspace, publish, state

        try:
            lock_workspace(self.session, workspace_id, active=True)
        except ShopifyError:
            return {"status": "commerce_ownership_unavailable", "imported": 0}
        row = self.session.scalar(
            select(ShopifyConnection)
            .where(
                ShopifyConnection.workspace_id == workspace_id,
            )
            .with_for_update(skip_locked=True)
        )
        if row is None or row.status != "connected" or row.commerce_store_id is None:
            return {"status": "commerce_reauthorization_required", "imported": 0}
        store: CommerceStore | None = None
        try:
            bind_shopify(self.session, row)
            store = lock_store(self.session, row.commerce_store_id, workspace_id)
            if store.next_attempt_at and utc(store.next_attempt_at) > now:
                return {"status": "retry_later", "imported": 0}
            if (
                store.window_end is None
                and store.last_sync_at
                and utc(store.last_sync_at)
                > now - timedelta(minutes=self.settings.shopify_sync_interval_minutes)
            ):
                return {"status": "up_to_date", "imported": 0}
            store.last_attempt_at = now
            token = ConnectionService(self.session, self.settings, self.client).access_token(
                row, now
            )
            bundle = Vault(self.settings).open(
                workspace_id, row.shop_domain, row.encrypted_credentials
            )
            if not set(bundle.get("scopes", [])) >= MEASUREMENT_SCOPES:
                raise ShopifyError("commerce_history_access_required")
            with self.session.begin_nested():
                if store.window_end is None:
                    floor = retention_floor(now, store.time_zone)
                    store.window_start = (
                        max(floor, utc(store.last_sync_at) - timedelta(days=7))
                        if store.last_sync_at
                        and state(self.session, store, now).history_from is not None
                        else floor
                    )
                    store.window_end, store.cursor = now, None
                start, end = utc(store.window_start), utc(store.window_end)  # type: ignore[arg-type]
                query = f"updated_at:>='{start.isoformat()}' updated_at:<='{end.isoformat()}'"
                sources, after = self.client.measurement_orders(
                    row.shop_domain, token, store.cursor, query
                )
                if after is not None and after == store.cursor:
                    raise ShopifyError("commerce_invalid_cursor")
                count = 0
                for source in sources:
                    if source.get("test") is True:
                        continue
                    agreements = self.client.agreements(row.shop_domain, token, source["id"])
                    count += apply_order(
                        self.session, store, row, source, agreements, self.settings, now
                    )
                from app.shopify.privacy_identity import finish_reconciliation

                self.session.flush()
                finish_reconciliation(self.session, row)
                store.cursor, store.error_code, store.next_attempt_at = after, None, None
                status = "syncing" if after else "complete"
                if after is None:
                    if store.covered_from is None:
                        store.covered_from = start
                    store.last_sync_at = end
                    store.window_start, store.window_end = None, None
                    from app.shopify.security import API_VERSION

                    publish(self.session, store, start, end, now, API_VERSION)
                self.session.add(
                    ShopifyAudit(
                        workspace_id=workspace_id,
                        action="measurement_page",
                        actor_role="scheduler",
                        record_count=count,
                    )
                )
            self.session.commit()
            return {"status": status, "imported": count}
        except (ShopifyError, ImportScopeError, KeyError, ValueError, TypeError) as exc:
            code = exc.code if isinstance(exc, ShopifyError) else "commerce_invalid_source"
            if store is not None:
                store.error_code = code
                store.next_attempt_at = now + timedelta(
                    seconds=exc.retry_after if isinstance(exc, ShopifyError) else 60
                )
                self.session.commit()
            else:
                self.session.rollback()
            return {"status": code, "imported": 0}


def run_commerce_tick(engine: Engine, configuration: Settings) -> None:
    if not configuration.shopify_measurement_enabled:
        return
    with Session(engine) as db:
        controls = AutomationControlService(db)
        if not configuration_ready(configuration) or not all(
            controls.master_enabled(key)
            for key in (
                AutomationControlKey.ALL_DATA_SYNCS,
                AutomationControlKey.SHOPIFY_SALES_SYNC,
            )
        ):
            return
        now = datetime.now(UTC)
        paused = select(WorkspaceAutomationControl.workspace_id).where(
            WorkspaceAutomationControl.key == AutomationControlKey.SHOPIFY_SALES_SYNC.value,
            WorkspaceAutomationControl.enabled.is_(False),
        )
        ids = list(
            db.scalars(
                select(ShopifyConnection.workspace_id)
                .join(CommerceStore, CommerceStore.id == ShopifyConnection.commerce_store_id)
                .join(Workspace, Workspace.id == ShopifyConnection.workspace_id)
                .join(
                    WorkspaceIntegration,
                    WorkspaceIntegration.id == ShopifyConnection.workspace_integration_id,
                )
                .where(
                    ShopifyConnection.commerce_store_id.is_not(None),
                    ShopifyConnection.status == "connected",
                    CommerceStore.status == "active",
                    Workspace.status == "active",
                    WorkspaceIntegration.status == "active",
                    WorkspaceIntegration.provider == "shopify",
                    WorkspaceIntegration.workspace_id == ShopifyConnection.workspace_id,
                    CommerceStore.connection_id == WorkspaceIntegration.id,
                    ~ShopifyConnection.workspace_id.in_(paused),
                    or_(
                        CommerceStore.window_end.is_not(None),
                        CommerceStore.last_sync_at.is_(None),
                        CommerceStore.last_sync_at
                        <= now - timedelta(minutes=configuration.shopify_sync_interval_minutes),
                    ),
                    or_(
                        CommerceStore.next_attempt_at.is_(None),
                        CommerceStore.next_attempt_at <= now,
                    ),
                )
                .order_by(CommerceStore.last_attempt_at.asc().nullsfirst(), CommerceStore.id)
                .limit(10)
            )
        )
    for workspace_id in ids:
        with Session(engine) as db:
            try:
                CommerceSyncService(db, configuration).page(workspace_id)
            except Exception:
                db.rollback()
                logging.getLogger(__name__).warning("commerce_sync_failed")
