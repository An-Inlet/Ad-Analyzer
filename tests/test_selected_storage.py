"""Internal owned storage over actual terminal Meta import; no customer/catalog claim."""

from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    CustomerEventSelectionV1,
    ReportingScopeV1,
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    capture_request_digest,
    selection_digest,
)
from app.campaign_performance.selected_export import export_selected
from app.campaign_performance.selected_models import (
    CurrentEventSelectionRow,
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from app.campaign_performance.selected_storage import (
    SelectedReportingUnavailable,
    invalidate_selected_account,
    read_selected_capture,
    read_selection,
    store_selected_capture,
    store_selection,
)
from app.lifecycle.inventory import verify_registry
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.meta.security import utc
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.test_campaign_performance import finish, setup
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_meta_connection import configuration as configuration


@pytest.fixture(autouse=True)
def enforce_sqlite_fk(customer_engine: Engine) -> None:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            connection.commit()


def ready(
    db: Session, config: Settings, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, CustomerEventSelectionV1, SelectedCaptureV1]:
    source, actor, _, _, payloads, _, runner = setup(db, config, monkeypatch)
    source._fixture_runner, source._fixture_payloads = runner, payloads
    cid = finish(db, source, runner)
    pointer = db.get(CurrentPerformance, source.account_id)
    assert pointer is not None
    completion = db.get(PerformanceCompletion, pointer.completion_id)
    account = db.get(AdvertisingAccount, source.account_id)
    campaign = db.get(Campaign, cid)
    assert completion and account and campaign
    now = utc(completion.completed_at) + timedelta(days=2)
    scope = ReportingScopeV1(
        workspace_id=source.workspace_id,
        connection_id=account.connection_id,
        account_id=account.id,
        platform="meta_ads",
        source_connection_ref=str(source.id),
        generation=source.generation,
        privacy_revision=completion.privacy_revision,
        native_account_id=source.external_account_id,
        currency=account.currency_code,
        time_zone=account.time_zone,
    )
    selection = CustomerEventSelectionV1(
        selection_id=uuid4().hex,
        scope=scope,
        confirmed_by_customer_id=actor,
        confirmed_at=now,
        event_namespace="meta_action_type",
        native_event_owner_id=scope.native_account_id,
        native_event_id="purchase",
        metric_family="actions",
        api_version="v25",
        query_profile_digest="c" * 64,
    )
    request = SelectedCaptureRequestV1(
        capture_id=uuid4().hex,
        aggregate=AggregateDependencyV1(
            completion_id=completion.id,
            manifest_digest=completion.manifest_digest,
            scope=scope,
            starts_on=completion.starts_on,
            ends_on=completion.ends_on,
        ),
        selection=selection,
        selection_digest=selection_digest(selection),
        requested_starts_on=completion.starts_on,
        requested_ends_on=completion.ends_on,
        started_at=now + timedelta(seconds=1),
        producer_contract="fixture.selected.meta.v1",
        query_profile_digest=selection.query_profile_digest,
        attribution=dict(
            click_window_days=None,
            view_window_days=None,
            report_time_basis="unknown",
            provenance="provider_default_unknown",
            producer_contract="fixture.selected.meta.v1",
        ),
    )
    result = SelectedCaptureV1.model_validate(
        dict(
            request=request,
            request_digest=capture_request_digest(request),
            completed_at=now + timedelta(seconds=2),
            capability="supported",
            pagination_complete=True,
            page_count=1,
            facts=[
                dict(
                    capture_id=request.capture_id,
                    request_digest=capture_request_digest(request),
                    campaign_id=cid,
                    native_campaign_id=campaign.external_campaign_id,
                    metric_date=completion.ends_on,
                    selected_conversions=dict(presence="present", value="0"),
                    selected_value_micros=dict(presence="missing", value=None),
                )
            ],
        )
    )
    return source, selection, result


def test_owned_roundtrip_replay_export_and_erasure(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    verify_registry()
    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
        assert read_selection(db, source.workspace_id, source.account_id) == selection
        assert (
            read_selected_capture(
                db, source.workspace_id, source.account_id, capture.request.capture_id
            )
            == capture
        )
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 1
        for model in (
            EventSelectionRow,
            CurrentEventSelectionRow,
            SelectedCaptureRow,
            SelectedFactRow,
        ):
            row = db.scalar(select(model))
            assert row is not None
            supplied = {c.name: getattr(row, c.name) for c in row.__table__.columns}
            assert (
                export_selected(db, model.__tablename__, supplied)["currentness"]
                == "historical_as_observed"
            )
        old = workspace_export_revision(db, source.workspace_id)
        bump_workspace_export_revision(db, source.workspace_id)
        db.commit()
        assert workspace_export_revision(db, source.workspace_id) > old
        for model in (
            EventSelectionRow,
            CurrentEventSelectionRow,
            SelectedCaptureRow,
            SelectedFactRow,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        with pytest.raises(SelectedReportingUnavailable):
            read_selection(db, source.workspace_id, source.account_id)


@pytest.mark.parametrize("change", ["generation", "status", "manifest", "current", "selection"])
def test_current_dependency_changes_deny(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
        if change == "generation":
            source.generation += 1
        elif change == "status":
            source.status = "reconnect_required"
        elif change == "manifest":
            metric = db.scalar(select(DailyMetric))
            assert metric
            metric.cost_micros += 1
        elif change == "current":
            db.execute(
                delete(CurrentPerformance).where(CurrentPerformance.account_id == source.account_id)
            )
        else:
            db.execute(
                delete(CurrentEventSelectionRow).where(
                    CurrentEventSelectionRow.account_id == source.account_id
                )
            )
        db.commit()
        with pytest.raises((SelectedReportingUnavailable, HTTPException)) as error:
            read_selected_capture(
                db, source.workspace_id, source.account_id, capture.request.capture_id
            )
        assert (
            isinstance(error.value, SelectedReportingUnavailable)
            or getattr(error.value, "status_code", None) == 409
        )


def test_cas_immutable_raw_fact_delete_retracts_whole_graph(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
        changed = selection.model_copy(
            update={"selection_id": uuid4().hex, "native_event_id": "lead"}
        )
        with pytest.raises(SelectedReportingUnavailable, match="compare-and-swap"):
            store_selection(db, changed, None, None)
        with pytest.raises(SelectedReportingUnavailable, match="invalidation"):
            store_selection(db, changed, selection.selection_id, selection_digest(selection))
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(update(EventSelectionRow).values(payload_digest="f" * 64))
            db.flush()
        db.rollback()
        old = workspace_export_revision(db, source.workspace_id)
        db.execute(delete(SelectedFactRow))
        db.commit()
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
        assert workspace_export_revision(db, source.workspace_id) > old
        with pytest.raises(SelectedReportingUnavailable):
            read_selection(db, source.workspace_id, source.account_id)
        assert db.get(EventSelectionRow, selection.selection_id) is not None


def test_foreign_campaign_atomic_failure_and_reused_id(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        db.commit()
        bad = capture.model_copy(
            update={
                "facts": (
                    capture.facts[0].model_copy(
                        update={"metric_date": capture.facts[0].metric_date - timedelta(days=1)}
                    ),
                    capture.facts[0].model_copy(
                        update={"campaign_id": 999999, "native_campaign_id": "999999"}
                    ),
                )
            }
        )
        with pytest.raises(SelectedReportingUnavailable, match="mapping"):
            store_selected_capture(db, bad)
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == 0
        with pytest.raises(SelectedReportingUnavailable, match="replay"):
            store_selection(
                db,
                selection.model_copy(update={"native_event_id": "lead"}),
                selection.selection_id,
                selection_digest(selection),
            )
        assert read_selection(db, source.workspace_id, source.account_id) == selection


def test_invalidate_commit_real_refresh_explicit_reconfirmation(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_meta_connection import NOW, campaign, insight, page

    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
        invalidate_selected_account(db, source.workspace_id, source.account_id)
        db.commit()
        with pytest.raises(SelectedReportingUnavailable, match="scope"):
            store_selection(db, selection, None, None)
        db.rollback()
        source._fixture_payloads.extend([page(campaign()), page(), page(insight())])
        for expected in ("syncing", "syncing", "complete"):
            assert (
                source._fixture_runner.page(
                    source.workspace_id, now=NOW + timedelta(minutes=1), manual=True
                )["status"]
                == expected
            )
        current = db.get(CurrentPerformance, source.account_id, populate_existing=True)
        assert current
        assert current.completion_id != capture.request.aggregate.completion_id
        item = db.get(PerformanceCompletion, current.completion_id)
        assert item
        assert item.privacy_revision == workspace_export_revision(db, source.workspace_id)
        fresh = selection.model_copy(
            update={
                "selection_id": uuid4().hex,
                "native_event_id": "lead",
                "scope": selection.scope.model_copy(
                    update={"privacy_revision": item.privacy_revision}
                ),
            }
        )
        store_selection(db, fresh, selection.selection_id, selection_digest(selection))
        db.commit()
        assert read_selection(db, source.workspace_id, source.account_id) == fresh
        old_selection = db.get(EventSelectionRow, selection.selection_id)
        assert old_selection is not None and old_selection.payload_digest == selection_digest(
            selection
        )
        with pytest.raises(SelectedReportingUnavailable):
            read_selected_capture(
                db, source.workspace_id, source.account_id, capture.request.capture_id
            )


def test_raw_head_cycles_and_idempotent_invalidation(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, a, _ = ready(db, configuration, monkeypatch)
        store_selection(db, a, None, None)
        db.commit()
        invalidate_selected_account(db, source.workspace_id, source.account_id)
        db.commit()
        revised = workspace_export_revision(db, source.workspace_id)
        invalidate_selected_account(db, source.workspace_id, source.account_id)
        db.commit()
        assert workspace_export_revision(db, source.workspace_id) == revised
        b = a.model_copy(
            update={
                "selection_id": uuid4().hex,
                "scope": a.scope.model_copy(update={"privacy_revision": revised}),
            }
        )
        store_selection(db, b, a.selection_id, selection_digest(a))
        db.commit()
        for values in (
            dict(selection_id=a.selection_id, selection_digest=selection_digest(a)),
            dict(selection_digest="f" * 64),
            dict(workspace_id=999),
        ):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(update(CurrentEventSelectionRow).values(**values))
        invalidate_selected_account(db, source.workspace_id, source.account_id)
        db.commit()
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                update(CurrentEventSelectionRow).values(
                    selection_id=a.selection_id,
                    selection_digest=selection_digest(a),
                    invalidated=False,
                )
            )
        head = db.get(CurrentEventSelectionRow, source.account_id, populate_existing=True)
        assert head is not None and head.invalidated


def test_export_validates_once_and_rejects_new_transaction(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.campaign_performance import selected_export as exporter
    from app.lifecycle.export_serializers import serialize

    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
        db.get(SelectedCaptureRow, capture.request.capture_id)
        calls = []
        from app.campaign_performance.selected_storage import historical_capture

        actual = historical_capture

        def counted(*args: Any, **kwargs: Any) -> SelectedCaptureV1:
            calls.append(1)
            return actual(*args, **kwargs)

        monkeypatch.setattr(exporter, "historical_capture", counted)
        context = exporter.SelectedExportContext(db)
        for model in (SelectedCaptureRow, SelectedFactRow, SelectedFactRow):
            row = db.scalar(select(model))
            assert row
            values = {c.name: getattr(row, c.name) for c in row.__table__.columns}
            result, missing = serialize(
                model.__tablename__, values, db=db, selected_context=context
            )
            assert not missing and "document" in result
        assert len(calls) == 1
        db.rollback()
        db.get(SelectedCaptureRow, capture.request.capture_id)
        with pytest.raises(SelectedReportingUnavailable, match="transaction"):
            context.export(model.__tablename__, values)


def test_actual0091_and_frozen_metadata_parity(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.campaign_performance.selected_storage import MODELS
    from app.campaign_performance.selected_triggers import statements

    module = importlib.import_module("migrations.versions.20261011_0091_selected_reporting")
    forward = importlib.import_module("migrations.versions.20261012_0093_capture_settings")
    for name in module.TABLES:
        for ddl in statements(name, customer_engine.dialect.name):
            assert (
                ddl in module.SQL[customer_engine.dialect.name]
                or ddl in forward.SQL[customer_engine.dialect.name]
            )
    with customer_engine.begin() as connection:
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))
        module.downgrade()
        module.upgrade()
    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
        for model in (EventSelectionRow, SelectedCaptureRow, SelectedFactRow):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(update(model).values(payload_digest="d" * 64))
        assert (
            read_selected_capture(
                db, source.workspace_id, source.account_id, capture.request.capture_id
            )
            == capture
        )
    with customer_engine.begin() as connection:
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))
        with pytest.raises(RuntimeError, match="cannot discard"):
            module.downgrade()
    with Session(customer_engine) as db:
        bump_workspace_export_revision(db, source.workspace_id)
        db.commit()
    with customer_engine.begin() as connection:
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))
        module.downgrade()
        module.upgrade()
    with Session(customer_engine) as db:
        for remaining_model in MODELS:
            assert db.scalar(select(func.count()).select_from(remaining_model)) == 0


def test_campaign_platform_corruption_denies_historical_export(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.campaign_performance.selected_storage import historical_capture

    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
        campaign = db.get(Campaign, capture.facts[0].campaign_id)
        assert campaign
        from app.ads.enums import AdvertisingPlatform

        campaign.platform = AdvertisingPlatform.GOOGLE_ADS
        # Existing metric ownership FK already prevents corrupting this populated graph.
        with pytest.raises(DBAPIError):
            db.commit()
        db.rollback()
        assert (
            historical_capture(
                db, source.workspace_id, source.account_id, capture.request.capture_id
            )
            == capture
        )
        row = db.get(SelectedCaptureRow, capture.request.capture_id)
        assert row
        assert export_selected(
            db, row.__tablename__, {c.name: getattr(row, c.name) for c in row.__table__.columns}
        )
        # The account-platform FK also protects it if metrics have been removed.
        db.execute(delete(DailyMetric).where(DailyMetric.campaign_id == campaign.id))
        campaign.platform = AdvertisingPlatform.GOOGLE_ADS
        with pytest.raises(DBAPIError):
            db.commit()
        db.rollback()
        assert (
            historical_capture(
                db, source.workspace_id, source.account_id, capture.request.capture_id
            )
            == capture
        )


def test_prepared_export_authority_revoked_by_raw_delete(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from datetime import UTC, datetime

    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerSession, CustomerUser
    from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
    from app.lifecycle.exports import Authority
    from app.lifecycle.service import begin
    from app.settings import settings

    from tests.test_customer_identity import FakeProvider

    monkeypatch.setattr(settings, "customer_export_enabled", True)
    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        store_selection(db, selection, None, None)
        store_selected_capture(db, capture)
        db.commit()
        user = db.get(CustomerUser, selection.confirmed_by_customer_id)
        assert user
        session = db.scalar(select(CustomerSession).where(CustomerSession.user_id == user.id))
        assert session
        provider = FakeProvider()
        provider.issuer = user.issuer
        principal = CustomerPrincipal(user, session)
        request = begin(
            db,
            principal,
            provider,
            LifecycleInputV1(
                scope=LifecycleScopeV1(workspace_id=source.workspace_id), operation="export"
            ),
            "selected-export-guard-01",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(customer_engine, principal, provider, source.workspace_id, request.id)
        authority.capture_privacy(db)
        db.rollback()
        authority.claim()
        authority.check()
        from app.campaign_review.storage import LocalMediaStore

        from tests.test_customer_exports import build, unpack

        output, metadata = build(customer_engine, authority, LocalMediaStore(tmp_path / "media"))
        try:
            _, entries = unpack(output)
            assert metadata["supported_customer_data_complete"] is True
            for model in (
                EventSelectionRow,
                CurrentEventSelectionRow,
                SelectedCaptureRow,
                SelectedFactRow,
            ):
                assert entries[f"data/{model.__tablename__}.jsonl"]
        finally:
            output.close()
        db.execute(delete(SelectedFactRow))
        db.commit()
        with pytest.raises(HTTPException, match="invalidated") as error:
            authority.check()
        assert error.value.status_code == 409


def test_postgres_cas_serialization_and_raw_delete_nowait(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return  # Actual SQLite CAS/deletion semantics covered separately; no row-lock claim.
    from app.workspaces.models import Workspace
    from sqlalchemy import text

    with Session(customer_engine) as db:
        source, selection, capture = ready(db, configuration, monkeypatch)
        wid = source.workspace_id
        db.commit()
        store_selection(db, selection, None, None)
        other = selection.model_copy(update={"selection_id": uuid4().hex})
        with Session(customer_engine) as competing:
            competing.execute(text("SET LOCAL lock_timeout='200ms'"))
            with pytest.raises(DBAPIError) as blocked:
                store_selection(competing, other, None, None)
            assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
            competing.rollback()
            db.commit()
            with pytest.raises(SelectedReportingUnavailable, match="compare-and-swap"):
                store_selection(competing, other, None, None)
            competing.rollback()
        store_selected_capture(db, capture)
        db.commit()
        db.execute(select(Workspace).where(Workspace.id == wid).with_for_update())
        with Session(customer_engine) as competing:
            with pytest.raises(DBAPIError) as blocked:
                competing.execute(delete(SelectedFactRow))
            assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
            competing.rollback()
            db.rollback()
            competing.execute(select(Workspace).where(Workspace.id == wid).with_for_update())
            competing.execute(delete(SelectedFactRow))
            competing.commit()
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
