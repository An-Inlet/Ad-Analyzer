"""Actual0088 DDL: ownership/bindings/immutability and erasable receipt graph."""

import importlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.ads.models import AdvertisingAccount
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.lifecycle.inventory import verify_registry
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import Engine, delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_planning_document_storage import rows

pytestmark = pytest.mark.planning_boundary


def seed(db: Session, wid: int) -> tuple[dict[str, Any], dict[str, Any]]:
    inputs, _ = rows(db, wid)
    if db.get(CustomerUser, inputs.actor_id) is None:
        db.add(
            CustomerUser(
                id=inputs.actor_id, issuer="test", subject="test", email="test@example.invalid"
            )
        )
        db.flush()
    db.add(CustomerMembership(user_id=inputs.actor_id, workspace_id=wid, role="owner"))
    db.add(
        CustomerSession(
            digest=f"{wid:064x}",
            user_id=inputs.actor_id,
            csrf_digest="e" * 64,
            created_at=123,
            authenticated_at=123,
            expires_at=9999999999,
        )
    )
    integration = WorkspaceIntegration(
        workspace_id=wid,
        integration_key="test",
        provider="google_ads",
        display_name="Test",
        status="active",
    )
    db.add(integration)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=wid,
        connection_id=integration.id,
        platform="google_ads",
        external_account_id=str(wid),
        name="Test",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    now = datetime.now(UTC)
    header = dict(
        workspace_id=wid,
        id=f"{wid + 1000:032x}",
        account_id=account.id,
        connection_id=integration.id,
        actor_id=inputs.actor_id,
        session_digest=f"{wid:064x}",
        authenticated_at=123,
        privacy_revision=0,
        source_revision="1",
        source_binding_digest="b" * 64,
        payload_schema="inlet.planning-catalog-receipt.v1",
        canonical_json="{}",
        payload_digest="c" * 64,
        payload_bytes=2,
        composite_digest=f"{wid:064x}",
        target_count=1,
        reporting_starts_at=now - timedelta(days=2),
        reporting_ends_at=now - timedelta(days=1),
        observation_started_at=now - timedelta(seconds=1),
        observed_at=now,
        expires_at=now + timedelta(hours=1),
        created_at=now,
    )
    link = dict(
        workspace_id=wid,
        plan_id=inputs.plan_id,
        input_revision=1,
        account_id=account.id,
        receipt_id=header["id"],
        connection_id=integration.id,
        composite_digest=header["composite_digest"],
        input_digest=inputs.digest,
        selected_keys_digest="d" * 64,
        selected_count=1,
        created_at=now,
    )
    return header, link


def actual_ddl(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Any:
    migration = importlib.import_module("migrations.versions.20261008_0088_catalog_receipts")
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            for name in reversed(migration.TABLES):
                connection.execute(text(f"DROP TABLE {name}"))
            connection.execute(text("PRAGMA foreign_keys=ON"))
            with monkeypatch.context() as patch:
                patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
                migration.upgrade()
    return migration


def test_actual0088_owned_bindings_immutability_erasure_and_downgrade(
    migration_customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = migration_customer_engine
    migration = actual_ddl(engine, monkeypatch)
    with Session(engine) as db:
        first, link = seed(db, 501)
        other, _ = seed(db, 502)
        db.add_all((CatalogReceiptRow(**first), CatalogReceiptRow(**other)))
        db.flush()
        selection = dict(
            workspace_id=501,
            account_id=first["account_id"],
            selection_key="a" * 64,
            receipt_id=first["id"],
            connection_id=first["connection_id"],
            canonical_entity_key="b" * 64,
        )
        db.add(CatalogReceiptSelectionRow(**selection))
        db.commit()
        verify_registry()
        variants = (
            {"account_id": other["account_id"], "connection_id": other["connection_id"]},
            {"actor_id": "f" * 32},
            {"session_digest": "f" * 64},
            {"authenticated_at": 124},
            {"payload_bytes": 1},
            {"payload_bytes": 1048577},
            {"target_count": 401},
            {"privacy_revision": -1},
            {"created_at": first["expires_at"]},
            {"reporting_ends_at": first["expires_at"]},
        )
        for index, change in enumerate(variants):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.add(
                    CatalogReceiptRow(
                        **{
                            **first,
                            "id": f"{9000 + index:032x}",
                            "composite_digest": f"{9000 + index:064x}",
                            **change,
                        }
                    )
                )
                db.flush()
        for change in (
            {"input_digest": "f" * 64},
            {"composite_digest": "f" * 64},
            {"created_at": first["expires_at"]},
            {"selected_count": 0},
            {"receipt_id": other["id"]},
            {"input_revision": 2},
        ):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.add(InputCatalogReceiptRow(**{**link, **change}))
                db.flush()
        db.add(InputCatalogReceiptRow(**link))
        db.flush()
        for model, field in (
            (CatalogReceiptRow, "payload_digest"),
            (CatalogReceiptSelectionRow, "canonical_entity_key"),
            (InputCatalogReceiptRow, "input_digest"),
        ):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(
                    update(model).where(model.workspace_id == 501).values(**{field: "e" * 64})
                )
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(delete(CatalogReceiptRow).where(CatalogReceiptRow.workspace_id == 501))
        # Receipt provenance does not retain/revive authentication sessions.
        db.execute(delete(CustomerSession).where(CustomerSession.digest == first["session_digest"]))
        assert db.scalar(select(func.count()).select_from(CatalogReceiptRow)) == 2
        db.commit()
    with engine.begin() as connection, monkeypatch.context() as patch:
        patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        with pytest.raises(RuntimeError, match="cannot discard"):
            migration.downgrade()
    with Session(engine) as db:
        bump_workspace_export_revision(db, 501)
        db.commit()
        for model in (CatalogReceiptRow, CatalogReceiptSelectionRow, InputCatalogReceiptRow):
            assert (
                db.scalar(select(func.count()).select_from(model).where(model.workspace_id == 501))
                == 0
            )
        assert (
            db.scalar(
                select(func.count())
                .select_from(CatalogReceiptRow)
                .where(CatalogReceiptRow.workspace_id == 502)
            )
            == 1
        )
        bump_workspace_export_revision(db, 502)
        db.commit()
    with engine.begin() as connection, monkeypatch.context() as patch:
        patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.downgrade()
        migration.upgrade()
