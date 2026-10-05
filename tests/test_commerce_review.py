"""Regressions from independent B05 review; providers remain synthetic."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from app.commerce.ledger import apply_order, bind_store
from app.commerce.models import CommerceEntry
from app.commerce.reporting import measurement
from app.imports.native import bind_shopify
from app.settings import Settings
from app.shopify.privacy import process_event
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW, agreement, setup, source, window
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration
from tests.test_shopify_sales import connected


def test_refund_uses_processed_date_not_agreement_date(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        refund = agreement(2, "22", "2", "RETURN", datetime(2026, 9, 30, tzinfo=UTC))
        refund["refund"] = {"processedAt": "2026-10-02T00:00:00Z"}
        apply_order(db, store, row, source(updated=NOW), [agreement(), refund], configuration, NOW)
        september = measurement(db, row.workspace_id, store.id, window(), now=NOW)
        october = measurement(
            db,
            row.workspace_id,
            store.id,
            window(date(2026, 10, 1), date(2026, 10, 5), "cumulative"),
            now=NOW,
        )
        assert september["net_sales_micros"] == 90_000_000
        assert october["net_sales_micros"] == -20_000_000


def test_open_return_is_not_a_processed_refund(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        opened = agreement(2, "22", "2", "RETURN", datetime(2026, 9, 30, tzinfo=UTC))
        opened.update(__typename="ReturnAgreement", reason="RETURN", refund=None)
        refund = agreement(3, "22", "2", "RETURN", datetime(2026, 10, 2, tzinfo=UTC))
        apply_order(
            db, store, row, source(updated=NOW), [agreement(), opened, refund], configuration, NOW
        )
        september = measurement(db, row.workspace_id, store.id, window(), now=NOW)
        assert september["quality"] == "unavailable"
        assert september["observed_net_sales_micros"] == 90_000_000
        october = measurement(
            db,
            row.workspace_id,
            store.id,
            window(date(2026, 10, 1), date(2026, 10, 5), "cumulative"),
            now=NOW,
        )
        assert october["observed_net_sales_micros"] == -20_000_000


def test_erasure_before_measurement_enable_cannot_replay(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row = connected(db, configuration)
        process_event(
            db,
            configuration,
            "customers/redact",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_to_redact": [1]},
            NOW,
        )
        configuration.shopify_measurement_enabled = True
        bind_shopify(db, row)
        store = bind_store(db, row, "gid://shopify/Shop/123", configuration, NOW)
        db.commit()
        assert not apply_order(db, store, row, source(), [agreement()], configuration, NOW)
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 0


def test_scheduler_skips_paused_and_revoked_before_batch_limit(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.automation import AutomationControlKey
    from app.automation.models import WorkspaceAutomationControl
    from app.commerce.sync import CommerceSyncService, run_commerce_tick
    from app.workspaces.models import WorkspaceIntegration

    selected: list[int] = []
    with Session(customer_engine) as db:
        blocked = []
        for index in range(10):
            native, store = setup(db, configuration, f"fair-{index}")
            store.last_attempt_at, store.last_sync_at = None, None
            blocked.append(native.workspace_id)
            if index % 2:
                registry = db.get(WorkspaceIntegration, native.workspace_integration_id)
                assert registry is not None
                registry.status = "revoked"
            else:
                db.add(
                    WorkspaceAutomationControl(
                        workspace_id=native.workspace_id,
                        key=AutomationControlKey.SHOPIFY_SALES_SYNC.value,
                        enabled=False,
                        updated_by="fixture",
                    )
                )
            db.commit()
        native, store = setup(db, configuration, "eligible")
        eligible_id = native.workspace_id
        store.last_attempt_at, store.last_sync_at = NOW, None
        db.commit()

    def page(self: CommerceSyncService, workspace_id: int, **kwargs: Any) -> dict[str, Any]:
        selected.append(workspace_id)
        return {"status": "complete", "imported": 0}

    monkeypatch.setattr(CommerceSyncService, "page", page)
    run_commerce_tick(customer_engine, configuration)
    run_commerce_tick(customer_engine, configuration)
    assert selected == [eligible_id, eligible_id]
    assert not set(selected).intersection(blocked)


def test_unclassified_legacy_customer_erasure_waits_for_identity(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.commerce.sync import CommerceSyncService
    from app.shopify.models import ShopifyAudit, ShopifyOrder, ShopifyPrivacyIdentity
    from app.shopify.sync import ShopifySyncService

    from tests.test_commerce_measurement import CREATED, FakeMeasurement
    from tests.test_shopify_sales import FakeShopify, page
    from tests.test_shopify_sales import order as old_order

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        store.last_sync_at, store.covered_from = None, None
        db.commit()
        legacy = FakeShopify(
            configuration,
            [
                page(
                    *[
                        old_order(n, createdAt=CREATED.isoformat(), updatedAt=NOW.isoformat())
                        for n in (1, 2)
                    ]
                )
            ],
        )
        assert (
            ShopifySyncService(db, configuration, legacy).page(row.workspace_id, now=NOW)["status"]
            == "complete"
        )
        process_event(
            db,
            configuration,
            "customers/redact",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_to_redact": []},
            NOW,
        )
        assert db.scalar(select(func.count()).select_from(ShopifyOrder)) == 2
        marker = db.scalar(
            select(ShopifyPrivacyIdentity).where(ShopifyPrivacyIdentity.kind == "customer")
        )
        assert marker is not None and marker.pending_legacy
        assert (
            db.scalar(
                select(ShopifyAudit.id).where(
                    ShopifyAudit.action == "privacy_reconciliation_pending"
                )
            )
            is not None
        )
        importer = FakeMeasurement(
            configuration, [([source(1, 100, NOW), source(2, 200, NOW)], None)]
        )
        assert (
            CommerceSyncService(db, configuration, importer).page(row.workspace_id, now=NOW)[
                "status"
            ]
            == "complete"
        )
        assert db.scalar(select(func.count()).select_from(ShopifyOrder)) == 1
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 1
        db.refresh(marker)
        assert not marker.pending_legacy


def test_unclassified_legacy_export_is_pending_not_empty(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from app.commerce.sync import CommerceSyncService
    from app.dashboard import shopify as dashboard
    from app.shopify.models import ShopifyPrivacyRequest
    from app.shopify.sync import ShopifySyncService
    from app.workspaces.models import Workspace
    from fastapi import HTTPException
    from starlette.requests import Request

    from tests.test_commerce_measurement import CREATED, FakeMeasurement
    from tests.test_shopify_sales import FakeShopify, page
    from tests.test_shopify_sales import order as old_order

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        store.last_sync_at, store.covered_from = None, None
        db.commit()
        legacy = FakeShopify(
            configuration,
            [page(old_order(1, createdAt=CREATED.isoformat(), updatedAt=NOW.isoformat()))],
        )
        assert (
            ShopifySyncService(db, configuration, legacy).page(row.workspace_id, now=NOW)["status"]
            == "complete"
        )
        process_event(
            db,
            configuration,
            "customers/data_request",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_requested": [], "data_request": {"id": 555}},
            NOW,
        )
        item = db.scalar(select(ShopifyPrivacyRequest))
        assert item is not None and item.resolution_pending
        workspace = db.get(Workspace, row.workspace_id)
        assert workspace is not None
        monkeypatch.setattr(dashboard, "_workspace", lambda *args, **kwargs: (workspace, "owner"))
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
        with pytest.raises(HTTPException) as denied:
            dashboard.privacy_export(request, workspace.slug, item.id, db)
        assert denied.value.status_code == 409
        import asyncio

        async def accepted_form(request: Request) -> dict[str, str]:
            return {}

        monkeypatch.setattr(dashboard, "_form", accepted_form)
        with pytest.raises(HTTPException) as delivery_denied:
            asyncio.run(dashboard.privacy_delivered(request, workspace.slug, item.id, db))
        assert delivery_denied.value.status_code == 409
        assert item.completed_at is None
        importer = FakeMeasurement(configuration, [([source(updated=NOW)], None)])
        assert (
            CommerceSyncService(db, configuration, importer).page(row.workspace_id, now=NOW)[
                "status"
            ]
            == "complete"
        )
        db.refresh(item)
        assert not item.resolution_pending
        result = json.loads(dashboard.privacy_export(request, workspace.slug, item.id, db).body)
        assert len(result["records"]) == len(result["measurement_records"]) == 1


def test_pre_enable_erasure_survives_disconnect_and_reconnect(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.shopify.models import ShopifyConnection
    from app.shopify.service import ConnectionService

    with Session(customer_engine) as db:
        row = connected(db, configuration)
        wid, domain = row.workspace_id, row.shop_domain
        process_event(
            db,
            configuration,
            "customers/redact",
            domain,
            {"customer": {"id": 100}, "orders_to_redact": []},
            NOW,
        )
        from app.shopify.sync import ShopifySyncService

        from tests.test_shopify_sales import FakeShopify

        legacy = FakeShopify(configuration)
        assert (
            ShopifySyncService(db, configuration, legacy).page(wid, now=NOW)["status"]
            == "shopify_privacy_reconciliation_required"
        )
        assert legacy.requests == []
        ConnectionService(db, configuration).disconnect(wid, "owner")
        replacement = ShopifyConnection(
            workspace_id=wid,
            shop_domain=domain,
            shop_name="Example",
            currency_code="USD",
            time_zone="UTC",
            encrypted_credentials="unused",
        )
        db.add(replacement)
        bind_shopify(db, replacement, reconnect=True)
        store = bind_store(db, replacement, "gid://shopify/Shop/123", configuration, NOW)
        assert not apply_order(db, store, replacement, source(), [agreement()], configuration, NOW)
        assert apply_order(
            db, store, replacement, source(2, 200), [agreement(2)], configuration, NOW
        )
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 1


def test_unknown_canonical_customer_keeps_privacy_pending(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.shopify.models import ShopifyPrivacyIdentity, ShopifyPrivacyRequest
    from app.shopify.privacy_identity import finish_reconciliation

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        apply_order(db, store, row, source(1, None), [agreement()], configuration, NOW)
        db.commit()
        process_event(
            db,
            configuration,
            "customers/data_request",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_requested": [], "data_request": {"id": 555}},
            NOW,
        )
        process_event(
            db,
            configuration,
            "customers/redact",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_to_redact": []},
            NOW,
        )
        finish_reconciliation(db, row)
        request = db.scalar(select(ShopifyPrivacyRequest))
        marker = db.scalar(
            select(ShopifyPrivacyIdentity).where(ShopifyPrivacyIdentity.kind == "customer")
        )
        assert request is not None and request.resolution_pending
        assert marker is not None and marker.pending_legacy
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 1


def test_migration_preserves_pre_enable_tombstones(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alembic import command
    from alembic.config import Config
    from app.settings import settings
    from app.shopify.models import ShopifyPrivacyIdentity, ShopifyTombstone
    from app.shopify.normalize import order_key
    from app.shopify.security import Vault
    from sqlalchemy import text

    if customer_engine.dialect.name != "postgresql":
        return  # Populated production-schema upgrade is PostgreSQL-only.
    with Session(customer_engine) as db:
        row = connected(db, configuration)
        wid, domain, rid = row.workspace_id, row.shop_domain, row.id
        key = order_key(Vault(configuration), row, 1)
        db.add(ShopifyTombstone(connection_id=rid, workspace_id=wid, order_key=key))
        db.commit()
    with customer_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    scoped = customer_engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    command.stamp(config, "head")
    command.downgrade(config, "20261005_0024")
    command.upgrade(config, "head")
    with Session(customer_engine) as db:
        from app.shopify.models import ShopifyConnection

        assert db.get(ShopifyPrivacyIdentity, (wid, domain, "order", key)) is not None
        restored = db.get(ShopifyConnection, rid)
        assert restored is not None
        bind_shopify(db, restored)
        store = bind_store(db, restored, "gid://shopify/Shop/123", configuration, NOW)
        assert not apply_order(db, store, restored, source(), [agreement()], configuration, NOW)
