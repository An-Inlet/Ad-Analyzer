"""Actual finalized0089 graph on SQLite and PostgreSQL, no provider traffic."""

import importlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import (
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    presence_digest,
)
from app.campaign_performance.presence_export import PresenceExportContext
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.presence_storage import (
    ReportingPresenceUnavailable,
    _row,
    read_presence,
    store_presence,
)
from app.campaign_performance.service import manifest
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.export_serializers import fields, serialize
from app.lifecycle.inventory import export_section, verify_registry
from app.lifecycle.privacy import advance_workspace_export_revision, bump_workspace_export_revision
from app.workspaces.models import Workspace, WorkspaceIntegration
from sqlalchemy import Engine, delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_reporting_presence_contracts import fact, header

pytestmark = pytest.mark.planning_boundary


def seed(
    db: Session, wid: int = 501, *, empty: bool = False
) -> tuple[PerformanceCompletion, ReportingSemanticsV1, tuple[ReportedMetricPresenceV1, ...]]:
    if db.get(Workspace, wid) is None:
        db.add(Workspace(id=wid, slug=f"presence-{wid}", name="Presence", client_name="Test"))
        db.flush()
    integration = WorkspaceIntegration(
        workspace_id=wid,
        integration_key="presence",
        provider="meta_ads",
        display_name="Synthetic",
        status="active",
    )
    db.add(integration)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=wid,
        connection_id=integration.id,
        platform="meta_ads",
        external_account_id=str(wid),
        name="Synthetic",
        currency_code="USD",
        time_zone="America/New_York",
    )
    db.add(account)
    db.flush()
    campaign = Campaign(
        account_id=account.id,
        platform="meta_ads",
        external_campaign_id="123",
        name="Synthetic <img src=x>",
    )
    db.add(campaign)
    db.flush()
    if not empty:
        db.add(
            DailyMetric(
                platform="meta_ads",
                entity_type="campaign",
                entity_id=campaign.id,
                campaign_id=campaign.id,
                metric_date=date(2026, 9, 1),
                impressions=1000,
                clicks=100,
                cost_micros=100_000_000,
                conversions=Decimal(10),
                conversion_value_micros=0,
            )
        )
        db.flush()
    digest, rows = manifest(db, account, date(2026, 9, 1), date(2026, 9, 30))
    completion = PerformanceCompletion(
        id=uuid4().hex,
        workspace_id=wid,
        account_id=account.id,
        platform="meta_ads",
        source_connection_ref="1",
        generation=1,
        privacy_revision=0,
        starts_on=date(2026, 9, 1),
        ends_on=date(2026, 9, 30),
        currency="USD",
        time_zone=account.time_zone,
        query_version="meta.v26.0.campaign-day.v1",
        semantics="explicit_platform_event",
        selected_event="purchase",
        reporting_basis="provider_defaults_unspecified",
        completed_at=datetime(2026, 10, 1, 12, tzinfo=UTC),
        row_count=len(rows),
        manifest_digest=digest,
    )
    db.add(completion)
    db.flush()
    db.add(CurrentPerformance(account_id=account.id, workspace_id=wid, completion_id=completion.id))
    db.flush()
    facts = (
        ()
        if empty
        else (
            fact(
                completion_id=completion.id,
                workspace_id=wid,
                account_id=account.id,
                campaign_id=campaign.id,
            ),
        )
    )
    semantics = header(
        facts,
        completion_id=completion.id,
        workspace_id=wid,
        account_id=account.id,
        connection_id=integration.id,
        source_connection_ref="1",
        legacy_manifest_digest=digest,
        query_descriptor=completion.query_version,
    )
    db.commit()
    return completion, semantics, facts


@pytest.mark.parametrize("empty", [False, True])
def test_store_read_replay_history_and_rollback(customer_engine: Engine, empty: bool) -> None:
    with Session(customer_engine) as db:
        item, h, facts = seed(db, empty=empty)
        assert read_presence(db, item) is None
        store_presence(db, h, facts)
        assert read_presence(db, item) == (h, facts)
        db.rollback()
        assert read_presence(db, item) is None
        store_presence(db, h, facts)
        db.commit()
        store_presence(db, h, facts)
        db.commit()
        assert db.scalar(select(func.count()).select_from(ReportingSemanticsRow)) == 1
        assert db.scalar(select(func.count()).select_from(MetricPresenceRow)) == len(facts)
        changed = h.model_copy(update={"producer_contract": "different.v1"})
        with pytest.raises(ReportingPresenceUnavailable, match="differs"):
            store_presence(db, changed, facts)
        db.execute(delete(CurrentPerformance))
        db.execute(update(DailyMetric).values(clicks=99))
        db.execute(update(WorkspaceIntegration).values(status="disconnected"))
        advance_workspace_export_revision(db, h.workspace_id)
        db.commit()
        assert read_presence(db, item) == (h, facts)
        with pytest.raises(ReportingPresenceUnavailable):
            store_presence(db, h, facts)
        # Ordinary counter advance retains the graph; semantic bump erases it.
        bump_workspace_export_revision(db, h.workspace_id)
        db.commit()
        assert read_presence(db, item) is None


@pytest.mark.parametrize(
    "change",
    [
        "count",
        "native",
        "present",
        "source",
        "query",
        "current",
        "currency",
        "manifest",
        "privacy",
        "fact_date",
    ],
)
def test_store_rejects_untrusted_or_changed_complete_basis(
    customer_engine: Engine, change: str
) -> None:
    with Session(customer_engine) as db:
        item, h, facts = seed(db)
        if change in {"native", "present", "fact_date"}:
            choices: dict[str, dict[str, Any]] = {
                "native": dict(native_campaign_id="999"),
                "present": dict(clicks=dict(presence="present", value=99)),
                "fact_date": dict(metric_date=date(2026, 9, 2)),
            }
            updates = choices[change]
            facts = (ReportedMetricPresenceV1.model_validate({**facts[0].model_dump(), **updates}),)
            h = h.model_copy(update={"fact_digest": presence_digest(facts)})
        elif change == "current":
            db.execute(delete(CurrentPerformance))
        elif change == "currency":
            db.execute(update(AdvertisingAccount).values(currency_code="EUR"))
        elif change == "manifest":
            db.execute(update(DailyMetric).values(clicks=1))
        elif change == "privacy":
            advance_workspace_export_revision(db, h.workspace_id)
        else:
            header_changes: dict[str, dict[str, Any]] = {
                "count": {"fact_count": 0},
                "source": {"source_connection_ref": "2"},
                "query": {"query_descriptor": "other.v1"},
            }
            h = h.model_copy(update=header_changes[change])
        with pytest.raises(ReportingPresenceUnavailable):
            store_presence(db, h, facts)
        assert db.scalar(select(func.count()).select_from(ReportingSemanticsRow)) == 0
        db.rollback()


def test_missing_whole_fact_set_and_corrupt_body_never_legacy(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        item, h, facts = seed(db)
        store_presence(db, h, facts)
        db.commit()
        with db.begin_nested() as transaction:
            db.execute(delete(MetricPresenceRow))
            with pytest.raises(ReportingPresenceUnavailable):
                read_presence(db, item)
            with pytest.raises(ReportingPresenceUnavailable):
                export_section(
                    db,
                    LifecycleScopeV1(workspace_id=h.workspace_id),
                    ReportingSemanticsRow.__tablename__,
                )
            transaction.rollback()
        # Replacement insert remains structurally scoped but its body commits a different fact.
        db.execute(delete(MetricPresenceRow))
        changed = ReportedMetricPresenceV1.model_validate(
            {**facts[0].model_dump(), "selected_conversions": dict(presence="present", value="0")}
        )
        db.add(MetricPresenceRow(**_row(changed)))
        db.commit()
        with pytest.raises(ReportingPresenceUnavailable):
            read_presence(db, item)


def test_snapshot_export_exact_rows_and_transaction_fence(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        item, h, facts = seed(db)
        store_presence(db, h, facts)
        db.commit()
        verify_registry()
        db.get(PerformanceCompletion, item.id)
        context = PresenceExportContext(db)
        for model in (ReportingSemanticsRow, MetricPresenceRow):
            row = db.scalars(select(model)).one()
            values = {key: getattr(row, key) for key in fields(model.__tablename__)}
            output, missing = serialize(
                model.__tablename__, values, db=db, presence_context=context
            )
            assert not missing and "document" in output and "canonical_json" not in output
            with pytest.raises(ReportingPresenceUnavailable):
                serialize(
                    model.__tablename__,
                    {**values, "payload_digest": "0" * 64},
                    db=db,
                    presence_context=context,
                )
        db.rollback()
        db.get(PerformanceCompletion, item.id)
        with pytest.raises(ReportingPresenceUnavailable, match="transaction changed"):
            context.export(model.__tablename__, values)


def test_actual0089_bindings_immutability_erasure_downgrade(
    migration_customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    migration = importlib.import_module("migrations.versions.20261008_0089_reporting_presence")
    engine = migration_customer_engine
    with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            for name in reversed(migration.TABLES):
                connection.exec_driver_sql(f"DROP TABLE {name}")
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            with monkeypatch.context() as patch:
                patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
                migration.upgrade()
    with Session(engine) as db:
        item, h, facts = seed(db)
        other_item, other, other_facts = seed(db, 502)
        invalid_rows: list[dict[str, Any]] = [
            dict(workspace_id=502),
            dict(account_id=other.account_id),
            dict(connection_id=other.connection_id),
            dict(generation=2),
            dict(payload_bytes=1),
            dict(fact_count=0),
            dict(platform="google_ads"),
        ]
        for updates in invalid_rows:
            with pytest.raises(DBAPIError), db.begin_nested():
                db.add(ReportingSemanticsRow(**{**_row(h), **updates}))
                db.flush()
        store_presence(db, h, facts)
        db.commit()
        for model in (ReportingSemanticsRow, MetricPresenceRow):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(update(model).values(payload_digest="0" * 64))
        with pytest.raises(DBAPIError), db.begin_nested():
            bad = _row(facts[0])
            bad["campaign_id"] = 99999
            db.add(MetricPresenceRow(**bad))
            db.flush()
        with pytest.raises(RuntimeError, match="cannot discard"), monkeypatch.context() as patch:
            patch.setattr(migration, "op", Operations(MigrationContext.configure(db.connection())))
            migration.downgrade()
        store_presence(db, other, other_facts)
        db.commit()
        bump_workspace_export_revision(db, h.workspace_id)
        db.commit()
        assert read_presence(db, item) is None
        assert read_presence(db, other_item) == (other, other_facts)
        bump_workspace_export_revision(db, other.workspace_id)
        db.commit()
        for name in migration.TABLES:
            assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0
        with monkeypatch.context() as patch:
            patch.setattr(migration, "op", Operations(MigrationContext.configure(db.connection())))
            migration.downgrade()
            migration.upgrade()
        db.commit()


def test_actual_archive_presence_and_delivery_privacy(export_engine: Engine, tmp_path: Any) -> None:
    import json

    from app.campaign_review.storage import LocalMediaStore
    from fastapi import HTTPException

    from tests.test_customer_exports import build, prepared, unpack

    authority, wid = prepared(export_engine)
    with Session(export_engine) as db:
        item, h, facts = seed(db, wid)
        store_presence(db, h, facts)
        db.commit()
    output, metadata = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, entries = unpack(output)
        for table in (ReportingSemanticsRow.__tablename__, MetricPresenceRow.__tablename__):
            exported = [json.loads(line) for line in entries[f"data/{table}.jsonl"].splitlines()]
            assert len(exported) == 1 and exported[0]["workspace_id"] == wid
            assert exported[0]["document"]["completion_id"] == h.completion_id
        assert metadata["supported_customer_data_complete"] is True
        with Session(export_engine) as db:
            db.execute(delete(MetricPresenceRow))
            db.commit()
        with pytest.raises(ReportingPresenceUnavailable):
            build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
        with Session(export_engine) as db:
            bump_workspace_export_revision(db, wid)
            db.commit()
        with pytest.raises(HTTPException):
            authority.check()
    finally:
        output.close()


def test_raw_insert_selected_event_actual_interval_and_historical_digest_guards(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        item, h, facts = seed(db)
        h = h.model_copy(update={"actual_ends_on": date(2026, 9, 1)})
        invalid_event = h.model_copy(
            update={
                "selected_event": h.selected_event.model_copy(update={"native_event_id": "lead"})
            }
        )
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(ReportingSemanticsRow(**_row(invalid_event)))
            db.flush()
        store_presence(db, h, facts)
        db.commit()
        with pytest.raises(DBAPIError), db.begin_nested():
            later = facts[0].model_copy(update={"metric_date": date(2026, 9, 2)})
            db.add(MetricPresenceRow(**_row(later)))
            db.flush()
        with db.begin_nested() as transaction:
            db.execute(delete(MetricPresenceRow))
            db.execute(delete(ReportingSemanticsRow))
            db.add(ReportingSemanticsRow(**{**_row(h), "payload_digest": "0" * 64}))
            db.flush()
            db.add(MetricPresenceRow(**_row(facts[0])))
            db.flush()
            with pytest.raises(ReportingPresenceUnavailable, match="canonical/scalar"):
                read_presence(db, item)
            transaction.rollback()
        assert read_presence(db, item) == (h, facts)
