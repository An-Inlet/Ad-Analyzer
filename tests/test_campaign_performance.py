"""Actual Meta wire/page publication → owned current-only reported evidence."""

import io
import json
import time
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from app.ads.models import Campaign, DailyMetric
from app.campaign_performance import service
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.inventory import export_section, verify_registry
from app.lifecycle.privacy import bump_workspace_export_revision
from app.meta import client as wire
from app.meta.client import MetaClient
from app.meta.sync import MetaSyncService
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_execution_session_authorizer import guard
from tests.test_meta_connection import NOW, campaign, connected, insight, page
from tests.test_meta_connection import configuration as configuration


def setup(
    db: Session, configuration: Settings, monkeypatch: pytest.MonkeyPatch, event: str = "purchase"
) -> Any:
    source = connected(db, configuration, event=event)
    uid = uuid4().hex
    user = CustomerUser(
        id=uid, issuer="test", subject=uid, email="owner@example.test", status="active"
    )
    db.add(user)
    db.flush()
    db.add(CustomerMembership(workspace_id=source.workspace_id, user_id=uid, role="owner"))
    db.commit()
    authorize, token = guard(db, uid)
    payloads = [page(campaign()), page(), page(insight())]
    requests: list[str] = []

    class Opener:
        def open(self, request: Any, timeout: int) -> io.BytesIO:
            parsed = urlsplit(request.full_url)
            assert parsed.hostname == "graph.facebook.com" and request.method == "GET"
            assert timeout == 12
            requests.append(parsed.path)
            return io.BytesIO(json.dumps(payloads.pop(0)).encode())

    monkeypatch.setattr(wire, "build_opener", lambda *_: Opener())
    runner = MetaSyncService(db, configuration, MetaClient(configuration))
    return source, uid, authorize, token, payloads, requests, runner


def finish(db: Session, source: Any, runner: MetaSyncService, now: Any = NOW) -> int:
    for status in ("syncing", "syncing", "complete"):
        assert runner.page(source.workspace_id, now=now, manual=True)["status"] == status
        if status != "complete":
            assert db.get(CurrentPerformance, source.account_id) is None
    cid = db.scalar(select(Campaign.id).where(Campaign.account_id == source.account_id))
    assert cid
    return cid


def test_real_http_terminal_publication_and_current_reader(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, actor, auth, _, _, requests, runner = setup(db, configuration, monkeypatch)
        cid = finish(db, source, runner)
        result = service.read_current(
            db, source.workspace_id, actor, source.account_id, cid, None, auth
        )
        assert len(requests) == 3 and requests[-1].endswith("/insights")
        assert result.conversions == "3.000000" and result.conversion_value_micros == 150120000
        assert result.spend_micros == 10000001 and result.reported_day_count == 1
        assert result.semantics == "explicit_platform_event" and result.maturity == "unqualified"
        assert (
            not result.spending_authorized
            and result.reporting_basis == "provider_defaults_unspecified"
        )
        verify_registry()
        scope = LifecycleScopeV1(workspace_id=source.workspace_id)
        exported = export_section(db, scope, "campaign_performance_completions")
        assert exported["rows"][0]["id"] == result.completion_id
        assert "encrypted" not in json.dumps(exported)
        assert (
            export_section(
                db,
                LifecycleScopeV1(workspace_id=source.workspace_id + 1),
                "campaign_performance_current",
            )["rows"]
            == []
        )
        with pytest.raises(HTTPException):
            service.read_current(
                db, source.workspace_id + 1, actor, source.account_id, cid, None, auth
            )


@pytest.mark.parametrize("change", ["rows", "generation", "event", "privacy", "session"])
def test_current_evidence_invalidates(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    with Session(customer_engine) as db:
        source, actor, auth, token, _, _, runner = setup(db, configuration, monkeypatch)
        cid = finish(db, source, runner)
        item = service.read_current(
            db, source.workspace_id, actor, source.account_id, cid, None, auth
        )
        if change == "rows":
            metric = db.scalar(select(DailyMetric))
            assert metric
            metric.cost_micros += 1
        elif change == "generation":
            source.generation += 1
        elif change == "event":
            source.conversion_action_type = "lead"
        elif change == "privacy":
            bump_workspace_export_revision(db, source.workspace_id)
        else:
            session = db.get(CustomerSession, token)
            assert session
            session.revoked_at = int(time.time())
        db.commit()
        with pytest.raises(HTTPException):
            service.read_current(
                db, source.workspace_id, actor, source.account_id, cid, item.completion_id, auth
            )


def test_unknown_event_and_true_zero_are_different(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, actor, auth, _, payloads, _, runner = setup(db, configuration, monkeypatch, "")
        cid = finish(db, source, runner)
        before = service.read_current(
            db, source.workspace_id, actor, source.account_id, cid, None, auth
        )
        assert before.conversions is None and before.conversion_value_micros is None
        source.conversion_action_type = "purchase"
        source.generation += 1
        db.commit()
        payloads.extend([page(campaign()), page(), page(insight(actions=[], action_values=[]))])
        for _ in range(3):
            runner.page(source.workspace_id, now=NOW + timedelta(hours=1), manual=True)
        after = service.read_current(
            db, source.workspace_id, actor, source.account_id, cid, None, auth
        )
        assert after.conversions == "0.000000" and after.conversion_value_micros == 0
        assert after.cpa_micros is None and before.completion_id != after.completion_id
        assert db.get(PerformanceCompletion, before.completion_id) is not None
        with pytest.raises(HTTPException):
            service.read_current(
                db, source.workspace_id, actor, source.account_id, cid, before.completion_id, auth
            )


def test_overflow_rolls_back_terminal_publication(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, _, _, _, _, _, runner = setup(db, configuration, monkeypatch)
        monkeypatch.setattr(service, "MAX_ROWS", 0)
        for _ in range(2):
            assert runner.page(source.workspace_id, now=NOW, manual=True)["status"] == "syncing"
        assert (
            runner.page(source.workspace_id, now=NOW, manual=True)["status"]
            == "meta_invalid_response"
        )
        assert db.scalar(select(PerformanceCompletion.id)) is None
        assert db.scalar(select(DailyMetric.id)) is None


def test_correction_reference_and_sparse_campaign_are_not_historical_or_zero(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, actor, auth, _, payloads, _, runner = setup(db, configuration, monkeypatch)
        cid = finish(db, source, runner)
        before = service.read_current(
            db, source.workspace_id, actor, source.account_id, cid, None, auth
        )
        payloads.extend([page(campaign()), page(), page()])
        later = NOW + timedelta(hours=1)
        for _ in range(2):
            runner.page(source.workspace_id, now=later, manual=True)
            # Partial replacement retains the old completed report, explicitly as-of old time.
            assert (
                service.read_current(
                    db,
                    source.workspace_id,
                    actor,
                    source.account_id,
                    cid,
                    before.completion_id,
                    auth,
                )
                == before
            )
            db.commit()
        assert runner.page(source.workspace_id, now=later, manual=True)["status"] == "complete"
        after = service.read_current(
            db, source.workspace_id, actor, source.account_id, cid, None, auth
        )
        assert (
            not after.campaign_rows_available
            and after.conversions is None
            and after.spend_micros is None
        )
        with pytest.raises(HTTPException):
            service.read_current(
                db, source.workspace_id, actor, source.account_id, cid, before.completion_id, auth
            )


def test_actual_0074_immutable_metadata_and_owned_reference(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import update
    from sqlalchemy.exc import DBAPIError

    migration = importlib.import_module("migrations.versions.20261006_0074_campaign_performance")
    with customer_engine.begin() as connection:
        if customer_engine.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.tables["campaign_performance_current"].drop(connection)
        Base.metadata.tables["campaign_performance_completions"].drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
    with Session(customer_engine) as db:
        source, actor, auth, _, _, _, runner = setup(db, configuration, monkeypatch)
        cid = finish(db, source, runner)
        before = service.read_current(
            db, source.workspace_id, actor, source.account_id, cid, None, auth
        )
        db.commit()
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(update(PerformanceCompletion).values(row_count=0))
        retained = db.get(PerformanceCompletion, before.completion_id)
        assert retained is not None and retained.row_count == 1
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(update(CurrentPerformance).values(workspace_id=source.workspace_id + 100))
        db.delete(retained)
        db.commit()
        assert db.get(CurrentPerformance, source.account_id, populate_existing=True) is None
        with pytest.raises(HTTPException):
            service.read_current(db, source.workspace_id, actor, source.account_id, cid, None, auth)
    with (
        customer_engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
    ):
        migration.downgrade()
        migration.upgrade()
