"""Real owned source/native/commerce paths; explicitly injected v3, no API activation."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.ads.models import Campaign
from app.campaign_performance.models import CurrentPerformance
from app.campaign_performance.presence_models import MetricPresenceRow
from app.collectors import account_diagnostics
from app.customers.models import CustomerSession
from app.meta.models import MetaConnection
from app.planning_documents.context import ReportingWindow
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.read_context import PlanningReadContexts
from app.planning_documents.window_adapter import OwnedWindowEvidenceReader
from app.planning_documents.window_local import recheck_window_sources
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, event, select, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_planning_qualified_reporting import install_presence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def prepared(
    engine: Engine,
    config: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str = "meta_ads",
    state: str | None = "positive",
) -> Any:
    _, old_ticket, principal, calls = setup_evidence(
        engine, config, replicas, monkeypatch, platform
    )
    if state is not None:
        install_presence(engine, old_ticket.inputs.accounts[0].account_id, state)
    primary = old_ticket.inputs.reporting_window
    inputs = old_ticket.inputs.model_copy(
        update={
            "comparison_window": ReportingWindow(
                starts_at=primary.starts_at - timedelta(days=1),
                ends_at_exclusive=primary.starts_at,
            )
        }
    )
    policy = PlanningCompositionPolicy(
        version="inlet.descriptive-review.v3", generator_version="inlet.descriptive-planning.v3"
    )
    ticket = GenerationTicket.model_validate(
        old_ticket.model_copy(
            update={
                "inputs": inputs,
                "policy_version": policy.version,
                "policy_digest": policy.digest(),
            }
        )
    )
    provider = replicas[2]
    reader = OwnedWindowEvidenceReader(
        lambda: Session(engine),
        principal=principal,
        provider=provider,
        policy=policy,
        clock=lambda: datetime.now(UTC),
    )
    return reader, ticket, principal, provider, calls


def final_read(
    engine: Engine, ticket: Any, principal: Any, provider: Any, bundle: Any, clock: Any = None
) -> None:
    reads = PlanningReadContexts(
        lambda: Session(engine), principal, provider, ticket.inputs.workspace_id, ticket.actor_id
    )
    with reads.open() as db:
        recheck_window_sources(
            db,
            principal=principal,
            ticket=ticket,
            bundle=bundle,
            authorize=reads.authorize,
            clock=clock or (lambda: datetime.now(UTC)),
        )
        # Context hooks are gone before caller persistence; ordinary flush remains possible.
        campaign = db.scalar(
            select(Campaign).where(Campaign.account_id == ticket.inputs.accounts[0].account_id)
        )
        if campaign is not None:
            campaign.name = "Rollback-only observer cleanup check"
            db.flush()
        db.rollback()


@pytest.mark.parametrize("state", ["positive", "zero", "missing", "partial"])
def test_actual_meta_primary_and_comparison_gap_with_final_reconstruction(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    reader, ticket, principal, provider, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, state=state
    )
    bundle = reader.collect(ticket)
    bundle.assert_ticket(ticket)
    assert calls and len(bundle.performance) == len(bundle.window_gaps) == 1
    report = bundle.performance[0].document
    assert report.requested_window == ticket.inputs.reporting_window
    assert report.summary.clicks.value == 100
    assert report.summary.selected_conversions.value == (
        "10" if state == "positive" else None if state == "missing" else "0"
    )
    assert report.summary.selected_zero_for_requested_window is (state == "zero")
    gap = bundle.window_gaps[0]
    assert gap.requested_window == ticket.inputs.comparison_window
    assert gap.reason == "outside_imported_window"
    assert bundle.commerce is not None and {c.reference.kind for c in bundle.context} == {
        "customer_context",
        "planning_policy",
    }
    count = len(calls)
    final_read(customer_engine, ticket, principal, provider, bundle)
    assert len(calls) == count, "DB-only final recheck cannot reread providers"


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_all_three_owned_legacy_sources_keep_presence_unavailable_per_window(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    reader, ticket, principal, provider, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch, platform=platform, state=None
    )
    bundle = reader.collect(ticket)
    assert len(bundle.catalogs) == 1 and not bundle.performance
    assert len(bundle.window_gaps) == 2
    assert {g.reason for g in bundle.window_gaps} == {"reporting_presence_unavailable"}
    final_read(customer_engine, ticket, principal, provider, bundle)


@pytest.mark.parametrize(
    "change",
    [
        "mapping",
        "generation",
        "privacy",
        "revocation",
        "current",
        "presence",
        "commerce",
        "goal",
        "owner",
    ],
)
def test_actual_changed_source_aborts_final_recheck_and_caller_write(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.commerce.models import CommerceStore
    from app.customers.models import CustomerMembership
    from app.goals.models import Goal
    from app.lifecycle.privacy import bump_workspace_export_revision

    reader, ticket, principal, provider, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch
    )
    bundle = reader.collect(ticket)
    aid = ticket.inputs.accounts[0].account_id
    with Session(customer_engine) as db:
        if change == "mapping":
            db.execute(
                update(Campaign)
                .where(Campaign.account_id == aid)
                .values(external_campaign_id="999")
            )
        elif change == "generation":
            db.execute(
                update(MetaConnection)
                .where(MetaConnection.account_id == aid)
                .values(generation=MetaConnection.generation + 1)
            )
        elif change == "privacy":
            bump_workspace_export_revision(db, ticket.inputs.workspace_id)
        elif change == "revocation":
            db.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == principal.session.digest)
                .values(revoked_at=int(datetime.now(UTC).timestamp()))
            )
        elif change == "current":
            db.execute(delete(CurrentPerformance).where(CurrentPerformance.account_id == aid))
        elif change == "presence":
            db.execute(delete(MetricPresenceRow))
        elif change == "goal":
            db.execute(
                update(Goal)
                .where(Goal.id == ticket.inputs.goal.goal_id)
                .values(confirmed_preview_id=None)
            )
        elif change == "owner":
            db.execute(
                update(CustomerMembership)
                .where(
                    CustomerMembership.workspace_id == ticket.inputs.workspace_id,
                    CustomerMembership.user_id == principal.user.id,
                )
                .values(status="suspended")
            )
        else:
            db.execute(
                update(CommerceStore)
                .where(CommerceStore.id == ticket.inputs.goal.definition.store_id)
                .values(revision=CommerceStore.revision + 1)
            )
        db.commit()
    with pytest.raises(HTTPException):
        final_read(customer_engine, ticket, principal, provider, bundle)


def test_native_failure_aborts_not_a_catalog_gap_and_no_invented_deadline(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, _, _, calls = prepared(customer_engine, configuration, replicas, monkeypatch)
    original = account_diagnostics.diagnostic_transport
    monkeypatch.setattr(
        account_diagnostics,
        "diagnostic_transport",
        lambda: httpx.MockTransport(
            lambda request: httpx.Response(403, json={"error": {"message": "unavailable"}})
        ),
    )
    from app.collectors.meta_native_inventory import MetaNativeInventoryUnavailable

    with pytest.raises(MetaNativeInventoryUnavailable):
        reader.collect(ticket)
    monkeypatch.setattr(account_diagnostics, "diagnostic_transport", original)
    window = ticket.inputs.reporting_window
    long_inputs = ticket.inputs.model_copy(
        update={
            "comparison_window": None,
            "reporting_window": ReportingWindow(
                starts_at=window.ends_at_exclusive - timedelta(days=367),
                ends_at_exclusive=window.ends_at_exclusive,
            ),
        }
    )
    long_ticket = GenerationTicket.model_validate(ticket.model_copy(update={"inputs": long_inputs}))
    count = len(calls)
    with pytest.raises(HTTPException):
        reader.collect(long_ticket)
    assert len(calls) == count


def test_final_clock_is_sampled_after_waits_and_no_identity_io_under_sql(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, principal, provider, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch
    )
    active: set[int] = set()

    def begin(connection: Any) -> None:
        active.add(id(connection))

    def end(connection: Any) -> None:
        active.discard(id(connection))

    original = provider.check_active

    def check(*args: Any) -> None:
        assert not active
        original(*args)

    monkeypatch.setattr(provider, "check_active", check)
    event.listen(customer_engine, "begin", begin)
    event.listen(customer_engine, "commit", end)
    event.listen(customer_engine, "rollback", end)
    try:
        bundle = reader.collect(ticket)
        expired = min(c.reference.expires_at for c in bundle.catalogs)
        from app.goals.progress import _read_goal_progress_locked
        from app.planning_documents import window_local

        waited = False

        def after_commerce(*args: Any, **kwargs: Any) -> Any:
            nonlocal waited
            result = _read_goal_progress_locked(*args, **kwargs)
            waited = True
            return result

        monkeypatch.setattr(window_local, "_read_goal_progress_locked", after_commerce)
        with pytest.raises(HTTPException):
            final_read(
                customer_engine,
                ticket,
                principal,
                provider,
                bundle,
                clock=lambda: expired if waited else datetime.now(UTC),
            )
        assert waited, "expiry advanced only after final commerce reconstruction"
    finally:
        event.remove(customer_engine, "begin", begin)
        event.remove(customer_engine, "commit", end)
        event.remove(customer_engine, "rollback", end)


def test_empty_catalog_and_reporting_absence_are_distinct_actual_states(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, principal, provider, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch
    )
    factory = account_diagnostics.diagnostic_transport

    def wire(request: httpx.Request) -> httpx.Response:
        transport = factory()
        assert transport is not None
        with transport:
            response = transport.handle_request(request)
            response.read()
        data = response.json()
        if request.url.path.endswith(("/campaigns", "/adsets")):
            data["data"] = []
        return httpx.Response(response.status_code, json=data)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    empty = reader.collect(ticket)
    assert empty.catalogs[0].catalog.targets == ()
    assert {g.reason for g in empty.window_gaps} == {"no_catalog_campaigns"}
    assert all(g.target is None for g in empty.window_gaps)
    final_read(customer_engine, ticket, principal, provider, empty)
    monkeypatch.setattr(account_diagnostics, "diagnostic_transport", factory)
    aid = ticket.inputs.accounts[0].account_id
    with Session(customer_engine) as db:
        current = db.get(CurrentPerformance, aid)
        assert current is not None
        completion_id = current.completion_id
        db.delete(current)
        db.commit()
    absent = reader.collect(ticket)
    assert {g.reason for g in absent.window_gaps} == {"current_reporting_unavailable"}
    assert all(g.target is not None for g in absent.window_gaps)
    final_read(customer_engine, ticket, principal, provider, absent)
    with Session(customer_engine) as db:
        db.add(
            CurrentPerformance(
                account_id=aid, workspace_id=ticket.inputs.workspace_id, completion_id=completion_id
            )
        )
        db.commit()
    with pytest.raises(HTTPException):
        final_read(customer_engine, ticket, principal, provider, absent)


def test_real_meta_56_day_import_primary_comparison_and_outside_slice_source_change(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io
    import json
    from decimal import Decimal
    from urllib.parse import urlsplit

    from app.ads.models import DailyMetric
    from app.lifecycle.privacy import workspace_export_revision
    from app.meta import client as meta_wire
    from app.meta.client import MetaClient
    from app.meta.sync import MetaSyncService
    from app.planning_documents.context import AccountRef
    from app.planning_documents.evidence_local import resolve_source_fences
    from app.publication import customer_intents
    from app.settings import settings

    from tests.test_meta_connection import campaign, insight, page

    reader, old_ticket, principal, provider, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch, state=None
    )
    wid, aid = old_ticket.inputs.workspace_id, old_ticket.inputs.accounts[0].account_id
    now = datetime.now(UTC)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=56)
    rows = []
    for offset in range(56):
        day = (start + timedelta(days=offset)).date().isoformat()
        selected = 10 if offset == 55 else 3 if offset == 48 else 0
        rows.append(
            insight(
                account_id="123",
                campaign_id="5",
                date_start=day,
                date_stop=day,
                impressions="1000",
                clicks="100" if offset == 55 else "1",
                spend="100" if offset == 55 else "1",
                actions=[{"action_type": "purchase", "value": str(selected)}],
                action_values=[{"action_type": "purchase", "value": "0"}],
            )
        )
    responses = [page(campaign("5", "123")), page(), page(*rows)]

    class Opener:
        def open(self, request: Any, timeout: int) -> io.BytesIO:
            assert urlsplit(request.full_url).hostname == "graph.facebook.com"
            assert request.method == "GET" and timeout == 12
            return io.BytesIO(json.dumps(responses.pop(0)).encode())

    monkeypatch.setattr(meta_wire, "build_opener", lambda *_: Opener())
    runtime = Settings(
        _env_file=None,
        AD_ANALYZER_META_ENABLED=True,
        meta_client_id="100000000000001",
        meta_client_secret=settings.meta_client_secret,
        meta_token_encryption_key=settings.meta_token_encryption_key,
        meta_redirect_uri="https://example.test/dashboard/meta/callback",
    )
    with Session(customer_engine) as db:
        runner = MetaSyncService(db, runtime, MetaClient(runtime))
        for expected in ("syncing", "syncing", "complete"):
            assert runner.page(wid, now=now, manual=True)["status"] == expected
    assert not responses
    with Session(customer_engine) as db:
        scope = customer_intents.account(db, wid, aid)
        account = AccountRef(
            workspace_id=wid,
            account_id=aid,
            connection_id=scope.account.connection_id,
            platform="meta_ads",
            connection_version=scope.connection_version,
        )
        inputs = old_ticket.inputs.model_copy(
            update={
                "accounts": (account,),
                "reporting_window": ReportingWindow(
                    starts_at=end - timedelta(days=7), ends_at_exclusive=end
                ),
                "comparison_window": ReportingWindow(
                    starts_at=end - timedelta(days=14), ends_at_exclusive=end - timedelta(days=7)
                ),
            }
        )
        ticket = GenerationTicket.model_validate(
            old_ticket.model_copy(
                update={
                    "inputs": inputs,
                    "sources": resolve_source_fences(
                        db, principal=principal, accounts=(account,), now=now
                    ),
                    "privacy_revision": workspace_export_revision(db, wid),
                }
            )
        )
    bundle = reader.collect(ticket)
    assert not bundle.window_gaps and len(bundle.performance) == 2
    by_window = {p.document.requested_window: p.document for p in bundle.performance}
    primary, comparison = by_window[inputs.reporting_window], by_window[inputs.comparison_window]
    assert primary.summary.selected_conversions.value == "10"
    assert comparison.summary.selected_conversions.value == "3"
    assert primary.original.summary.selected_conversions.value == "13"
    assert primary.original == comparison.original
    assert primary.original.presence.requested_starts_on == start.date()
    assert primary.original.presence.requested_ends_on == (end - timedelta(days=1)).date()
    assert len({p.reference.key for p in bundle.performance}) == 2
    final_read(customer_engine, ticket, principal, provider, bundle)
    with Session(customer_engine) as db:
        # Correction outside both requested slices invalidates the whole original manifest.
        db.execute(
            update(DailyMetric)
            .where(DailyMetric.metric_date == start.date())
            .values(conversions=Decimal(1))
        )
        db.commit()
    with pytest.raises(HTTPException):
        final_read(customer_engine, ticket, principal, provider, bundle)


def test_actual_saved_receipt_reused_and_original_deadline_enforced(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import customer_planning_documents, customer_planning_target_catalog
    from app.planning_documents.catalog_receipts import CatalogReceiptUnavailable
    from app.planning_documents.context import PlanInputRevision

    from tests.test_customer_optimization_api import headers
    from tests.test_planning_documents_api import create_body

    reader, old_ticket, principal, provider, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch
    )
    alice = replicas[0]
    alice.app.include_router(customer_planning_documents.router)
    alice.app.include_router(customer_planning_target_catalog.router)
    root = f"/api/customer/v1/workspaces/{old_ticket.inputs.workspace_id}/planning"
    window = old_ticket.inputs.reporting_window
    response = alice.post(
        root + "/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=old_ticket.inputs.accounts[0].account_id,
            starts_at=window.starts_at.isoformat(),
            ends_at=window.ends_at_exclusive.isoformat(),
        ),
    )
    assert response.status_code == 200, response.text
    observed = response.json()
    target = next(t for t in observed["targets"] if t["entity"]["kind"] == "campaign")
    body = create_body(old_ticket.inputs)
    body["inputs"]["comparison_window"] = old_ticket.inputs.comparison_window.model_dump(
        mode="json"
    )
    body["inputs"]["fixed_allocations"] = [
        dict(
            amount_micros=0,
            target=dict(
                account_id=old_ticket.inputs.accounts[0].account_id,
                canonical_entity_key=target["canonical_entity_key"],
                selection_key=target["selection_key"],
            ),
        )
    ]
    created = alice.post(root + "/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    inputs = PlanInputRevision.model_validate(created.json()["inputs"])
    ticket = GenerationTicket.model_validate(
        old_ticket.model_copy(update={"inputs": inputs, "prepared_at": datetime.now(UTC)})
    )
    count = len(calls)
    bundle = reader.collect(ticket)
    assert len(calls) == count
    assert bundle.catalogs[0].catalog.composite_digest == observed["composite_digest"]
    final_read(customer_engine, ticket, principal, provider, bundle)
    assert len(calls) == count
    with pytest.raises(CatalogReceiptUnavailable) as error:
        final_read(
            customer_engine,
            ticket,
            principal,
            provider,
            bundle,
            clock=lambda: bundle.catalogs[0].reference.expires_at,
        )
    assert error.value.reason == "expired"


def test_current_owner_denial_and_final_failure_roll_back_caller_transaction(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.planning_documents.evidence_local import local_authority
    from app.workspaces.models import Workspace

    reader, ticket, principal, provider, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch
    )
    bundle = reader.collect(ticket)
    wid = ticket.inputs.workspace_id
    with Session(customer_engine) as db:
        before = db.get(Workspace, wid)
        assert before is not None
        original_name = before.name
    reads = PlanningReadContexts(
        lambda: Session(customer_engine), principal, provider, wid, ticket.actor_id
    )
    with pytest.raises(HTTPException), reads.open() as db:
        # A caller write predating recheck must roll back if final acceptance fails.
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.name = "Uncommitted caller work"
        db.flush()
        recheck_window_sources(
            db,
            principal=principal,
            ticket=ticket,
            bundle=bundle,
            authorize=reads.authorize,
            clock=lambda: min(c.reference.expires_at for c in bundle.catalogs),
        )
        db.commit()
    with Session(customer_engine) as db:
        workspace = db.get(Workspace, wid)
        assert workspace is not None and workspace.name == original_name
        foreign = ticket.inputs.accounts[0].model_copy(update={"workspace_id": wid + 1000})
        with pytest.raises(HTTPException):
            local_authority(db, principal, foreign.workspace_id, principal.user.id)
    forged = GenerationTicket.model_validate(ticket.model_copy(update={"session_digest": "f" * 64}))
    with pytest.raises(HTTPException):
        reader.collect(forged)
