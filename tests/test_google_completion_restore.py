"""Populated native pg_dump/restore, immutable lineage and safe migration downgrade."""

import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app import advertising_capabilities
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

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("purpose", ["optimization", "creation"])
def test_native_completion_migration_restore(
    configuration: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, purpose: str
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
    from app.publication import coordinator
    from app.publication.google_execution_completion import read_execution_completion
    from app.publication.service import owner

    from tests.test_provider_coordinator import GoogleServer, ready

    def emit(db: Session) -> tuple[int, str, str]:
        if purpose == "optimization":
            result = emitted(db, configuration, tmp_path)
            return result[0], result[1], result[2]
        wid, run, actor, store, runtime = ready(db, configuration, tmp_path, GoogleServer())
        claim = coordinator.claim_creation_step(db, wid, run, actor, store, runtime, lambda: NOW)
        assert claim is not None
        coordinator.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        return wid, actor, claim.attempt_id

    def read(db: Session, wid: int, attempt: str, actor: str) -> str:
        if purpose == "optimization":
            old = read_owned(db, wid, attempt, actor, NOW)
            assert old is not None
            return old.digest()
        projection = read_execution_completion(
            db, wid, attempt, actor, authorize=lambda: owner(db, wid, actor), clock=lambda: NOW
        )
        assert projection.status == "completed" and projection.commitment is not None
        return projection.commitment

    url = target()
    admin = create_engine(url)
    schema = "inlet_completion_" + uuid4().hex
    engine = create_engine(url.update_query_dict({"options": f"-csearch_path={schema}"}))
    tools = PostgresTools(url, container)
    with admin.begin() as connection:
        tools.prove_server(connection)
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'REVOKE ALL ON SCHEMA "{schema}" FROM PUBLIC'))
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
            with monkeypatch.context() as historical:
                historical.setattr(
                    advertising_capabilities, "require_advertising_write", lambda: None
                )
                wid, actor, attempt = emit(db)
            with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
                advertising_capabilities.require_advertising_write()
            original = read(db, wid, attempt, actor)
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
        with engine.connect() as connection:
            before = fingerprint(connection, schema)
        archive = tools.run("pg_dump", ["--format=custom", "--no-owner", f"--schema={schema}"])
        assert archive.startswith(b"PGDMP") and len(archive) <= 20_000_000
        engine.dispose()
        with admin.begin() as connection:
            tools.prove_server(connection)
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        tools.run(
            "pg_restore", ["--exit-on-error", "--no-owner", f"--dbname={url.database}"], archive
        )
        with engine.connect() as connection:
            assert fingerprint(connection, schema) == before
        with Session(engine) as db:
            restored = read(db, wid, attempt, actor)
            assert restored == original
            assert db.get(GoogleOriginalCompletion, attempt) is not None
            assert [
                (r.id, r.amount_micros, r.state)
                for r in db.scalars(select(ProviderExposureReservation))
            ] == holds
            assert all(state == "held" for _, _, state in holds)
        with engine.connect() as connection:
            assert fingerprint(connection, schema) == before
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
