"""0086 actual DDL, owned inserts, erasable planning record and nonlossy downgrade."""

import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.database.session import Base
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.export_serializers import serialize
from app.lifecycle.inventory import predicate
from app.lifecycle.registry import TABLES
from app.settings import Settings
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.budget_mandate_fixture import first_customer
from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_consents import confirm
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.fixture
def customer_engine(migration_customer_engine: Engine) -> Engine:
    return migration_customer_engine


def test_real_0086_ownership_export_erasure_and_downgrade(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    migration = importlib.import_module("migrations.versions.20261008_0086_planning_consents")
    if customer_engine.dialect.name == "sqlite":
        # Fixture uses ORM for old SQLite migrations; apply this exact frozen0086 DDL.
        with customer_engine.begin() as connection:
            connection.execute(text("DROP TABLE initial_planning_consents"))
            with monkeypatch.context() as patch:
                patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
                migration.upgrade()
    client, root, body, _, _, _, wid, _ = first_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    confirm(client, root, body)
    with Session(customer_engine) as db:
        row = db.scalar(select(PlanningConsentRow))
        assert row
        values = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        exported, omitted = serialize("initial_planning_consents", values)
        assert not omitted and exported["preparation_digest"] == row.preparation_digest
        assert not TABLES["initial_planning_consents"].protected
    # Exercise the actual authenticated consistent-snapshot archive builder, not
    # only a serializer projection of the new scalar table.
    from app.campaign_review.storage import LocalMediaStore
    from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
    from app.customers.models import CustomerSession, CustomerUser
    from app.lifecycle.contracts import LifecycleInputV1
    from app.lifecycle.exports import Authority
    from app.lifecycle.service import begin
    from app.settings import settings

    from tests.test_customer_exports import build, unpack

    monkeypatch.setattr(settings, "customer_export_enabled", True)
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, digest(client.cookies[SESSION_COOKIE]))
        assert session
        user = db.get(CustomerUser, session.user_id)
        assert user
        principal = CustomerPrincipal(user, session)
        request = begin(
            db,
            principal,
            replicas[2],
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "planning-confirmation-export",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(customer_engine, principal, replicas[2], wid, request.id)
    authority.claim()
    archive, _ = build(customer_engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, entries = unpack(archive)
        section = next(v for k, v in entries.items() if "initial_planning_consents" in k)
        assert values["preparation_digest"].encode() in section
    finally:
        archive.close()
    with pytest.raises(DBAPIError), customer_engine.begin() as connection:
        connection.execute(text("UPDATE initial_planning_consents SET actor=actor"))
    with customer_engine.begin() as connection, monkeypatch.context() as patch:
        patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        with pytest.raises(RuntimeError, match="cannot discard retained planning"):
            migration.downgrade()
    table = Base.metadata.tables["initial_planning_consents"]
    with Session(customer_engine) as db:
        # Exact lifecycle predicate cannot erase another workspace's confirmation.
        db.execute(
            delete(table).where(predicate(table.name, LifecycleScopeV1(workspace_id=wid + 1)))
        )
        db.commit()
        assert db.scalar(select(PlanningConsentRow)) is not None
        db.execute(delete(table).where(predicate(table.name, LifecycleScopeV1(workspace_id=wid))))
        db.commit()
        assert db.scalar(select(PlanningConsentRow)) is None
    for change in (
        {"workspace_id": wid + 1},
        {"policy_digest": "f" * 64},
        {"preparation_digest": "e" * 64},
        {"mandate_revision": 99},
    ):
        with pytest.raises(DBAPIError), customer_engine.begin() as connection:
            connection.execute(table.insert().values(**{**values, **change}))
    with customer_engine.begin() as connection:
        with monkeypatch.context() as patch:
            patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.downgrade()
            migration.upgrade()
        assert connection.scalar(text("SELECT COUNT(*) FROM initial_planning_consents")) == 0
