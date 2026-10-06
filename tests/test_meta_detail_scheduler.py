"""Actual HTTP request construction through scheduled durable child publication, offline."""

import io
import json
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest
from app.ads.models import DailyMetric
from app.meta import client as transport
from app.meta import sync
from app.meta.models import MetaConnection, MetaDetailCheckpoint, MetaDetailStagedPage
from app.meta.service import ConnectionService
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_meta_connection import NOW, campaign, complete, connected, insight, page
from tests.test_meta_connection import configuration as configuration
from tests.test_meta_detail import inventory


class OfflineHTTP:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str | None]] = []
        self.failure: str | None = None

    def open(self, request: Request, timeout: float) -> io.BytesIO:
        assert request.method == "GET" and 0 < timeout <= 12
        url = urlsplit(request.full_url)
        assert url.hostname == "graph.facebook.com"
        query = parse_qs(url.query)
        assert "access_token" not in query and "appsecret_proof" in query
        phase = query.get("level", [url.path.rsplit("/", 1)[-1]])[0]
        after = query.get("after", [None])[0]
        self.requests.append((url.path, phase, after))
        if phase in {"adset", "ad"}:
            assert query["time_increment"] == ["1"] and "breakdowns" not in query
            assert {"account_id", "campaign_id", "adset_id"} <= set(query["fields"][0].split(","))
        if phase == "campaigns":
            result = page(campaign())
        elif phase == "adsets":
            result = page(
                {
                    "id": "301",
                    "account_id": "101",
                    "campaign_id": "201",
                    "name": "Set",
                    "status": "ACTIVE",
                }
            )
        elif phase == "campaign":
            result = page(insight(spend="100"))
        elif phase == "ads":
            result = page(
                inventory("401" if after is None else "402"),
                cursor="ads-two" if after is None else None,
            )
        elif phase == "adset":
            result = (
                page(insight(adset_id="301", spend="100"), cursor="set-two")
                if after is None
                else page()
            )
        else:
            result = page(
                insight(
                    adset_id="301",
                    ad_id="401" if after is None else "402",
                    spend="60" if after is None else "40",
                ),
                cursor="ad-two" if after is None else None,
            )
        if self.failure and phase == "ad" and after is not None:
            if self.failure == "throttle":
                result = {"error": {"code": 4}}
            elif self.failure == "wrong_account":
                result = page(insight(account_id="102", adset_id="301", ad_id="402"))
            elif self.failure == "cycle":
                result = page(cursor="ad-two")
            elif self.failure == "wrong_parent":
                result = page(insight(adset_id="999", ad_id="402"))
        return io.BytesIO(json.dumps(result).encode())


def setup_import(
    engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, OfflineHTTP]:
    with Session(engine) as db:
        row = connected(db, configuration, event="purchase")
        complete(db, configuration, row, metric=insight(spend="7"))
        row.last_sync_at = None
        db.commit()
        wid = row.workspace_id
    configuration.meta_detail_enabled = True
    configuration.meta_sync_pages = 1

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> "FixedDateTime":
            return cls.fromtimestamp(NOW.timestamp(), tz)

    monkeypatch.setattr(sync, "datetime", FixedDateTime)
    monkeypatch.setattr(sync, "settings", configuration)
    http = OfflineHTTP()
    monkeypatch.setattr(transport, "build_opener", lambda *args: http)
    return wid, http


def spend(db: Session) -> list[tuple[str, int]]:
    return list(
        db.execute(
            select(DailyMetric.entity_type, DailyMetric.cost_micros).order_by(
                DailyMetric.entity_type, DailyMetric.id
            )
        ).tuples()
    )


def test_scheduler_resumes_child_pages_and_atomically_publishes(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wid, http = setup_import(customer_engine, configuration, monkeypatch)
    for step in range(8):
        sync.run_meta_tick(customer_engine)
        assert len(http.requests) == step + 1  # One actual bounded HTTP read per tick.
        with Session(customer_engine) as db:  # New session after every restart boundary.
            assert spend(db) == [("campaign", 7_000_000)]
            if step >= 3:
                checkpoint = db.scalar(select(MetaDetailCheckpoint))
                assert checkpoint is not None and checkpoint.page_count == step - 2
                assert checkpoint.workspace_id == wid
                assert db.scalar(select(func.count()).select_from(MetaDetailStagedPage)) == step - 2
    sync.run_meta_tick(customer_engine)
    with Session(customer_engine) as db:
        assert spend(db) == [
            ("ad", 60_000_000),
            ("ad", 40_000_000),
            ("ad_set", 100_000_000),
            ("campaign", 100_000_000),
        ]
        assert db.scalar(select(MetaDetailCheckpoint)) is None
        assert db.scalar(select(MetaDetailStagedPage)) is None
    assert [p for _, p, _ in http.requests] == [
        "campaigns",
        "adsets",
        "campaign",
        "ads",
        "ads",
        "adset",
        "adset",
        "ad",
        "ad",
    ]
    sync.run_meta_tick(customer_engine)
    assert len(http.requests) == 9  # Completed window is not refetched immediately.


@pytest.mark.parametrize(
    "failure,code",
    [
        ("throttle", "meta_throttled"),
        ("wrong_account", "meta_account_mismatch"),
        ("cycle", "meta_invalid_cursor"),
        ("wrong_parent", "meta_detail_invalid_snapshot"),
    ],
)
def test_failed_final_child_page_preserves_previous_complete_window(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    code: str,
) -> None:
    _, http = setup_import(customer_engine, configuration, monkeypatch)
    from app.ads.enums import AdvertisingPlatform
    from app.imports.scope import AdvertisingImportScope
    from app.meta.detail import publish

    from tests.test_meta_detail import batch

    with Session(customer_engine) as db:
        owner = db.scalar(select(MetaConnection))
        assert owner is not None
        publish(
            db,
            AdvertisingImportScope(
                owner.workspace_id,
                owner.workspace_integration_id or 0,
                owner.account_id,
                AdvertisingPlatform.META_ADS,
            ),
            batch(configuration),
        )
        db.commit()
        prior = spend(db)
    http.failure = failure
    for _ in range(9):
        sync.run_meta_tick(customer_engine)
    with Session(customer_engine) as db:
        assert spend(db) == prior
        row = db.scalar(select(MetaConnection))
        assert row is not None and row.error_code == code and row.next_attempt_at is not None
    before = len(http.requests)
    sync.run_meta_tick(customer_engine)
    assert len(http.requests) == before  # Persisted retry backoff, including after restart.


@pytest.mark.parametrize("action", ["disconnect", "generation", "revocation", "capacity"])
def test_child_staging_lifecycle_fences(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    wid, http = setup_import(customer_engine, configuration, monkeypatch)
    for _ in range(4):
        sync.run_meta_tick(customer_engine)
    with Session(customer_engine) as db:
        row = db.scalar(select(MetaConnection))
        checkpoint = db.scalar(select(MetaDetailCheckpoint))
        assert row is not None and checkpoint is not None
        if action == "disconnect":
            ConnectionService(db, configuration).disconnect(wid, "owner")
        elif action == "generation":
            row.generation += 1
        elif action == "capacity":
            checkpoint.page_count = 300
        else:
            from app.workspaces.models import WorkspaceIntegration

            integration = db.get(WorkspaceIntegration, row.workspace_integration_id)
            assert integration is not None
            integration.status = "revoked"
        db.commit()
    before = len(http.requests)
    sync.run_meta_tick(customer_engine)
    with Session(customer_engine) as db:
        assert db.scalar(select(MetaDetailCheckpoint)) is None
        assert db.scalar(select(MetaDetailStagedPage)) is None
    assert len(http.requests) == before


def test_transient_failure_resumes_last_cursor_without_reloading_inventory(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta

    wid, http = setup_import(customer_engine, configuration, monkeypatch)
    http.failure = "throttle"
    for _ in range(9):
        sync.run_meta_tick(customer_engine)
    http.failure = None
    with Session(customer_engine) as db:
        result = sync.MetaSyncService(db, configuration).page(
            wid, now=NOW + timedelta(seconds=301), manual=True
        )
        assert result["status"] == "complete"
        assert len(spend(db)) == 4
    assert len(http.requests) == 10 and http.requests[-1][1:] == ("ad", "ad-two")


def test_populated_checkpoint_migration_and_database_scope_constraints(
    migration_customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if migration_customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL migration and compound ownership constraints")
    from alembic import command
    from alembic.config import Config
    from app.settings import settings
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import IntegrityError

    _, _http = setup_import(migration_customer_engine, configuration, monkeypatch)
    for _ in range(4):
        sync.run_meta_tick(migration_customer_engine)
    with Session(migration_customer_engine) as db:
        checkpoint = db.scalar(select(MetaDetailCheckpoint))
        assert checkpoint is not None
        other = connected(db, configuration, slug="other", number="102")
        for field, value in [
            ("workspace_id", other.workspace_id),
            ("account_id", other.account_id),
            ("integration_id", other.workspace_integration_id),
        ]:
            with pytest.raises(IntegrityError), db.begin_nested():
                setattr(checkpoint, field, value)
                db.flush()
        assert spend(db) == [("campaign", 7_000_000)]
    with migration_customer_engine.connect() as db:
        schema = db.scalar(text("SELECT current_schema()"))
    url = migration_customer_engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setattr(settings, "database_url", url.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    command.downgrade(config, "20261006_0039")
    assert "meta_detail_checkpoints" not in inspect(migration_customer_engine).get_table_names()
    command.upgrade(config, "heads")
    with Session(migration_customer_engine) as db:
        assert spend(db) == [("campaign", 7_000_000)]
        assert db.scalar(select(MetaDetailCheckpoint)) is None


def test_scheduled_child_publication_isolates_other_customer_campaign_facts(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ads.enums import AdvertisingPlatform
    from app.ads.models import Campaign

    _, http = setup_import(customer_engine, configuration, monkeypatch)
    with Session(customer_engine) as db:
        other = connected(db, configuration, slug="other", number="102")
        other.last_sync_at = NOW
        campaign_row = Campaign(
            account_id=other.account_id,
            platform=AdvertisingPlatform.META_ADS,
            external_campaign_id="201",
            name="Other owner",
            status="ACTIVE",
        )
        db.add(campaign_row)
        db.flush()
        metric = DailyMetric(
            platform=AdvertisingPlatform.META_ADS,
            entity_type="campaign",
            entity_id=campaign_row.id,
            campaign_id=campaign_row.id,
            metric_date=NOW.date(),
            impressions=9,
            clicks=2,
            cost_micros=17,
            conversions=1,
            conversion_value_micros=19,
        )
        db.add(metric)
        db.commit()
        metric_id, other_id = metric.id, other.id
    for _ in range(9):
        sync.run_meta_tick(customer_engine)
    assert len(http.requests) == 9 and all("act_101/" in path for path, _, _ in http.requests)
    with Session(customer_engine) as db:
        existing = db.get(DailyMetric, metric_id)
        assert existing is not None and existing.cost_micros == 17 and existing.conversions == 1
        assert db.get(MetaDetailCheckpoint, other_id) is None
