"""Concurrent first grants must not deadlock while upgrading workspace FK locks."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic

import pytest
from app.ads.models import AdvertisingAccount
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate
from app.meta import service as meta_service
from app.meta.locking import lock_workspace
from app.meta.models import MetaConnection, MetaPendingGrant
from app.meta.security import MetaError, Vault
from app.meta.service import ConnectionService
from app.settings import Settings
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_meta_connection import NOW, FakeMeta, authorized, workspace
from tests.test_meta_connection import configuration as configuration


def test_simultaneous_first_meta_connections_resolve_without_deadlock(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    with Session(customer_engine) as db:
        workspace_id = workspace(db).id
        for actor, account_id in [("alice", "101"), ("bob", "102")]:
            fake = FakeMeta(configuration)
            fake.account_id = account_id
            authorized(db, configuration, workspace_id, fake, actor)
    inserted, second_attempting, release = Event(), Event(), Event()
    backend_ids: dict[str, int] = {}
    original = AdvertisingMetricsRepository.upsert_account

    def synchronized_upsert(
        self: AdvertisingMetricsRepository,
        account: AdvertisingAccountCreate,
        *,
        workspace_id: int | None = None,
    ) -> AdvertisingAccount:
        result = original(self, account, workspace_id=workspace_id)
        # The workspace-first fence intentionally prevents a second concurrent insert.
        # Hold the winning transaction after its FK insert, before native publication.
        assert account.external_account_id == "101"
        inserted.set()
        assert release.wait(timeout=10)
        return result

    monkeypatch.setattr(AdvertisingMetricsRepository, "upsert_account", synchronized_upsert)
    original_lock = lock_workspace

    def observed_lock(db: Session, wid: int, *, skip_locked: bool = False) -> bool:
        if db.info.get("actor") == "bob":
            second_attempting.set()
        return original_lock(db, wid, skip_locked=skip_locked)

    monkeypatch.setattr(meta_service, "lock_workspace", observed_lock)

    def connect(pair: tuple[str, str]) -> str:
        actor, external_id = pair
        with Session(customer_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
            db.info["actor"] = actor
            backend_ids[actor] = db.scalar(text("SELECT pg_backend_pid()"))
            try:
                ConnectionService(db, configuration, FakeMeta(configuration)).select_account(
                    workspace_id,
                    actor,
                    external_id,
                    "purchase",
                    "owner",
                    NOW,
                )
            except MetaError as exc:
                return exc.code
            return "connected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(connect, ("alice", "101"))
        second = None
        try:
            assert inserted.wait(timeout=5)
            second = pool.submit(connect, ("bob", "102"))
            assert second_attempting.wait(timeout=5)
            deadline = monotonic() + 5
            blockers: list[int] = []
            while monotonic() < deadline:
                with customer_engine.connect() as observer:
                    blockers = observer.scalar(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": backend_ids["bob"]}
                    )
                if backend_ids["alice"] in blockers:
                    break
                Event().wait(0.01)
            assert backend_ids["alice"] in blockers
            assert not second.done()
        finally:
            release.set()
        assert first.result(timeout=10) == "connected"
        assert second is not None
        assert second.result(timeout=10) == "meta_disconnect_existing_first"
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(MetaConnection)) == 1
        assert db.scalar(select(func.count()).select_from(AdvertisingAccount)) == 1
        assert db.scalar(select(func.count()).select_from(WorkspaceIntegration)) == 1
        assert db.scalar(select(func.count()).select_from(MetaPendingGrant)) == 1
        row = db.scalar(select(MetaConnection))
        assert row and row.workspace_integration_id is not None
        assert row.external_account_id == "101"
        grant = db.scalar(select(MetaPendingGrant))
        assert grant and grant.actor_digest == Vault(configuration).digest("actor", "bob")
