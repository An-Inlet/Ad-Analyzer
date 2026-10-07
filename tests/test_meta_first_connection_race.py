"""Concurrent first grants must not deadlock while upgrading workspace FK locks."""

from concurrent.futures import Future, ThreadPoolExecutor
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
    assert_connections_serialize(customer_engine, configuration, monkeypatch)


def test_delayed_first_meta_connection_still_serializes(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Starting a worker is not a product latency guarantee. Exercise a delay
    # beyond the old five-second startup watchdog before any database work.
    assert_connections_serialize(customer_engine, configuration, monkeypatch, startup_delay=6)


def test_first_connection_worker_failure_is_reported(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return

    def failed_upsert(
        self: AdvertisingMetricsRepository,
        account: AdvertisingAccountCreate,
        *,
        workspace_id: int | None = None,
    ) -> AdvertisingAccount:
        raise RuntimeError("synthetic first-worker failure")

    monkeypatch.setattr(AdvertisingMetricsRepository, "upsert_account", failed_upsert)
    with pytest.raises(RuntimeError, match="synthetic first-worker failure"):
        assert_connections_serialize(customer_engine, configuration, monkeypatch)


def assert_connections_serialize(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    *,
    startup_delay: float = 0,
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
    stages: dict[str, float] = {}
    started = monotonic()
    # One main-thread deadline, shorter than either worker watchdog. The old
    # independent 5s + 5s waits competed with the winner's 10s release timeout.
    deadline = started + 30

    def reached(stage: str) -> None:
        stages[stage] = round(monotonic() - started, 3)

    def await_stage(event: Event, worker: Future[str], stage: str) -> None:
        while not event.is_set():
            if worker.done():
                # Surface the original worker exception rather than replacing
                # it with a misleading event timeout.
                worker.result()
                pytest.fail(f"worker finished before {stage}; stages={stages}")
            remaining = deadline - monotonic()
            assert remaining > 0, f"timed out before {stage}; stages={stages}"
            event.wait(min(0.1, remaining))

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
        reached("first_inserted")
        inserted.set()
        assert release.wait(timeout=45), f"winner release timeout; stages={stages}"
        return result

    monkeypatch.setattr(AdvertisingMetricsRepository, "upsert_account", synchronized_upsert)
    original_lock = lock_workspace

    def observed_lock(db: Session, wid: int, *, skip_locked: bool = False) -> bool:
        if db.info.get("actor") == "bob":
            reached("second_attempting")
            second_attempting.set()
        return original_lock(db, wid, skip_locked=skip_locked)

    monkeypatch.setattr(meta_service, "lock_workspace", observed_lock)

    def connect(pair: tuple[str, str]) -> str:
        actor, external_id = pair
        if actor == "alice" and startup_delay:
            Event().wait(startup_delay)
        reached(f"{actor}_started")
        with Session(customer_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '40s'"))
            db.execute(text("SET LOCAL statement_timeout = '45s'"))
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
            await_stage(inserted, first, "first insert")
            second = pool.submit(connect, ("bob", "102"))
            await_stage(second_attempting, second, "second lock attempt")
            blockers: list[int] = []
            while monotonic() < deadline:
                with customer_engine.connect() as observer:
                    observer.execute(text("SET LOCAL statement_timeout = '2s'"))
                    blockers = observer.scalar(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": backend_ids["bob"]}
                    )
                if backend_ids["alice"] in blockers:
                    reached("database_blocking_observed")
                    break
                if second.done():
                    second.result()
                    pytest.fail(f"second worker escaped workspace fence; stages={stages}")
                Event().wait(0.01)
            assert backend_ids["alice"] in blockers, f"blocking not observed; stages={stages}"
            assert not second.done()
        except BaseException as error:
            release.set()
            outcomes = {}
            for actor, worker in (("alice", first), ("bob", second)):
                if worker is not None:
                    try:
                        outcomes[actor] = worker.result(timeout=10)
                    except BaseException as failure:
                        # Do not repeat SQL payloads or credential material in notes.
                        outcomes[actor] = type(failure).__name__
            error.add_note(f"connection stages={stages}; worker outcomes={outcomes}")
            raise
        finally:
            reached("winner_released")
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
