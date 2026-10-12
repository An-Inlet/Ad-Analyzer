"""Owned alias/marker membership and generic writer fences, entirely offline."""

import importlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.commerce.models import CommerceShopAlias, CommerceStore
from app.commerce.mutation_guards import TABLES, statements
from app.commerce.privacy import remove_store
from app.settings import Settings
from app.shopify.models import ShopifyPrivacyIdentity
from app.shopify.privacy_identity import markers, remember
from app.shopify.service import ConnectionService
from app.workspaces.locking import lock_workspace_row
from app.workspaces.models import Workspace, WorkspaceIntegration
from sqlalchemy import Engine, create_engine, delete, event, insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_commerce_measurement import setup
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration

A, B, C = "a" * 32, "b" * 32, "c" * 32
DOMAIN = "unmapped.myshopify.com"
W1, W2, W3 = 501, 502, 503


def store_values(sid: str, wid: int) -> dict[str, Any]:
    return dict(
        id=sid,
        workspace_id=wid,
        connection_id=wid,
        shop_key=sid * 2,
        shop_domain=f"{sid[0]}.myshopify.com",
        currency="USD",
        time_zone="UTC",
        connected_at=datetime.now(UTC),
    )


def seed(db: Session) -> None:
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON"))
        assert db.scalar(text("PRAGMA foreign_keys")) == 1
    for wid in (W1, W2, W3):
        db.add(Workspace(id=wid, slug=f"alias-{wid}", name="Alias fixture", client_name="Test"))
    db.flush()
    for wid in (W1, W2):
        db.add(
            WorkspaceIntegration(
                id=wid,
                workspace_id=wid,
                integration_key="shop",
                provider="shopify",
                display_name="Shop",
                status="active",
            )
        )
    db.flush()
    db.add_all(CommerceStore(**store_values(sid, wid)) for sid, wid in ((A, W1), (B, W1), (C, W2)))
    db.flush()
    remember(db, W1, DOMAIN, "order", "1" * 64)
    remember(db, W2, DOMAIN, "order", "2" * 64)
    remember(db, W3, DOMAIN, "order", "3" * 64)
    db.add(CommerceShopAlias(store_id=B, shop_domain="b.myshopify.com"))
    db.commit()


def applicable(db: Session, sid: str) -> set[str]:
    store = db.get(CommerceStore, sid)
    assert store
    return {marker.object_key for marker in markers(db, store)}


def rows(db: Session) -> dict[str, list[tuple[Any, ...]]]:
    return {
        model.__tablename__: sorted(
            (tuple(row) for row in db.execute(select(model.__table__))), key=repr
        )
        for model in (CommerceStore, CommerceShopAlias, ShopifyPrivacyIdentity)
    }


def test_cross_store_membership_and_delete_is_not_disconnect(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        seed(db)
        assert applicable(db, A) == {"1" * 64}
        db.add(CommerceShopAlias(store_id=C, shop_domain=DOMAIN))
        db.commit()
        assert applicable(db, A) == {"1" * 64}  # Different workspace cannot classify it.
        db.add(CommerceShopAlias(store_id=B, shop_domain=DOMAIN))
        db.commit()
        assert applicable(db, A) == set()
        assert applicable(db, B) == {"1" * 64}
        before = rows(db)
        remove_store(db, B)
        db.commit()
        assert db.get(CommerceStore, B) is not None
        assert applicable(db, A) == set()  # Revocation retains verified aliases.
        retained = rows(db)
        assert retained[CommerceShopAlias.__tablename__] == before[CommerceShopAlias.__tablename__]
        assert (
            retained[ShopifyPrivacyIdentity.__tablename__]
            == before[ShopifyPrivacyIdentity.__tablename__]
        )
        db.execute(delete(CommerceStore).where(CommerceStore.id == B))
        assert db.get(CommerceShopAlias, (DOMAIN, B)) is None
        assert applicable(db, A) == {"1" * 64}
        db.rollback()
        assert rows(db) == retained
        db.execute(delete(CommerceStore).where(CommerceStore.id == B))
        db.commit()
        assert applicable(db, A) == {"1" * 64}
        assert applicable(db, C) == {"2" * 64}
        # Workspace-owned marker cascade has no store/integration in this workspace.
        db.execute(delete(Workspace).where(Workspace.id == W3))
        db.commit()
        assert db.get(ShopifyPrivacyIdentity, (W3, DOMAIN, "order", "3" * 64)) is None
        assert applicable(db, A) == {"1" * 64}


def test_actual_disconnect_retains_store_alias_and_identity(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        if customer_engine.dialect.name == "sqlite":
            db.execute(text("PRAGMA foreign_keys=ON"))
            assert db.scalar(text("PRAGMA foreign_keys")) == 1
        native, store = setup(db, configuration)
        sid, wid = store.id, store.workspace_id
        remember(db, wid, native.shop_domain, "order", "9" * 64)
        db.commit()
        before = rows(db)
        ConnectionService(db, configuration).disconnect(wid, "owner")
        db.expire_all()
        retained = db.get(CommerceStore, sid)
        assert retained and retained.status == "revoked"
        after = rows(db)
        assert after[CommerceShopAlias.__tablename__] == before[CommerceShopAlias.__tablename__]
        assert (
            after[ShopifyPrivacyIdentity.__tablename__]
            == before[ShopifyPrivacyIdentity.__tablename__]
        )


def test_generic_mutations_and_cascades_respect_both_owners(
    customer_engine: Engine, tmp_path: Path
) -> None:
    engine = customer_engine
    with Session(engine) as db:
        seed(db)
    copied = engine.dialect.name == "sqlite"
    if copied:
        path = tmp_path / "alias-fences.db"
        with engine.connect() as connection, closing(sqlite3.connect(path)) as destination:
            driver = connection.connection.driver_connection
            assert driver is not None
            driver.backup(destination)
        engine = create_engine(
            f"sqlite:///{path}", poolclass=NullPool, connect_args={"timeout": 0.1}
        )

        @event.listens_for(engine, "connect")
        def foreign_keys(connection: Any, _record: Any) -> None:
            connection.execute("PRAGMA foreign_keys=ON")
            assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    changes = [
        insert(CommerceStore).values(**store_values("d" * 32, W1)),
        update(CommerceStore).where(CommerceStore.id == B).values(status="revoked"),
        delete(CommerceStore).where(CommerceStore.id == B),
        insert(CommerceShopAlias).values(store_id=B, shop_domain=DOMAIN),
        update(CommerceShopAlias).where(CommerceShopAlias.store_id == B).values(shop_domain=DOMAIN),
        delete(CommerceShopAlias).where(CommerceShopAlias.store_id == B),
        insert(ShopifyPrivacyIdentity).values(
            workspace_id=W1, shop_domain=DOMAIN, kind="customer", object_key="4" * 64
        ),
        update(ShopifyPrivacyIdentity)
        .where(ShopifyPrivacyIdentity.workspace_id == W1)
        .values(pending_legacy=True),
        delete(ShopifyPrivacyIdentity).where(ShopifyPrivacyIdentity.workspace_id == W1),
    ]
    moves = [
        update(CommerceStore)
        .where(CommerceStore.id == B)
        .values(workspace_id=W2, connection_id=W2),
        update(CommerceShopAlias).where(CommerceShopAlias.store_id == B).values(store_id=C),
        update(ShopifyPrivacyIdentity)
        .where(ShopifyPrivacyIdentity.workspace_id == W1)
        .values(workspace_id=W2),
    ]
    try:
        with Session(engine) as db:
            before = rows(db)
        for owner, statement in [(W1, s) for s in changes] + [
            (w, s) for w in (W1, W2) for s in moves
        ]:
            with Session(engine) as reader:
                if copied:
                    reader.execute(text("BEGIN IMMEDIATE"))
                assert lock_workspace_row(reader, owner)
                with Session(engine) as writer:
                    with pytest.raises(DBAPIError) as error:
                        writer.execute(statement)
                        writer.flush()
                    if copied:
                        assert "database is locked" in str(error.value)
                    else:
                        assert getattr(error.value.orig, "sqlstate", None) == "55P03"
                    writer.rollback()
                reader.rollback()
            with Session(engine) as writer:
                assert rows(writer) == before
                writer.execute(statement)
                writer.flush()
                writer.rollback()
                assert rows(writer) == before
        alias_insert = insert(CommerceShopAlias).values(store_id=B, shop_domain=DOMAIN)
        store_move = moves[0]
        store_delete = delete(CommerceStore).where(CommerceStore.id == B)
        for first, second in (
            (alias_insert, store_move),
            (store_move, alias_insert),
            (alias_insert, store_delete),
            (store_delete, alias_insert),
        ):
            with Session(engine) as holder:
                holder.execute(first)
                holder.flush()
                with Session(engine) as competitor:
                    if not copied:
                        competitor.execute(text("SET LOCAL lock_timeout = '150ms'"))
                    with pytest.raises(DBAPIError) as error:
                        competitor.execute(second)
                    if copied:
                        assert "database is locked" in str(error.value)
                    else:
                        assert getattr(error.value.orig, "sqlstate", None) == "55P03"
                    competitor.rollback()
                holder.rollback()
            with Session(engine) as db:
                assert rows(db) == before
    finally:
        if copied:
            engine.dispose()


def test_populated_migration_parity_and_reversible_guards(
    migration_customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20261012_0094_commerce_mutation_guards"
    )
    assert migration.TABLES == TABLES
    assert tuple(sql for table in TABLES for sql in statements(table)) == migration.SQL
    engine = migration_customer_engine
    with Session(engine) as db:
        seed(db)
        before = rows(db)
    with engine.begin() as connection, monkeypatch.context() as patch:
        patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.downgrade()
        migration.upgrade()
    with Session(engine) as db:
        assert rows(db) == before
        db.execute(update(Workspace).where(Workspace.id == W1).values(status="closing"))
        remember(db, W1, DOMAIN, "customer", "8" * 64)
        db.flush()
        db.rollback()
        assert rows(db) == before
        # A populated workspace may have restrictive integration dependencies.
        # Accept only its actual FK refusal or a complete owned cascade, atomically.
        try:
            db.execute(delete(Workspace).where(Workspace.id == W1))
        except IntegrityError as error:
            cascade_outcome = "foreign_key_refusal"
            if engine.dialect.name == "postgresql":
                assert getattr(error.orig, "sqlstate", None) == "23503"
            else:
                assert "FOREIGN KEY constraint failed" in str(error)
            db.rollback()
        else:
            cascade_outcome = "complete_owned_cascade"
            assert db.get(CommerceStore, A) is None
            assert db.get(CommerceStore, B) is None
            assert db.get(CommerceShopAlias, ("b.myshopify.com", B)) is None
            assert db.get(ShopifyPrivacyIdentity, (W1, DOMAIN, "order", "1" * 64)) is None
            db.rollback()
        assert rows(db) == before
        db.execute(delete(CommerceStore).where(CommerceStore.id == B))
        db.rollback()
        assert rows(db) == before

    (tmp_path / "commerce-cascade-outcome.json").write_text(
        json.dumps(
            {
                "backend": engine.dialect.name,
                "workspace_delete": cascade_outcome,
                "migration_data_unchanged": True,
                "rollback_rows_restored": True,
            }
        )
        + "\n"
    )
