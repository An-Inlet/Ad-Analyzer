"""Original Meta windows through actual sync and immutable publication, offline only."""

import importlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.ads.models import AdvertisingAccount, DailyMetric
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_models import ReportingSemanticsRow
from app.campaign_performance.presence_storage import read_presence
from app.lifecycle.inventory import verify_registry
from app.lifecycle.privacy import advance_workspace_export_revision, bump_workspace_export_revision
from app.meta import presence_staging, staging
from app.meta.client import MetaClient
from app.meta.models import MetaStagedMetric
from app.meta.presence_models import MetaPresenceStageContext
from app.meta.security import MetaError
from app.meta.sync import MetaSyncService
from app.settings import Settings
from sqlalchemy import Engine, func, insert, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests import test_shopify_sales
from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_meta_connection import NOW, FakeMeta, campaign, complete, connected, insight, page
from tests.test_meta_connection import configuration as configuration

shopify_configuration = test_shopify_sales.configuration

pytestmark = pytest.mark.planning_boundary


def required[T](value: T | None) -> T:
    assert value is not None
    return value


def result(db: Session, account_id: int) -> tuple[Any, Any]:
    current = db.get(CurrentPerformance, account_id, populate_existing=True)
    assert current is not None
    completion = db.get(PerformanceCompletion, current.completion_id)
    assert completion is not None
    value = read_presence(db, completion)
    assert value is not None
    return value


@pytest.mark.parametrize(
    "actions,expected",
    [
        ([{"action_type": "purchase", "value": "10"}], "present"),
        ([{"action_type": "purchase", "value": "0"}], "present"),
        (None, "missing"),
        ([], "missing"),
        ([{"action_type": "lead", "value": "10"}], "missing"),
    ],
)
def test_actual_http_new_window_presence(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    actions: Any,
    expected: str,
) -> None:
    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        payloads = [
            page(campaign()),
            page(),
            page(insight(clicks="100", spend="100", actions=actions, action_values=[])),
        ]
        seen = []

        class Opener:
            def open(self, request: Any, timeout: int) -> BytesIO:
                assert request.method == "GET"
                # Context committed/visible to the importer before its very first HTTP.
                context = db.get(MetaPresenceStageContext, source.id)
                assert context is not None
                seen.append(request.full_url.split("?")[0])
                return BytesIO(json.dumps(payloads.pop(0)).encode())

        monkeypatch.setattr("app.meta.client.build_opener", lambda handler: Opener())
        service = MetaSyncService(db, configuration, MetaClient(configuration))
        for expected_status in ("syncing", "syncing", "complete"):
            assert (
                service.page(source.workspace_id, now=NOW, manual=True)["status"] == expected_status
            )
        header, facts = result(db, source.account_id)
        assert len(seen) == 3 and len(facts) == 1
        assert facts[0].clicks.value == 100 and facts[0].spend_micros.value == 100_000_000
        assert facts[0].selected_conversions.presence == expected
        assert facts[0].selected_value_micros.presence == "missing"
        assert header.attribution.provenance == "provider_default_unknown"
        assert db.get(MetaPresenceStageContext, source.id) is None
        assert db.scalar(select(func.count()).select_from(MetaStagedMetric)) == 0
        verify_registry()


def test_retry_partial_empty_and_history(customer_engine: Engine, configuration: Settings) -> None:
    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        raw = insight(actions=[], action_values=[{"action_type": "purchase", "value": "12"}])
        fake = FakeMeta(
            configuration,
            [
                page(campaign()),
                page(),
                page(raw, cursor="next"),
                MetaError("meta_throttled"),
                page(raw),
            ],
        )
        service = MetaSyncService(db, configuration, fake)
        for _ in range(3):
            assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        token = required(db.get(MetaPresenceStageContext, source.id)).window_token
        assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "meta_throttled"
        assert required(db.get(MetaPresenceStageContext, source.id)).window_token == token
        assert (
            service.page(source.workspace_id, now=NOW + timedelta(minutes=6), manual=True)["status"]
            == "complete"
        )
        header, facts = result(db, source.account_id)
        assert (
            facts[0].selected_conversions.value is None
            and facts[0].selected_value_micros.value == 12_000_000
        )
        completion = required(db.get(PerformanceCompletion, header.completion_id))
        advance_workspace_export_revision(db, source.workspace_id)
        db.commit()
        assert read_presence(db, completion) is not None
        empty = MetaSyncService(
            db, configuration, FakeMeta(configuration, [page(), page(), page()])
        )
        for status in ("syncing", "syncing", "complete"):
            assert (
                empty.page(source.workspace_id, now=NOW + timedelta(minutes=10), manual=True)[
                    "status"
                ]
                == status
            )
        new_header, new_facts = result(db, source.account_id)
        assert new_header.fact_count == 0 and new_facts == ()
        bump_workspace_export_revision(db, source.workspace_id)
        db.commit()
        assert read_presence(db, required(completion)) is None


@pytest.mark.parametrize(
    "drift", ["generation", "event", "currency", "privacy", "window", "conflict"]
)
def test_original_window_drift_never_replaces_snapshot(
    customer_engine: Engine, configuration: Settings, drift: str
) -> None:
    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        complete(db, configuration, source)
        old = required(db.get(CurrentPerformance, source.account_id)).completion_id
        fake = FakeMeta(
            configuration,
            [
                page(campaign()),
                page(),
                page(insight(), cursor="next"),
                page(insight(clicks="999") if drift == "conflict" else insight()),
            ],
        )
        service = MetaSyncService(db, configuration, fake)
        for _ in range(3):
            assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        account = db.get(AdvertisingAccount, source.account_id)
        if drift == "generation":
            source.generation += 1
        elif drift == "event":
            source.conversion_action_type = "lead"
        elif drift == "currency":
            required(account).currency_code = "EUR"
        elif drift == "privacy":
            advance_workspace_export_revision(db, source.workspace_id)
        elif drift == "window":
            source.window_start = required(source.window_start) + timedelta(days=1)
        db.commit()
        assert service.page(source.workspace_id, now=NOW, manual=True)["status"] != "complete"
        assert (
            required(
                db.get(CurrentPerformance, source.account_id, populate_existing=True)
            ).completion_id
            == old
        )
        assert db.scalar(select(func.count()).select_from(ReportingSemanticsRow)) == 1


def test_late_failure_rolls_back_legacy_and_presence(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        complete(db, configuration, source)
        old = required(db.get(CurrentPerformance, source.account_id)).completion_id
        original = presence_staging.publish_presence

        def late(*args: Any, **kwargs: Any) -> None:
            original(*args, **kwargs)
            raise MetaError("meta_unavailable")

        monkeypatch.setattr(presence_staging, "publish_presence", late)
        service = MetaSyncService(
            db,
            configuration,
            FakeMeta(configuration, [page(campaign()), page(), page(insight(spend="999"))]),
        )
        for _ in range(2):
            assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        assert (
            service.page(source.workspace_id, now=NOW, manual=True)["status"] == "meta_unavailable"
        )
        assert (
            required(
                db.get(CurrentPerformance, source.account_id, populate_existing=True)
            ).completion_id
            == old
        )
        assert db.scalar(select(DailyMetric.cost_micros)) == 10_000_001
        assert db.scalar(select(func.count()).select_from(ReportingSemanticsRow)) == 1
        assert db.get(MetaPresenceStageContext, source.id) is not None


@pytest.mark.parametrize("reset", [False, True])
def test_legacy_or_retained_window_reset_never_adopts(
    customer_engine: Engine, configuration: Settings, reset: bool
) -> None:
    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        if reset:
            first = MetaSyncService(
                db,
                configuration,
                FakeMeta(configuration, [page(campaign()), MetaError("meta_invalid_cursor")]),
            )
            assert first.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
            assert (
                first.page(source.workspace_id, now=NOW, manual=True)["status"]
                == "meta_invalid_cursor"
            )
            assert db.get(MetaPresenceStageContext, source.id) is None
            source.next_attempt_at = None
        else:
            source.window_start = NOW.date() - timedelta(days=55)
            source.window_end = NOW.date() - timedelta(days=1)
        db.commit()
        service = MetaSyncService(
            db, configuration, FakeMeta(configuration, [page(campaign()), page(), page(insight())])
        )
        for status in ("syncing", "syncing", "complete"):
            assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == status
        completion = db.get(
            PerformanceCompletion,
            required(db.get(CurrentPerformance, source.account_id)).completion_id,
        )
        assert read_presence(db, required(completion)) is None


def test_detail_clear_does_not_erase_campaign_context(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        service = MetaSyncService(db, configuration, FakeMeta(configuration, [page(campaign())]))
        assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        token = required(db.get(MetaPresenceStageContext, source.id)).window_token
        staging.clear(db, source.id)
        db.commit()
        assert required(db.get(MetaPresenceStageContext, source.id)).window_token == token
        bump_workspace_export_revision(db, source.workspace_id)
        db.commit()
        assert db.get(MetaPresenceStageContext, source.id) is None


def test_actual0090_downgrade_and_binding(
    migration_customer_engine: Engine, configuration: Settings
) -> None:
    engine = migration_customer_engine
    migration = importlib.import_module("migrations.versions.20261008_0090_meta_presence")
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=ON"))
            # Actual frozen0090 DDL from its empty predecessor, not create_all alone.
            for sql in migration.DOWN["sqlite"]:
                conn.execute(text(sql))
            for sql in migration.SQL["sqlite"]:
                conn.execute(text(sql))
        else:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "20261008_0090"
    with Session(engine) as db:
        source = connected(db, configuration, event="purchase")
        service = MetaSyncService(
            db,
            configuration,
            FakeMeta(configuration, [page(campaign()), page(), page(insight(), cursor="next")]),
        )
        for _ in range(3):
            assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(update(MetaPresenceStageContext).values(generation=999))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(update(MetaStagedMetric).values(presence_context_token=None))
        with pytest.raises(DBAPIError), db.begin_nested():
            presence_staging.clear_presence_context(db, source.id)
        with (
            pytest.raises(RuntimeError),
            Operations.context(MigrationContext.configure(db.connection())),
        ):
            migration.downgrade()
        staged = required(db.scalar(select(MetaStagedMetric)))
        legacy_values = {
            column.name: getattr(staged, column.name)
            for column in MetaStagedMetric.__table__.columns
            if column.name not in {"presence_context_token", "presence_json"}
        }
        presence_staging.clear_campaign_presence(db, source.id)
        db.execute(insert(MetaStagedMetric).values(**legacy_values))
        db.commit()
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        migration.downgrade()
        migration.upgrade()
    with Session(engine) as db:
        preserved = required(db.scalar(select(MetaStagedMetric)))
        assert preserved.presence_context_token is preserved.presence_json is None
        assert all(getattr(preserved, key) == value for key, value in legacy_values.items())


def test_terminal_calibration_privacy_and_semantic_erasure(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uuid import uuid4

    from app.ads.models import Campaign
    from app.campaign_performance.service import publish_meta
    from app.initial_planning.models import CalibrationRow
    from app.lifecycle.privacy import workspace_export_revision

    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        service = MetaSyncService(
            db, configuration, FakeMeta(configuration, [page(campaign()), page(), page(insight())])
        )
        for _ in range(2):
            assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        campaign_id = required(db.scalar(select(Campaign.id)))
        context = required(db.get(MetaPresenceStageContext, source.id))
        captured_revision = context.privacy_revision
        # Owned retained calibration row exercises the actual deletion trigger;
        # no calibration result is offered as recommendation evidence in this test.
        db.add(
            CalibrationRow(
                id=uuid4().hex,
                workspace_id=source.workspace_id,
                account_id=source.account_id,
                campaign_id=campaign_id,
                document={},
                document_digest="a" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=1),
                environment="offline",
                objective={},
                objective_digest="b" * 64,
                policy_digest="c" * 64,
                input_digest="d" * 64,
                created_at=NOW,
            )
        )
        db.commit()
        assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "complete"
        header, _ = result(db, source.account_id)
        assert header.privacy_revision > captured_revision
        assert header.privacy_revision == workspace_export_revision(db, source.workspace_id)
        assert db.scalar(select(func.count()).select_from(CalibrationRow)) == 0
        # Semantic erase between capture and attachment must never resurrect prepared facts.
        account = required(db.get(AdvertisingAccount, source.account_id))
        source.window_start = NOW.date() - timedelta(days=55)
        source.window_end = NOW.date() - timedelta(days=1)
        presence_staging.begin_presence(db, source, account, NOW)
        prepared = presence_staging.capture_presence(db, source, account)
        assert prepared is not None
        bump_workspace_export_revision(db, source.workspace_id)
        completion = publish_meta(
            db, source, required(source.window_start), required(source.window_end), NOW
        )
        with pytest.raises(MetaError, match="meta_presence_context_changed"):
            presence_staging.publish_presence(db, prepared, completion)
        db.rollback()


def test_fixed_read_import_retains_presence_without_new_writes(
    customer_engine: Engine,
    shopify_configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import advertising_capabilities
    from app.database.session import Base

    from tests.test_reported_feedback_acquisition import acquisition_fixture
    from tests.test_reported_feedback_acquisition import complete as complete_fixed

    with Session(customer_engine) as db:
        # Setup-only historical fixture: guards restored before every import page.
        with monkeypatch.context() as historical:
            historical.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
            historical.setattr(advertising_capabilities, "advertising_writes_enabled", lambda: True)
            wid, _, _, job, _, source, clock, runner, requests, _, server = acquisition_fixture(
                db, shopify_configuration, tmp_path, monkeypatch
            )
        assert advertising_capabilities.advertising_writes_enabled() is False
        with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
            advertising_capabilities.require_advertising_write()
        attempts = Base.metadata.tables["provider_execution_attempts"]
        before = db.scalar(select(func.count()).select_from(attempts))
        posts = len(server.posts)
        complete_fixed(runner, wid, clock[0])
        saved = (source.covered_from, source.covered_through, source.last_sync_at)
        complete_fixed(runner, wid, clock[0])
        header, facts = result(db, source.account_id)
        assert facts and header.pagination_complete and job.completed_observations == 1
        assert (source.covered_from, source.covered_through, source.last_sync_at) == saved
        assert db.scalar(select(func.count()).select_from(attempts)) == before
        assert len(server.posts) == posts
        assert len([path for path, _ in requests if path.endswith("/insights")]) == 2


def test_null_event_never_infers_purchase(customer_engine: Engine, configuration: Settings) -> None:
    with Session(customer_engine) as db:
        source = connected(db, configuration)
        complete(db, configuration, source)
        header, facts = result(db, source.account_id)
        assert header.selected_event.provenance == "unavailable"
        assert facts[0].selected_conversions.presence == "unsupported"
        assert facts[0].selected_value_micros.presence == "unsupported"


@pytest.mark.parametrize(
    "damage", ["missing_payload", "numeric_missing", "foreign_context", "oversize"]
)
def test_stage_integrity_rejects_before_terminal(
    customer_engine: Engine, configuration: Settings, damage: str
) -> None:
    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        service = MetaSyncService(
            db,
            configuration,
            FakeMeta(
                configuration, [page(campaign()), page(), page(insight(actions=[]), cursor="next")]
            ),
        )
        for _ in range(3):
            assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        if damage in {"foreign_context", "oversize"}:
            context = required(db.get(MetaPresenceStageContext, source.id))
            values = {
                column.name: getattr(context, column.name)
                for column in MetaPresenceStageContext.__table__.columns
            }
            presence_staging.clear_campaign_presence(db, source.id)
            if damage == "foreign_context":
                values["workspace_id"] += 10
            else:
                values["canonical_json"] += " " * 8192
                values["payload_bytes"] = len(values["canonical_json"].encode())
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(insert(MetaPresenceStageContext).values(**values))
        else:
            staged = required(db.scalar(select(MetaStagedMetric)))
            # Both-null is a valid legacy DB row, but cannot enter a qualified window.
            if damage == "missing_payload":
                staged.presence_context_token = staged.presence_json = None
            else:
                staged.conversions = Decimal(99)
            db.flush()
            account = required(db.get(AdvertisingAccount, source.account_id))
            with pytest.raises(MetaError):
                presence_staging.capture_presence(db, source, account)
            if damage == "missing_payload":
                with pytest.raises(MetaError):
                    presence_staging.stage_presence(
                        db, source, account, staged, insight(actions=[])
                    )
                db.commit()
                retry = MetaSyncService(
                    db, configuration, FakeMeta(configuration, [page(insight(actions=[]))])
                )
                assert (
                    retry.page(source.workspace_id, now=NOW, manual=True)["status"]
                    == "meta_presence_stage_changed"
                )
                assert db.get(CurrentPerformance, source.account_id) is None
        db.rollback()


def test_ephemeral_presence_not_exportable(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.lifecycle.contracts import LifecycleScopeV1
    from app.lifecycle.export_serializers import exclusion, fields
    from app.lifecycle.inventory import export_section
    from app.lifecycle.registry import PRIVATE_STAGING_TABLES

    with Session(customer_engine) as db:
        source = connected(db, configuration, event="purchase")
        service = MetaSyncService(db, configuration, FakeMeta(configuration, [page(campaign())]))
        assert service.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        assert "meta_presence_stage_contexts" in PRIVATE_STAGING_TABLES
        with pytest.raises(ValueError, match="not workspace-exportable"):
            export_section(
                db,
                LifecycleScopeV1(workspace_id=source.workspace_id),
                "meta_presence_stage_contexts",
            )
        for column in ("presence_context_token", "presence_json"):
            assert column not in fields("meta_staged_metrics")
            assert exclusion("meta_staged_metrics", column) == "security_or_internal"
