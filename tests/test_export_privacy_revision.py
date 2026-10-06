"""Shared privacy counter rollback/status semantics, without provider IO."""

from pathlib import Path
from typing import Any

import pytest
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import seed
from tests.test_meta_connection import configuration as meta_configuration  # noqa: F401
from tests.test_shopify_sales import configuration as configuration


def test_revision_tracks_transaction_not_customer_access(customer_engine: Engine) -> None:
    from app.workspaces.models import Workspace

    with Session(customer_engine) as db:
        _, wid = seed(db)
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.status = "closing"
        db.commit()
        assert workspace_export_revision(db, wid) == 0
        bump_workspace_export_revision(db, wid)
        assert workspace_export_revision(db, wid) == 1
        db.rollback()
        assert workspace_export_revision(db, wid) == 0
        bump_workspace_export_revision(db, wid)
        db.commit()
        assert workspace_export_revision(db, wid) == 1
        with pytest.raises(ValueError, match="unavailable"):
            bump_workspace_export_revision(db, wid + 10000)


@pytest.mark.parametrize("phase", ["build", "stream"])
def test_actual_legacy_only_erasure_interrupts_export(
    export_engine: Engine, configuration: Settings, tmp_path: Path, phase: str
) -> None:
    from app.campaign_review.storage import LocalMediaStore
    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerMembership
    from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
    from app.lifecycle.exports import SLOTS, Authority, Download
    from app.lifecycle.service import begin
    from app.shopify.models import ShopifyOrder
    from app.shopify.privacy import process_event
    from app.shopify.sync import ShopifySyncService
    from fastapi import HTTPException
    from sqlalchemy import func, select

    from tests.test_customer_exports import build
    from tests.test_customer_identity import FakeProvider
    from tests.test_shopify_sales import NOW, SHOP, FakeShopify, connected, order, page

    with Session(export_engine) as db:
        principal, _ = seed(db, "export-owner")
        row = connected(db, configuration)
        wid = row.workspace_id
        db.add(
            CustomerMembership(
                workspace_id=wid, user_id=principal.user.id, role="owner", status="active"
            )
        )
        db.commit()
        ShopifySyncService(db, configuration, FakeShopify(configuration, [page(order())])).page(
            wid, now=NOW
        )
        assert row.commerce_store_id is None
        assert db.scalar(select(func.count()).select_from(ShopifyOrder)) == 1
        request = begin(
            db,
            principal,
            FakeProvider(),
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "privacy-race-request",
            NOW,
        )
        db.commit()
        authority = Authority(
            export_engine,
            CustomerPrincipal(principal.user, principal.session),
            FakeProvider(),
            wid,
            request.id,
        )
    authority.claim()

    def erase() -> None:
        from sqlalchemy import event

        locks: list[str] = []

        def capture_lock(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
            if "FOR UPDATE" in statement or "FOR NO KEY UPDATE" in statement:
                locks.append(statement)

        event.listen(export_engine, "before_cursor_execute", capture_lock)
        try:
            with Session(export_engine) as db:
                process_event(db, configuration, "orders/delete", SHOP, {"id": 101}, NOW)
                assert db.scalar(select(func.count()).select_from(ShopifyOrder)) == 0
            if export_engine.dialect.name == "postgresql":
                assert locks and "FROM workspaces" in locks[0]
        finally:
            event.remove(export_engine, "before_cursor_execute", capture_lock)

    store = LocalMediaStore(tmp_path / "media")
    if phase == "build":
        capture = authority.capture_privacy

        def captured(snapshot: Session) -> dict[str, Any]:
            result = capture(snapshot)
            # A committed independent writer while the archive snapshot stays open.
            erase()
            return result

        authority.capture_privacy = captured  # type: ignore[method-assign]
        with pytest.raises(HTTPException, match="invalidated"):
            build(export_engine, authority, store)
        authority.finish(None)
    else:
        file, manifest = build(export_engine, authority, store)
        authority.finish(manifest)
        assert SLOTS.acquire(blocking=False)
        download = Download(file, authority)
        chunks = download.chunks()
        assert next(chunks)
        erase()
        with pytest.raises(HTTPException, match="invalidated"):
            next(chunks)
        assert file.closed


@pytest.mark.parametrize("operation", ["disconnect", "uninstall", "retention"])
def test_legacy_privacy_writers_advance_revision_on_closing_workspace(
    export_engine: Engine, configuration: Settings, operation: str
) -> None:
    from datetime import timedelta

    from app.shopify.models import ShopifyOrder
    from app.shopify.normalize import normalized_order
    from app.shopify.privacy import process_event, purge_expired_facts
    from app.shopify.security import Vault
    from app.shopify.service import ConnectionService
    from app.workspaces.models import Workspace
    from sqlalchemy import func, select

    from tests.test_shopify_sales import NOW, SHOP, connected, order

    with Session(export_engine) as db:
        row = connected(db, configuration)
        wid = row.workspace_id
        data = normalized_order(
            db, row, order(createdAt=(NOW - timedelta(days=60)).isoformat()), Vault(configuration)
        )
        db.add(ShopifyOrder(connection_id=row.id, workspace_id=wid, **data))
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.status = "closing"
        db.commit()
        before = workspace_export_revision(db, wid)
        db.rollback()
        if operation == "disconnect":
            ConnectionService(db, configuration).disconnect(wid, "owner")
        elif operation == "uninstall":
            process_event(db, configuration, "app/uninstalled", SHOP, {}, NOW)
        else:
            purge_expired_facts(export_engine, now=NOW)
        db.expire_all()
        assert workspace_export_revision(db, wid) > before
        assert db.scalar(select(func.count()).select_from(ShopifyOrder)) == 0


def test_meta_disconnect_fences_export_on_closing_scope(
    export_engine: Engine, meta_configuration: Settings  # noqa: F811
) -> None:
    from app.meta.models import MetaConnection
    from app.meta.service import ConnectionService
    from app.workspaces.models import Workspace

    from tests.test_meta_connection import connected

    with Session(export_engine) as db:
        row = connected(db, meta_configuration)
        wid = row.workspace_id
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.status = "closing"
        db.commit()
        before = workspace_export_revision(db, wid)
        ConnectionService(db, meta_configuration).disconnect(wid, "owner")
        assert workspace_export_revision(db, wid) > before
        assert db.get(MetaConnection, row.id) is None
