"""B04 review regressions: verified reconnect, lifecycle events and serialization."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from app.imports.native import bind_shopify
from app.imports.scope import ImportScopeError
from app.settings import Settings
from app.shopify.models import ShopifyConnection
from app.shopify.privacy import process_event
from app.shopify.security import ShopifyError, verify_callback
from app.shopify.service import ConnectionService
from app.shopify.sync import ShopifySyncService
from app.workspaces.models import Workspace, WorkspaceIntegration
from sqlalchemy import Engine, select, text, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import NOW, SHOP, FakeShopify, callback_values, connected, page
from tests.test_shopify_sales import configuration as configuration


def reauthorize(db: Session, configuration: Settings, workspace_id: int) -> ShopifyConnection:
    service = ConnectionService(db, configuration, FakeShopify(configuration))
    args = parse_qs(urlsplit(service.begin(workspace_id, SHOP, "owner", NOW)).query)
    assert configuration.shopify_client_secret
    values = callback_values(
        configuration.shopify_client_secret.get_secret_value(), state=args["state"][0]
    )
    verified = verify_callback(
        list(values.items()), configuration.shopify_client_secret.get_secret_value(), NOW
    )
    state = service.pending(verified, "owner", NOW)
    return service.finish(state, verified["code"], "owner", NOW)


def test_only_verified_shopify_reauthorization_restores_same_registry(
    customer_engine: Engine,
    configuration: Settings,
) -> None:
    with Session(customer_engine) as db:
        row = connected(db, configuration)
        bind_shopify(db, row)
        registry = db.get(WorkspaceIntegration, row.workspace_integration_id)
        assert registry
        connection_id = registry.id
        registry.status = "revoked"
        row.status = "reconnect_required"
        db.commit()
        with pytest.raises(ImportScopeError):
            bind_shopify(db, row)
        assert registry.status == "revoked"
        service = ConnectionService(db, configuration, FakeShopify(configuration))
        args = parse_qs(urlsplit(service.begin(row.workspace_id, SHOP, "owner", NOW)).query)
        with pytest.raises(ShopifyError):
            service.pending({"state": args["state"][0], "shop": SHOP}, "other-owner", NOW)
        assert registry.status == "revoked"
        restored = reauthorize(db, configuration, row.workspace_id)
        assert restored.workspace_integration_id == connection_id
        db.refresh(registry)
        assert registry.status == "active"
        registry.status = "revoked"
        registry.provider = "meta_ads"
        db.commit()
        with pytest.raises(ImportScopeError):
            bind_shopify(db, row, reconnect=True)
        assert registry.status == "revoked"


@pytest.mark.parametrize("topic", ["app/uninstalled", "shop/redact"])
def test_shopify_removal_revokes_registry_but_old_events_do_not(
    customer_engine: Engine,
    configuration: Settings,
    topic: str,
) -> None:
    with Session(customer_engine) as db:
        row = connected(db, configuration)
        bind_shopify(db, row)
        connection_id = row.workspace_integration_id
        db.commit()
        process_event(db, configuration, topic, SHOP, {}, NOW - timedelta(days=1))
        registry = db.get(WorkspaceIntegration, connection_id)
        assert registry and registry.status == "active"
        process_event(db, configuration, topic, SHOP, {}, NOW)
        db.expire_all()
        assert db.scalar(select(ShopifyConnection)) is None
        registry = db.get(WorkspaceIntegration, connection_id)
        assert registry and registry.status == "revoked"
        # Replayed removal cannot restore or delete the canonical historical row.
        process_event(db, configuration, topic, SHOP, {}, NOW)
        assert db.get(WorkspaceIntegration, connection_id) is registry


@pytest.mark.parametrize("target", ["connection", "workspace"])
def test_postgres_revocation_serializes_with_inflight_shopify_import(
    customer_engine: Engine,
    configuration: Settings,
    target: str,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    with Session(customer_engine) as db:
        row = connected(db, configuration)
        bind_shopify(db, row)
        workspace_id, connection_id = row.workspace_id, row.workspace_integration_id
        db.commit()
    collecting, release, revoking, revoked = (Event() for _ in range(4))

    class PausedShopify(FakeShopify):
        def orders(self, *args: object, **kwargs: object) -> dict[str, Any]:
            collecting.set()
            assert release.wait(10)
            return page()

    def import_page() -> dict[str, Any]:
        with Session(customer_engine) as db:
            return ShopifySyncService(db, configuration, PausedShopify(configuration)).page(
                workspace_id, now=NOW, manual=True
            )

    def revoke() -> None:
        with Session(customer_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
            revoking.set()
            if target == "connection":
                db.execute(
                    update(WorkspaceIntegration)
                    .where(WorkspaceIntegration.id == connection_id)
                    .values(status="revoked")
                )
            else:
                db.execute(
                    update(Workspace).where(Workspace.id == workspace_id).values(status="suspended")
                )
            db.commit()
            revoked.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        imported = pool.submit(import_page)
        assert collecting.wait(5)
        revocation = pool.submit(revoke)
        assert revoking.wait(5)
        try:
            assert not revoked.wait(0.2)
        finally:
            release.set()
        assert imported.result(timeout=10)["status"] == "complete"
        revocation.result(timeout=10)
    with Session(customer_engine) as db:
        fake = FakeShopify(configuration)
        assert (
            ShopifySyncService(db, configuration, fake).page(
                workspace_id, now=NOW + timedelta(hours=1), manual=True
            )["status"]
            == "shopify_ownership_unavailable"
        )
        assert not fake.requests
