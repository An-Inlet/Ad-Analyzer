"""Concurrent first grants must not deadlock while upgrading workspace FK locks."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from app.ads.models import AdvertisingAccount
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate
from app.meta.models import MetaConnection, MetaPendingGrant
from app.meta.security import MetaError
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
    inserted = Barrier(2)
    original = AdvertisingMetricsRepository.upsert_account

    def synchronized_upsert(
        self: AdvertisingMetricsRepository,
        account: AdvertisingAccountCreate,
        *,
        workspace_id: int | None = None,
    ) -> AdvertisingAccount:
        result = original(self, account, workspace_id=workspace_id)
        # Both transactions now own workspace KEY SHARE locks from different FK inserts.
        inserted.wait(timeout=5)
        return result

    monkeypatch.setattr(AdvertisingMetricsRepository, "upsert_account", synchronized_upsert)

    def connect(pair: tuple[str, str]) -> str:
        actor, external_id = pair
        with Session(customer_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
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
        outcomes = list(pool.map(connect, [("alice", "101"), ("bob", "102")]))
    assert sorted(outcomes) == ["connected", "meta_account_already_connected"]
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(MetaConnection)) == 1
        assert db.scalar(select(func.count()).select_from(AdvertisingAccount)) == 1
        assert db.scalar(select(func.count()).select_from(WorkspaceIntegration)) == 1
        assert db.scalar(select(func.count()).select_from(MetaPendingGrant)) == 1
        row = db.scalar(select(MetaConnection))
        assert row and row.workspace_integration_id is not None
