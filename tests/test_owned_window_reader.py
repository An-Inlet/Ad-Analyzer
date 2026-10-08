"""Actual owned SQL/MockHTTP catalog, read-only window context, no v3 activation."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.ads.models import Campaign
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.presence_report import CampaignPerformanceV3
from app.planning_documents.composer import targets
from app.planning_documents.evidence_local import local_authority
from app.planning_documents.ports import ReportingPresencePin
from app.planning_documents.retained_sources import capture_reporting_presence_pin
from app.planning_documents.window_evidence import KnownWindowGap
from app.planning_documents.window_reader import prepare_owned_window_context
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_planning_qualified_reporting import install_presence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def setup(
    engine: Engine,
    config: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    platform: str = "meta_ads",
    presence: bool = True,
) -> Any:
    reader, ticket, principal, calls = setup_evidence(
        engine, config, replicas, monkeypatch, platform
    )
    if presence:
        install_presence(engine, ticket.inputs.accounts[0].account_id)
    bundle = reader.collect(ticket)
    catalog = bundle.catalogs[0]
    target = next(t for t in targets(catalog) if t.kind == "campaign")
    return ticket, principal, catalog, target, calls


def arguments(db: Session, ticket: Any, principal: Any, catalog: Any) -> dict[str, Any]:
    def authorize(session: Session, wid: int, actor: str) -> None:
        local_authority(session, principal, wid, actor)

    authorize(db, ticket.inputs.workspace_id, principal.user.id)
    account = ticket.inputs.accounts[0]
    digest = capture_reporting_presence_pin(db, principal, account, ticket.privacy_revision)
    return dict(
        principal=principal,
        account=account,
        expected_source=ticket.sources[0],
        expected_reporting_pin=ReportingPresencePin(account=account, document_digest=digest),
        catalog=catalog,
        authorize=authorize,
        clock=lambda: datetime.now(UTC),
    )


def test_owned_projection_shared_pin_graph_and_default_digest(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.campaign_performance import presence_report
    from app.campaign_performance.presence_storage import read_presence

    ticket, principal, catalog, target, calls = setup(
        customer_engine, configuration, replicas, monkeypatch
    )
    with Session(customer_engine) as db:
        kwargs = arguments(db, ticket, principal, catalog)
        count = 0
        original = read_presence

        def counted(*args: Any, **kw: Any) -> Any:
            nonlocal count
            count += 1
            return original(*args, **kw)

        monkeypatch.setattr(presence_report, "read_presence", counted)
        native_calls = len(calls)
        with prepare_owned_window_context(db, **kwargs) as context:
            result = context.read(target, ticket.inputs.reporting_window)
            assert not isinstance(result, KnownWindowGap)
            assert isinstance(result.original, CampaignPerformanceV3)
            assert result.summary.clicks.value == 100
            assert result.summary.selected_conversions.value == "10"
            assert not result.summary.selected_zero_for_requested_window
            assert context.read(target, ticket.inputs.reporting_window) == result
            assert count == 1, "pin + original + repeated projection share one presence parse"
            assert (
                capture_reporting_presence_pin(
                    db,
                    principal,
                    target.account,
                    ticket.privacy_revision,
                    presence_context=context._presence,
                )
                == kwargs["expected_reporting_pin"].document_digest
            )
            assert count == 1
        context.close()
        assert not context._hooks
        with pytest.raises(HTTPException):
            context.read(target, ticket.inputs.reporting_window)
        assert len(calls) == native_calls


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_real_legacy_sources_without_presence_are_known_gaps(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    ticket, principal, catalog, target, _ = setup(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        platform=platform,
        presence=False,
    )
    with (
        Session(customer_engine) as db,
        prepare_owned_window_context(db, **arguments(db, ticket, principal, catalog)) as context,
    ):
        assert context.read(target, ticket.inputs.reporting_window) == KnownWindowGap(
            reason="reporting_presence_unavailable",
        )


@pytest.mark.parametrize(
    "operation",
    [
        "rollback",
        "commit",
        "nested_rollback",
        "nested_release",
        "nested_active",
        "flush",
        "pending",
    ],
)
def test_transaction_and_flush_reuse_rejected_and_hooks_removed(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    ticket, principal, catalog, target, _ = setup(
        customer_engine, configuration, replicas, monkeypatch
    )
    with Session(customer_engine) as db:
        context = prepare_owned_window_context(db, **arguments(db, ticket, principal, catalog))
        context.read(target, ticket.inputs.reporting_window)
        if operation in {"rollback", "commit"}:
            getattr(db, operation)()
        elif operation.startswith("nested"):
            nested = db.begin_nested()
            if operation == "nested_rollback":
                nested.rollback()
            elif operation == "nested_release":
                nested.commit()
        else:
            campaign = db.scalar(
                select(Campaign).where(Campaign.account_id == target.account.account_id)
            )
            assert campaign is not None
            campaign.name = "Pending Change"
            if operation == "flush":
                with pytest.raises(HTTPException):
                    db.flush()
        with pytest.raises(HTTPException):
            context.read(target, ticket.inputs.reporting_window)
        context.close()
        assert not context._hooks
        # Listener removal: a subsequent ordinary transaction can write normally.
        db.rollback()
        campaign = db.scalar(
            select(Campaign).where(Campaign.account_id == target.account.account_id)
        )
        assert campaign is not None
        campaign.name = "Ordinary Test Change"
        db.flush()
        db.rollback()


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_connection_ref", "different"),
        ("query_version", "different"),
        ("row_count", 123),
        ("selected_event", None),
        ("currency", "EUR"),
        ("manifest_digest", "f" * 64),
    ],
)
def test_completion_scalar_cache_hit_rejected_before_refresh(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
) -> None:
    ticket, principal, catalog, target, _ = setup(
        customer_engine, configuration, replicas, monkeypatch
    )
    with (
        Session(customer_engine) as db,
        prepare_owned_window_context(db, **arguments(db, ticket, principal, catalog)) as context,
    ):
        context.read(target, ticket.inputs.reporting_window)
        item = db.get(PerformanceCompletion, context._completion_id)
        assert item is not None
        # Simulate changed loaded scalars without marking dirty: refresh must not hide it.
        # No DB mutation, immutable trigger bypass, or manufactured presence document.
        set_committed_value(item, field, value)
        with pytest.raises(HTTPException):
            context._presence.read(item)
        with pytest.raises(HTTPException):
            context.read(target, ticket.inputs.reporting_window)


def test_current_authority_expiry_and_exact_selector_checked_on_original_cache_hit(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket, principal, catalog, target, _ = setup(
        customer_engine, configuration, replicas, monkeypatch
    )
    with Session(customer_engine) as db:
        kwargs = arguments(db, ticket, principal, catalog)
        denied = False
        ordinary = kwargs["authorize"]

        def authorize(*args: Any) -> None:
            ordinary(*args)
            if denied:
                raise HTTPException(401, "revoked test authority")

        kwargs["authorize"] = authorize
        with prepare_owned_window_context(db, **kwargs) as context:
            context.read(target, ticket.inputs.reporting_window)
            forged = target.model_copy(update={"selection_key": "f" * 64})
            with pytest.raises(HTTPException):
                context.read(forged, ticket.inputs.reporting_window)
            denied = True
            with pytest.raises(HTTPException) as error:
                context.read(target, ticket.inputs.reporting_window)
            assert error.value.status_code == 401
            denied = False
            context.clock = lambda: catalog.reference.expires_at
            with pytest.raises(HTTPException):
                context.read(target, ticket.inputs.reporting_window)


def test_prepare_failure_removes_observers_and_known_window_gap(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket, principal, catalog, target, _ = setup(
        customer_engine, configuration, replicas, monkeypatch
    )
    with Session(customer_engine) as db:
        kwargs = arguments(db, ticket, principal, catalog)
        installed = []
        listen = event.listen

        def record(owner: Any, name: str, callback: Any, *args: Any, **kw: Any) -> None:
            installed.append((owner, name, callback))
            listen(owner, name, callback, *args, **kw)

        monkeypatch.setattr(event, "listen", record)
        invalid = {**kwargs, "clock": lambda: catalog.reference.expires_at}
        with pytest.raises(HTTPException):
            prepare_owned_window_context(db, **invalid)
        assert installed and all(not event.contains(*entry) for entry in installed)
        with prepare_owned_window_context(db, **kwargs) as context:
            window = ticket.inputs.reporting_window
            outside = window.model_copy(update={"starts_at": window.starts_at - timedelta(days=1)})
            assert context.read(target, outside) == KnownWindowGap(reason="outside_imported_window")


@pytest.mark.parametrize(
    "change",
    ["mapping", "generation", "revocation", "privacy", "corrupt_presence", "current_absent"],
)
def test_actual_source_changes_before_new_context_reject_old_pin(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.campaign_performance.models import CurrentPerformance
    from app.campaign_performance.presence_models import MetricPresenceRow
    from app.customers.models import CustomerSession
    from app.lifecycle.privacy import bump_workspace_export_revision
    from app.meta.models import MetaConnection
    from sqlalchemy import delete, update

    ticket, principal, catalog, target, _ = setup(
        customer_engine, configuration, replicas, monkeypatch
    )
    with Session(customer_engine) as db:
        kwargs = arguments(db, ticket, principal, catalog)
    with Session(customer_engine) as db:
        if change == "mapping":
            campaign = db.scalar(
                select(Campaign).where(Campaign.account_id == target.account.account_id)
            )
            assert campaign is not None
            campaign.external_campaign_id = "999"
        elif change == "generation":
            source = db.scalar(
                select(MetaConnection).where(MetaConnection.account_id == target.account.account_id)
            )
            assert source is not None
            source.generation += 1
        elif change == "revocation":
            db.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == principal.session.digest)
                .values(revoked_at=int(datetime.now(UTC).timestamp()))
            )
        elif change == "privacy":
            bump_workspace_export_revision(db, ticket.inputs.workspace_id)
        elif change == "corrupt_presence":
            db.execute(delete(MetricPresenceRow))
        else:
            db.execute(
                delete(CurrentPerformance).where(
                    CurrentPerformance.account_id == target.account.account_id
                )
            )
        db.commit()
    with Session(customer_engine) as db:
        # Establish the caller-owned transaction; the old pin is deliberately retained.
        db.begin()
        with pytest.raises(HTTPException):
            prepare_owned_window_context(db, **kwargs)


def test_absent_current_is_gap_and_foreign_session_optional_cache_rejected(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.campaign_performance.models import CurrentPerformance
    from app.campaign_performance.presence_report import PresenceReadContext
    from sqlalchemy import delete

    ticket, principal, catalog, target, _ = setup(
        customer_engine, configuration, replicas, monkeypatch
    )
    with Session(customer_engine) as db:
        db.execute(
            delete(CurrentPerformance).where(
                CurrentPerformance.account_id == target.account.account_id
            )
        )
        db.commit()
    with Session(customer_engine) as db, Session(customer_engine) as other:
        kwargs = arguments(db, ticket, principal, catalog)
        other.begin()
        with pytest.raises(HTTPException):
            capture_reporting_presence_pin(
                db,
                principal,
                target.account,
                ticket.privacy_revision,
                presence_context=PresenceReadContext(other),
            )
        with prepare_owned_window_context(db, **kwargs) as context:
            assert context.read(target, ticket.inputs.reporting_window) == KnownWindowGap(
                reason="current_reporting_unavailable"
            )


def test_failed_authority_does_not_query_completion_before_denial(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket, principal, catalog, _, _ = setup(customer_engine, configuration, replicas, monkeypatch)
    with Session(customer_engine) as db:
        kwargs = arguments(db, ticket, principal, catalog)
        queries: list[str] = []

        def record(
            connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
        ) -> None:
            queries.append(statement)

        def denied(*args: Any) -> None:
            raise HTTPException(403, "foreign caller")

        event.listen(customer_engine, "before_cursor_execute", record)
        try:
            with pytest.raises(HTTPException):
                prepare_owned_window_context(db, **{**kwargs, "authorize": denied})
        finally:
            event.remove(customer_engine, "before_cursor_execute", record)
        assert not any("campaign_performance" in query for query in queries)


def test_actual_foreign_workspace_and_source_binding_rejected(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket, principal, catalog, _, _ = setup(customer_engine, configuration, replicas, monkeypatch)
    with Session(customer_engine) as db:
        kwargs = arguments(db, ticket, principal, catalog)
        foreign = kwargs["account"].model_copy(
            update={"workspace_id": ticket.inputs.workspace_id + 1000}
        )
        with pytest.raises(HTTPException) as denied:
            prepare_owned_window_context(db, **{**kwargs, "account": foreign})
        assert denied.value.status_code in {403, 404}
        wrong_source = kwargs["expected_source"].model_copy(
            update={"source_binding_digest": "f" * 64}
        )
        with pytest.raises(HTTPException):
            prepare_owned_window_context(db, **{**kwargs, "expected_source": wrong_source})
        # Failed prepares left neither listeners nor pending writes behind.
        with prepare_owned_window_context(db, **kwargs) as context:
            assert not context._closed


def test_multiple_campaigns_and_distinct_windows_share_only_one_transaction_graph(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actual SQL presence + server catalog; no raw provider-import qualification."""
    from decimal import Decimal
    from uuid import uuid4

    import httpx
    from app.ads.models import AdvertisingAccount, DailyMetric
    from app.campaign_performance import presence_report
    from app.campaign_performance.models import CurrentPerformance
    from app.campaign_performance.presence_contracts import (
        ReportedMetricPresenceV1,
        ReportingSemanticsV1,
        presence_digest,
    )
    from app.campaign_performance.presence_storage import read_presence, store_presence
    from app.campaign_performance.service import manifest
    from app.collectors import account_diagnostics
    from app.meta.models import MetaConnection
    from app.planning_documents.context import ReportingWindow

    reader, ticket, principal, _ = setup_evidence(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        "meta_ads",
    )
    aid = ticket.inputs.accounts[0].account_id
    old_header, old_facts = install_presence(customer_engine, aid, extra_campaign=True)
    # Expose the second genuinely owned SQL campaign through actual native+metadata HTTP reads.
    transport_factory = account_diagnostics.diagnostic_transport

    def wire(request: httpx.Request) -> httpx.Response:
        transport = transport_factory()
        assert transport is not None
        with transport:
            response = transport.handle_request(request)
            response.read()
        data = response.json()
        if request.url.path.endswith("/campaigns"):
            assert len(data["data"]) == 1
            data["data"].append({**data["data"][0], "id": "6"})
        return httpx.Response(response.status_code, json=data)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    with Session(customer_engine) as db:
        account = db.get(AdvertisingAccount, aid)
        current = db.get(CurrentPerformance, aid)
        assert account is not None and current is not None
        old = db.get(PerformanceCompletion, current.completion_id)
        source = db.scalar(select(MetaConnection).where(MetaConnection.account_id == aid))
        assert old is not None and source is not None
        completion_id = uuid4().hex
        start = old.starts_on - timedelta(days=1)
        facts = []
        for index, old_fact in enumerate(old_facts, 1):
            facts.append(
                ReportedMetricPresenceV1.model_validate(
                    old_fact.model_copy(
                        update={
                            "completion_id": completion_id,
                        }
                    )
                )
            )
            db.add(
                DailyMetric(
                    platform="meta_ads",
                    entity_type="campaign",
                    entity_id=old_fact.campaign_id,
                    campaign_id=old_fact.campaign_id,
                    metric_date=start,
                    impressions=100 * index,
                    clicks=10 * index,
                    cost_micros=1_000_000 * index,
                    conversions=Decimal(index),
                    conversion_value_micros=0,
                )
            )
            facts.append(
                ReportedMetricPresenceV1.model_validate(
                    old_fact.model_copy(
                        update={
                            "completion_id": completion_id,
                            "metric_date": start,
                            "impressions": {"presence": "present", "value": 100 * index},
                            "clicks": {"presence": "present", "value": 10 * index},
                            "spend_micros": {"presence": "present", "value": 1_000_000 * index},
                            "selected_conversions": {"presence": "present", "value": str(index)},
                        }
                    )
                )
            )
        db.flush()
        digest, rows = manifest(db, account, start, old.ends_on)
        values = {
            column.name: getattr(old, column.name)
            for column in PerformanceCompletion.__table__.columns
        }
        values.update(
            id=completion_id, starts_on=start, row_count=len(rows), manifest_digest=digest
        )
        db.add(PerformanceCompletion(**values))
        db.flush()
        current.completion_id = completion_id
        source.covered_from = start
        db.flush()
        ordered_facts = tuple(sorted(facts, key=lambda fact: (fact.campaign_id, fact.metric_date)))
        header = ReportingSemanticsV1.model_validate(
            old_header.model_copy(
                update={
                    "completion_id": completion_id,
                    "legacy_manifest_digest": digest,
                    "requested_starts_on": start,
                    "actual_starts_on": start,
                    "fact_count": len(ordered_facts),
                    "fact_digest": presence_digest(ordered_facts),
                }
            )
        )
        store_presence(db, header, ordered_facts)
        db.commit()
    catalog = reader.collect(ticket).catalogs[0]
    campaign_targets = sorted(
        (t for t in targets(catalog) if t.kind == "campaign"),
        key=lambda t: t.provider_reference.entity_id,
    )
    assert [t.provider_reference.entity_id for t in campaign_targets] == ["5", "6"]
    primary = ticket.inputs.reporting_window
    comparison = ReportingWindow(
        starts_at=primary.starts_at - timedelta(days=1), ends_at_exclusive=primary.starts_at
    )
    # Expected collection pin belongs to an earlier, separately closed transaction.
    with Session(customer_engine) as db:
        kwargs = arguments(db, ticket, principal, catalog)
    count = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal count
        count += 1
        return read_presence(*args, **kwargs)

    monkeypatch.setattr(presence_report, "read_presence", counted)
    retained_results = {}
    for transaction_number in (1, 2):
        with Session(customer_engine) as db:
            db.begin()
            with prepare_owned_window_context(db, **kwargs) as context:
                for index, target in enumerate(campaign_targets, 1):
                    for label, window in (("primary", primary), ("comparison", comparison)):
                        result = context.read(target, window)
                        assert not isinstance(result, KnownWindowGap)
                        assert result.original.presence == header
                        assert (
                            result.original.presence.model_dump_json() == header.model_dump_json()
                        )
                        assert (
                            result.original.native_campaign_id
                            == target.provider_reference.entity_id
                        )
                        assert result.requested_window == window
                        assert result.summary.requested_days == result.summary.returned_days == 1
                        assert result.summary.missing_calendar_days == 0
                        assert result.summary.selected_conversions.value == (
                            "10" if label == "primary" else str(index)
                        )
                        assert result.summary.clicks.value == (
                            100 if label == "primary" else 10 * index
                        )
                        key = (target.provider_reference.entity_id, label)
                        if transaction_number == 1:
                            retained_results[key] = result
                        else:
                            assert result == retained_results[key]
                        assert count == transaction_number
                assert len({r.original_document_digest for r in retained_results.values()}) == 2
        assert count == transaction_number, "new transaction must parse freshly exactly once"
