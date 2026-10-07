"""Frozen 0082 DDL on populated parents, immutable scope and private staging export."""

import importlib
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.commerce.acquisition_models import CommerceAcquisitionCheckpoint as Checkpoint
from app.commerce.acquisition_models import CommerceAcquisitionJob as Job
from app.lifecycle.export_serializers import serialize
from app.lifecycle.inventory import verify_registry
from app.lifecycle.local_work import verify_work_registry
from app.settings import Settings
from sqlalchemy import Engine, delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_commerce_acquisition_jobs import configured
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_independent_publications import ready
from tests.test_shopify_sales import configuration as configuration


def test_populated_additive_migration_roundtrip(
    migration_customer_engine: Engine, configuration: Settings
) -> None:
    engine = migration_customer_engine
    migration = importlib.import_module("migrations.versions.20261007_0082_commerce_acquisition")
    # This migration adds only new leaf tables, no rebuild/stamp or old-parent rewrite.
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
    owned, request, _, _, _, _ = ready(engine, configuration, None)
    with engine.connect() as connection:
        before = [
            dict(r)
            for r in connection.execute(
                text("SELECT * FROM commerce_measurement_publications")
            ).mappings()
        ]
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
        assert [
            dict(r)
            for r in connection.execute(
                text("SELECT * FROM commerce_measurement_publications")
            ).mappings()
        ] == before
        migration.downgrade()
        migration.upgrade()
    assert owned.authority(request, owned.clock()).active


def test_actual_owned_job_immutable_private_export_and_nonempty_downgrade(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    _, _, _, client, _, prefix, headers, intent = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    response = client.post(prefix, json=intent, headers=headers)
    assert response.status_code == 200, response.text
    identifier = response.json()["job_id"]
    verify_registry()
    verify_work_registry()
    with Session(customer_engine) as db:
        job = db.get(Job, identifier)
        checkpoint = db.get(Checkpoint, identifier)
        assert job is not None and checkpoint is not None
        for table, value in [
            ("commerce_acquisition_jobs", job),
            ("commerce_acquisition_checkpoints", checkpoint),
        ]:
            raw = {column.name: getattr(value, column.name) for column in value.__table__.columns}
            exported, missing = serialize(table, raw)
            assert not missing
            assert not {
                "session_digest",
                "authenticated_at",
                "identity_digest",
                "request",
                "profile",
                "state_document",
                "state_digest",
                "encrypted_handles",
            } & set(exported)
        with pytest.raises(DBAPIError):
            db.execute(update(Job).where(Job.id == identifier).values(profile_digest="0" * 64))
            db.commit()
        db.rollback()
    migration = importlib.import_module("migrations.versions.20261007_0082_commerce_acquisition")
    with (
        customer_engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
        pytest.raises(RuntimeError, match="cannot discard"),
    ):
        migration.downgrade()
    with Session(customer_engine) as db:
        db.execute(delete(Job).where(Job.id == identifier))
        db.commit()
        assert db.scalar(select(Checkpoint).where(Checkpoint.job_id == identifier)) is None


def test_frozen_migration_guard_inventory_matches_current_contract() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.commerce.acquisition_guards import statements

    migration = importlib.import_module("migrations.versions.20261007_0082_commerce_acquisition")
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert len(scripts.get_heads()) == 1
    # Later additive migrations must retain 0082 in the current ancestry; they
    # do not change its frozen guard contract or make it the latest head again.
    assert migration.revision in {revision.revision for revision in scripts.walk_revisions()}
    revision = scripts.get_revision(migration.revision)
    assert revision is not None and revision.down_revision == "20261007_0081"
    for dialect in ("sqlite", "postgresql"):
        guards = statements(dialect)
        assert migration.SQL[dialect][-len(guards) :] == guards
        names = {
            line.split()[5] for line in guards if line.startswith("CREATE TRIGGER IF NOT EXISTS")
        }
        if dialect == "sqlite":
            assert names == {name for name, _ in migration.TRIGGERS}
