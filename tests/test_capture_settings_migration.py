"""Actual forward binding migration, preserving populated historical captures."""

import importlib
import json
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.campaign_performance.selected_models import SelectedCaptureRow
from app.campaign_performance.selected_storage import (
    read_selected_capture,
    store_selected_capture,
    store_selection,
)
from app.campaign_performance.selected_triggers import statements
from app.settings import Settings
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import configured as configured
from tests.test_meta_connection import configuration as configuration
from tests.test_selected_capture_api import prepare
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_customer_api import customer as customer
from tests.test_selected_storage import ready


@pytest.fixture()
def customer_engine(migration_customer_engine: Engine) -> Engine:
    return migration_customer_engine


def test_actual0093_preserves_legacy_capture_and_fences(
    migration_customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = migration_customer_engine
    module = importlib.import_module("migrations.versions.20261012_0093_capture_settings")
    original = importlib.import_module("migrations.versions.20261011_0091_selected_reporting")
    dialect = engine.dialect.name
    for ddl in module.PRIOR_SQL[dialect]:
        assert ddl in original.SQL[dialect]
    for ddl in statements("selected_reporting_captures", dialect):
        assert ddl in module.SQL[dialect] or ddl in original.SQL[dialect]
    with engine.begin() as connection:
        if dialect == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    with Session(engine) as db:
        _source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        snapshot = connection.execute(text("SELECT * FROM selected_reporting_captures")).all()
        assert len(snapshot) == 1
        module.downgrade()
        assert (
            connection.execute(text("SELECT * FROM selected_reporting_captures")).all() == snapshot
        )
        module.upgrade()
        assert (
            connection.execute(text("SELECT * FROM selected_reporting_captures")).all() == snapshot
        )
    with Session(engine) as db:
        assert (
            read_selected_capture(
                db,
                capture.request.aggregate.scope.workspace_id,
                capture.request.aggregate.scope.account_id,
                capture.request.capture_id,
            )
            == capture
        )


def test_forward_binding_rejects_mixed_versions_and_keeps_header_byte_limit(
    customer: CustomerFixture,
) -> None:
    import importlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import insert
    from sqlalchemy.exc import DBAPIError

    f = customer
    migration = importlib.import_module("migrations.versions.20261012_0093_capture_settings")
    with f.engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        migration.upgrade()
    body = prepare(f)
    response = f.post("/captures", body)
    assert response.status_code == 200, response.text
    with (
        f.engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
        pytest.raises(RuntimeError, match="reader-capable migration0093"),
    ):
        migration.downgrade()
    with Session(f.engine) as db:
        original = db.get(SelectedCaptureRow, body["request_id"])
        assert original
        values = {c.name: getattr(original, c.name) for c in original.__table__.columns}
        retained = original.canonical_json
        for attack in ("capture1", "request1", "absent", "null", "list", "unknown", "oversize"):
            candidate = dict(values, id=uuid4().hex)
            header = json.loads(retained)
            header["request"]["capture_id"] = candidate["id"]
            if attack == "capture1":
                header["schema_version"] = "inlet.selected-capture.v1"
            elif attack == "request1":
                header["request"]["schema_version"] = "inlet.selected-capture-request.v1"
            elif attack == "absent":
                header["request"].pop("settings")
            elif attack in {"null", "list"}:
                header["request"]["settings"] = None if attack == "null" else []
            elif attack == "unknown":
                header["request"]["settings"]["schema_version"] = "inlet.capture-settings.v99"
            payload = json.dumps(header)
            if attack == "oversize":
                payload += " " * (16385 - len(payload.encode()))
            candidate.update(canonical_json=payload, payload_bytes=len(payload.encode()))
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(insert(SelectedCaptureRow), candidate)
        # Exercise the database byte fence independently of DTO/canonical validation.
        candidate = dict(values, id=uuid4().hex)
        header = json.loads(retained)
        header["request"]["capture_id"] = candidate["id"]
        payload = json.dumps(header)
        payload += " " * (16384 - len(payload.encode()))
        candidate.update(canonical_json=payload, payload_bytes=len(payload.encode()))
        savepoint = db.begin_nested()
        db.execute(insert(SelectedCaptureRow), candidate)
        savepoint.rollback()
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 1
        reread = db.get(SelectedCaptureRow, body["request_id"])
        assert reread is not None and reread.canonical_json == retained
