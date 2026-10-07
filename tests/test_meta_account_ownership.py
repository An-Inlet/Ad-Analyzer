"""Retained Meta ownership and the cross-workspace database serialization boundary."""

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier, Event
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate
from app.meta.locking import lock_workspace
from app.meta.models import MetaConnection, MetaPendingGrant
from app.meta.security import MetaError
from app.meta.service import ConnectionService
from app.settings import Settings
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_meta_connection import NOW, FakeMeta, authorized, workspace
from tests.test_meta_connection import configuration as configuration

migration = import_module("migrations.versions.20261006_0049_meta_account_ownership")


def recheck(db: Session, wid: int) -> None:
    lock_workspace(db, wid)


def account(
    wid: int, platform: AdvertisingPlatform = AdvertisingPlatform.META_ADS
) -> AdvertisingAccountCreate:
    return AdvertisingAccountCreate(
        workspace_id=wid,
        platform=platform,
        external_account_id="101",
        name="Fixture",
        currency_code="USD",
        time_zone="UTC",
    )


def test_other_workspace_connect_disconnect_during_customer_io_is_rejected(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        a, b = workspace(db, "a").id, workspace(db, "b").id
        authorized(db, configuration, a, FakeMeta(configuration), "alice")
        authorized(db, configuration, b, FakeMeta(configuration), "bob")

    class Interleaved(FakeMeta):
        def account(self, account_id: str, token: str) -> dict[str, Any]:
            with Session(customer_engine) as other:
                service = ConnectionService(other, configuration, FakeMeta(configuration))
                service.select_account(b, "bob", "101", "purchase", "owner", NOW)
                service.disconnect(b, "owner")
            return super().account(account_id, token)

    with Session(customer_engine) as db:
        service = ConnectionService(db, configuration, Interleaved(configuration))
        with pytest.raises(MetaError, match="meta_account_already_connected"):
            service.select_account(
                a,
                "alice",
                "101",
                "purchase",
                "owner",
                NOW,
                before_persist=lambda: recheck(db, a),
            )
    with Session(customer_engine) as db:
        assert list(db.scalars(select(AdvertisingAccount.workspace_id))) == [b]
        assert db.scalar(select(func.count()).select_from(MetaConnection)) == 0
        assert db.scalar(select(func.count()).select_from(MetaPendingGrant)) == 1


def test_two_workspace_writers_serialize_at_meta_account_index(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL concurrent unique-index enforcement")
    with Session(customer_engine) as db:
        a, b = workspace(db, "race-a").id, workspace(db, "race-b").id
        authorized(db, configuration, a, FakeMeta(configuration), "alice")
    barrier = Barrier(2)
    inserted, release = Event(), Event()
    original = AdvertisingMetricsRepository.upsert_account
    conflicts: list[str] = []

    def insert(
        self: AdvertisingMetricsRepository,
        value: AdvertisingAccountCreate,
        *,
        workspace_id: int | None = None,
    ) -> AdvertisingAccount:
        barrier.wait(timeout=8)
        if value.workspace_id == a:
            assert inserted.wait(8)
        try:
            result = original(self, value, workspace_id=workspace_id)
        except IntegrityError as error:
            conflicts.append(str(getattr(getattr(error.orig, "diag", None), "constraint_name", "")))
            raise
        if value.workspace_id == b:
            inserted.set()
            assert release.wait(8)
        return result

    monkeypatch.setattr(AdvertisingMetricsRepository, "upsert_account", insert)

    def connect() -> str:
        with Session(customer_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '10s'"))
            try:
                ConnectionService(db, configuration, FakeMeta(configuration)).select_account(
                    a,
                    "alice",
                    "101",
                    "purchase",
                    "owner",
                    NOW,
                    before_persist=lambda: recheck(db, a),
                )
            except MetaError as exc:
                return exc.code
            return "connected"

    def historical_writer() -> None:
        with Session(customer_engine) as db:
            AdvertisingMetricsRepository(db).upsert_account(account(b))
            db.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(connect), pool.submit(historical_writer)
        try:
            assert inserted.wait(8)
            assert not first.done()
        finally:
            release.set()
        second.result(timeout=10)
        assert first.result(timeout=10) == "meta_account_already_connected"
    assert conflicts == ["uq_meta_external_account_owner"]
    with Session(customer_engine) as db:
        assert list(db.scalars(select(AdvertisingAccount.workspace_id))) == [b]
        assert db.scalar(select(func.count()).select_from(MetaConnection)) == 0
        assert db.scalar(select(func.count()).select_from(MetaPendingGrant)) == 1


@pytest.mark.parametrize("duplicate", [False, True])
def test_populated_migration_preserves_data_and_rejects_legacy_conflicts(
    customer_engine: Engine, duplicate: bool
) -> None:
    with customer_engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        migration.downgrade()  # Simulate the actual pre-0049 schema in an isolated fixture.
    with Session(customer_engine) as db:
        a, b = workspace(db, "migration-a").id, workspace(db, "migration-b").id
        AdvertisingMetricsRepository(db).upsert_account(account(a))
        if duplicate:
            AdvertisingMetricsRepository(db).upsert_account(account(b))
        # Other platforms retain their existing workspace-scoped identity policy.
        for wid in (a, b):
            AdvertisingMetricsRepository(db).upsert_account(
                account(wid, AdvertisingPlatform.GOOGLE_ADS)
            )
        db.commit()
        before = list(
            db.execute(
                select(
                    AdvertisingAccount.id,
                    AdvertisingAccount.workspace_id,
                    AdvertisingAccount.platform,
                )
            )
        )
    if duplicate:
        with (
            pytest.raises(RuntimeError, match="explicit reconciliation"),
            customer_engine.begin() as conn,
            Operations.context(MigrationContext.configure(conn)),
        ):
            migration.upgrade()
    else:
        with customer_engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        with Session(customer_engine) as db:
            with pytest.raises(IntegrityError):
                AdvertisingMetricsRepository(db).upsert_account(account(b))
            db.rollback()
        with customer_engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
            migration.upgrade()
    with Session(customer_engine) as db:
        after = list(
            db.execute(
                select(
                    AdvertisingAccount.id,
                    AdvertisingAccount.workspace_id,
                    AdvertisingAccount.platform,
                )
            )
        )
        assert after == before
