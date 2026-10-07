"""Populated native pg_dump/restore, immutable lineage and safe migration downgrade."""

import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionAttempt,
    ProviderExposureReservation,
)
from app.publication.google_completion import read_owned
from app.settings import Settings, settings
from scripts.inlet_restore_drill import PostgresTools, fingerprint, target
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_google_completion_evidence import emitted
from tests.test_shopify_sales import configuration as configuration


def test_native_completion_migration_restore(
    configuration: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    container = os.environ.get("INLET_RESTORE_POSTGRES_CONTAINER")
    if not container and not all(shutil.which(p) for p in ("pg_dump", "pg_restore", "psql")):
        if os.environ.get("CI") == "true":
            pytest.fail("native PostgreSQL tools required in CI")
        pytest.skip("native tools or explicit local test container required")
    url = target()
    admin = create_engine(url)
    schema = "inlet_completion_" + uuid4().hex
    engine = create_engine(url.update_query_dict({"options": f"-csearch_path={schema}"}))
    tools = PostgresTools(url, container)
    with admin.begin() as db:
        tools.prove_server(db)
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
        db.execute(text(f'REVOKE ALL ON SCHEMA "{schema}" FROM PUBLIC'))
    monkeypatch.setattr(settings, "database_url", engine.url.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0066")
        command.downgrade(config, "20261006_0060")
        assert "google_original_completions" not in inspect(engine).get_table_names()
        command.upgrade(config, "20261006_0066")
        # Composed current helpers also use sibling candidate/billing schemas.
        # Keep the exact 0066 roundtrip above, then populate the actual full schema.
        command.upgrade(config, "heads")
        with Session(engine) as db:
            wid, actor, attempt = emitted(db, configuration, tmp_path)
            original = read_owned(db, wid, attempt, actor, NOW)
            assert original is not None
            holds = [
                (r.id, r.amount_micros, r.state)
                for r in db.scalars(select(ProviderExposureReservation))
            ]
            db.rollback()
            with pytest.raises(IntegrityError):
                db.execute(
                    text("UPDATE google_original_completions SET workspace_id=workspace_id+1000")
                )
                db.commit()
            db.rollback()
            with pytest.raises(IntegrityError):
                db.delete(db.get(ProviderExecutionAttempt, attempt))
                db.commit()
            db.rollback()
        with pytest.raises(RuntimeError, match="cannot be discarded"):
            command.downgrade(config, "20261006_0060")
        with engine.connect() as db:
            before = fingerprint(db, schema)
        archive = tools.run("pg_dump", ["--format=custom", "--no-owner", f"--schema={schema}"])
        assert archive.startswith(b"PGDMP") and len(archive) <= 20_000_000
        engine.dispose()
        with admin.begin() as db:
            tools.prove_server(db)
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        tools.run(
            "pg_restore", ["--exit-on-error", "--no-owner", f"--dbname={url.database}"], archive
        )
        with engine.connect() as db:
            assert fingerprint(db, schema) == before
        with Session(engine) as db:
            restored = read_owned(db, wid, attempt, actor, NOW)
            assert restored == original
            assert db.get(GoogleOriginalCompletion, attempt) is not None
            assert [
                (r.id, r.amount_micros, r.state)
                for r in db.scalars(select(ProviderExposureReservation))
            ] == holds
            assert all(state == "held" for _, _, state in holds)
        with engine.connect() as db:
            assert fingerprint(db, schema) == before
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
