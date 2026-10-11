"""Standalone collector over actual selected API, native MockHTTP and commerce."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import httpx
import pytest
from app.api.customer_reporting import get_selected_customer_runtime, router
from app.customers.models import CustomerSession
from app.google_connections.http import GoogleHTTPRead, GoogleReadError
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault
from app.google_connections.selected_customer import SelectedCustomerRuntime
from app.planning_documents.evidence_local import resolve_source_fences
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.read_context import PlanningReadContexts
from app.planning_documents.retained_sources import RetainedSourcesChanged
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
    SelectedCaptureSelectorV1,
)
from app.planning_documents.selected_plan_adapter import OwnedSelectedEvidenceReader
from app.planning_documents.selected_plan_local import recheck_selected_sources
from app.settings import Settings
from fastapi import FastAPI, HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_selected_capture_api import prepare
from tests.test_selected_customer_api import CustomerFixture
from tests.test_shopify_sales import configuration as configuration


def prepared(
    engine: Engine,
    config: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    value: str | None = "10",
    selected: bool = True,
) -> Any:
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    _, ticket, principal, calls = setup_evidence(
        engine, config, replicas, monkeypatch, "google_ads"
    )
    f = CustomerFixture.__new__(CustomerFixture)
    f.engine, (f.alice, f.bob, f.provider) = engine, replicas
    f.now, f.hook, f.calls, f.label = datetime.now(UTC), lambda: None, [], "Website purchase"
    f.actor, f.sid, f.wid = principal.user.id, principal.session.digest, ticket.inputs.workspace_id
    f.aid = ticket.inputs.accounts[0].account_id
    with Session(engine) as db:
        source = db.scalar(
            select(GoogleCustomerConnection).where(GoogleCustomerConnection.account_id == f.aid)
        )
        assert source is not None
        f.source_id, f.day = source.id, source.window_start
    f.oauth_transport = httpx.MockTransport(f.handle)
    f.oauth = GoogleHTTPRead(
        "fixture-client",
        SecretStr("fixture-secret"),
        SecretStr("fixture-developer"),
        "v24",
        transport=f.oauth_transport,
    )
    f.runtime = SelectedCustomerRuntime(
        lambda: Session(engine),
        f.oauth,
        Vault(),
        lambda: httpx.MockTransport(f.handle),
        lambda: f.now,
    )
    for client in (f.alice, f.bob):
        application = cast(FastAPI, client.app)
        application.include_router(router)
        application.dependency_overrides[get_selected_customer_runtime] = lambda: f.runtime
    f.base = f"/api/customer/v1/workspaces/{f.wid}/reporting/google"
    f.refresh()
    selectors: tuple[SelectedCaptureSelectorV1, ...] = ()
    if selected:
        body = prepare(f, value)
        response = f.post("/captures", body)
        assert response.status_code == 200, response.text
        selectors = (SelectedCaptureSelectorV1(account_id=f.aid, capture_id=body["request_id"]),)
    policy = PlanningCompositionPolicy(
        version=SELECTED_POLICY_VERSION, generator_version=SELECTED_GENERATOR_VERSION
    )
    inputs = ticket.inputs.model_copy(update={"selected_reporting": selectors})
    reads = PlanningReadContexts(lambda: Session(engine), principal, f.provider, f.wid, f.actor)
    with reads.open() as db:
        sources = resolve_source_fences(
            db, principal=principal, accounts=inputs.accounts, now=datetime.now(UTC)
        )
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(
            update={
                "inputs": inputs,
                "sources": sources,
                "privacy_revision": sources[0].privacy_revision,
                "policy_version": policy.version,
                "policy_digest": policy.digest(),
            }
        )
    )
    reader = OwnedSelectedEvidenceReader(
        lambda: Session(engine),
        principal=principal,
        provider=f.provider,
        policy=policy,
        clock=lambda: datetime.now(UTC),
    )
    return reader, ticket, f, calls


@pytest.mark.parametrize("value,selected", [("10", True), ("0", True), (None, True), ("10", False)])
def test_actual_selected_collector(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
    selected: bool,
) -> None:
    reader, ticket, f, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, value, selected
    )
    bundle = reader.collect(ticket)
    bundle.assert_ticket(ticket)
    assert calls and bundle.commerce is not None and len(bundle.context) == 2
    if selected:
        assert len(bundle.selected_captures) == len(bundle.performance) == 1
        assert bundle.performance[0].document.summary.conversions.value == (
            Decimal(value) if value is not None else None
        )
    else:
        assert not bundle.selected_captures and not bundle.performance
        assert {g.reason for g in bundle.window_gaps} == {"selected_capture_not_requested"}
    reads = PlanningReadContexts(
        lambda: Session(customer_engine), reader.principal, f.provider, f.wid, f.actor
    )
    count = len(calls)
    with reads.open() as db:
        recheck_selected_sources(
            db,
            principal=reader.principal,
            ticket=ticket,
            bundle=bundle,
            authorize=reads.authorize,
            clock=reader.clock,
        )
    assert len(calls) == count


def test_original_session_revoked_at_native_callback(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.collectors import account_diagnostics

    reader, ticket, f, _ = prepared(customer_engine, configuration, replicas, monkeypatch)
    original = account_diagnostics.diagnostic_transport
    transport = original()

    def wire(request: httpx.Request) -> httpx.Response:
        with Session(customer_engine) as db:
            db.execute(
                update(CustomerSession).where(CustomerSession.digest == f.sid).values(revoked_at=1)
            )
            db.commit()
        return transport.handle_request(request)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    with pytest.raises(HTTPException):
        reader.collect(ticket)


@pytest.mark.parametrize("change", ["generation", "head", "capture", "expiry"])
def test_actual_final_reconstruction_denies_change(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.campaign_performance.selected_models import (
        CurrentEventSelectionRow,
        SelectedCaptureRow,
    )
    from sqlalchemy import delete

    reader, ticket, f, _ = prepared(customer_engine, configuration, replicas, monkeypatch)
    bundle = reader.collect(ticket)
    with Session(customer_engine) as db:
        if change == "generation":
            db.execute(
                update(GoogleCustomerConnection)
                .where(GoogleCustomerConnection.account_id == f.aid)
                .values(generation=2)
            )
        elif change == "head":
            db.execute(
                delete(CurrentEventSelectionRow).where(CurrentEventSelectionRow.account_id == f.aid)
            )
        elif change == "capture":
            db.execute(delete(SelectedCaptureRow).where(SelectedCaptureRow.account_id == f.aid))
        db.commit()
    reads = PlanningReadContexts(
        lambda: Session(customer_engine), reader.principal, f.provider, f.wid, f.actor
    )
    with reads.open() as db, pytest.raises((HTTPException, ValueError, RetainedSourcesChanged)):
        recheck_selected_sources(
            db,
            principal=reader.principal,
            ticket=ticket,
            bundle=bundle,
            authorize=reads.authorize,
            clock=(lambda: bundle.catalogs[0].reference.expires_at)
            if change == "expiry"
            else reader.clock,
        )


def test_saved_receipt_reuse(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import customer_planning_documents, customer_planning_target_catalog

    from tests.test_customer_optimization_api import headers
    from tests.test_planning_documents_api import create_body

    reader, ticket, f, calls = prepared(customer_engine, configuration, replicas, monkeypatch)
    f.alice.app.include_router(customer_planning_documents.router)
    f.alice.app.include_router(customer_planning_target_catalog.router)
    root = f"/api/customer/v1/workspaces/{f.wid}/planning"
    window = ticket.inputs.reporting_window
    response = f.alice.post(
        root + "/target-catalog-v2",
        headers=headers(f.alice),
        json=dict(
            account_id=f.aid,
            starts_at=window.starts_at.isoformat(),
            ends_at=window.ends_at_exclusive.isoformat(),
        ),
    )
    assert response.status_code == 200, response.text
    observed = response.json()
    target = next(t for t in observed["targets"] if t["entity"]["kind"] == "campaign")
    body = create_body(ticket.inputs)
    body["inputs"]["selected_reporting"] = [
        s.model_dump(mode="json") for s in ticket.inputs.selected_reporting
    ]
    body["inputs"]["fixed_allocations"] = [
        dict(
            amount_micros=0,
            target=dict(
                account_id=f.aid,
                canonical_entity_key=target["canonical_entity_key"],
                selection_key=target["selection_key"],
            ),
        )
    ]
    # Public creation deliberately rejects v4. Exercise the real internal input
    # writer/receipt binding without registering a generator or bypassing a guard.
    from app.planning_documents import authority, repository
    from app.planning_documents.catalog_receipts import (
        ResolvedInputs,
        bind_input_receipts,
        resolve_input_catalogs,
    )
    from app.planning_documents.input_resolution import prepare as prepare_input
    from app.planning_documents.input_resolution import resolve
    from app.planning_documents.requests import CustomerInputs

    intent = CustomerInputs.model_validate(body["inputs"])
    fact = authority.refresh(reader.principal, f.provider)
    with Session(customer_engine) as db:
        authority.lock(db, reader.principal, f.wid, fact)
        prepared_input = prepare_input(
            db,
            workspace_id=f.wid,
            plan_id=ticket.inputs.plan_id,
            revision=1,
            actor_id=f.actor,
            intent=intent,
            now=datetime.now(UTC),
        )
        resolved = resolve_input_catalogs(
            db,
            principal=reader.principal,
            prepared=prepared_input,
            intent=intent,
            sources=ticket.sources,
            now=datetime.now(UTC),
        )
        inputs = resolve(prepared_input, intent, resolved.catalogs)
        repository.save_input(
            db,
            principal=reader.principal,
            fact=fact,
            document=inputs,
            expected_input_revision=0,
            expected_version=0,
            request_key="selected-collector-input",
            request_digest=intent.digest(),
            now=datetime.now(UTC),
        )
        bind_input_receipts(
            db,
            principal=reader.principal,
            resolved=ResolvedInputs(inputs=inputs, receipt_bindings=resolved.bindings),
            sources=ticket.sources,
            now=datetime.now(UTC),
        )
        authority.final(reader.principal, fact)
        db.commit()
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(update={"inputs": inputs, "prepared_at": datetime.now(UTC)})
    )
    count = len(calls)
    bundle = reader.collect(ticket)
    assert len(calls) == count
    assert bundle.catalogs[0].catalog.composite_digest == observed["composite_digest"]
    assert len(bundle.performance) == 1


def test_all_catalogs_unsupported_abort(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.planning_documents.context import ReportingWindow

    reader, ticket, _, calls = prepared(customer_engine, configuration, replicas, monkeypatch)
    end = ticket.inputs.reporting_window.ends_at_exclusive
    inputs = ticket.inputs.model_copy(
        update={
            "reporting_window": ReportingWindow(
                starts_at=end - timedelta(days=367), ends_at_exclusive=end
            )
        }
    )
    ticket = GenerationTicket.model_validate(ticket.model_copy(update={"inputs": inputs}))
    count = len(calls)
    with pytest.raises(HTTPException):
        reader.collect(ticket)
    assert len(calls) == count


@pytest.mark.parametrize("failure", ["transport", "parser", "none"])
def test_native_and_identity_io_outside_sql(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    from app.collectors import account_diagnostics
    from sqlalchemy import event

    reader, ticket, f, _ = prepared(customer_engine, configuration, replicas, monkeypatch)
    checked_out: set[int] = set()

    def checkout(connection: Any, record: Any, proxy: Any) -> None:
        checked_out.add(id(connection))

    def checkin(connection: Any, record: Any) -> None:
        checked_out.discard(id(connection))

    event.listen(customer_engine, "checkout", checkout)
    event.listen(customer_engine, "checkin", checkin)
    transport = account_diagnostics.diagnostic_transport()
    original_identity = f.provider.check_active

    def identity(subject: str, authenticated_at: int) -> None:
        assert not checked_out, "external identity cannot run under SQL"
        original_identity(subject, authenticated_at)

    def wire(request: httpx.Request) -> httpx.Response:
        assert not checked_out, "native HTTP cannot run under SQL"
        if failure == "transport":
            raise httpx.ConnectError("fixture transport unavailable")
        if failure == "parser":
            return httpx.Response(200, json={"results": "invalid"})
        return transport.handle_request(request)

    monkeypatch.setattr(f.provider, "check_active", identity)
    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    try:
        if failure == "none":
            assert reader.collect(ticket).performance
        else:
            from app.collectors.google_native_inventory import GoogleNativeInventoryUnavailable

            with pytest.raises(
                (HTTPException, ValueError, GoogleNativeInventoryUnavailable, GoogleReadError)
            ):
                reader.collect(ticket)
    finally:
        event.remove(customer_engine, "checkout", checkout)
        event.remove(customer_engine, "checkin", checkin)
        transport.close()


def test_partial_catalog_recheck_keeps_actual_selected_graph(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic partial catalog boundary; real selected graph and SQL final read.

    Normal collection cannot retain any catalog when its global window exceeds
    366 days. This does not claim that the customer receipt endpoint emits one.
    """
    import json
    from uuid import uuid4

    from app.ads.models import AdvertisingAccount
    from app.campaign_performance.selected_models import SelectedCaptureRow
    from app.planning_catalog.metadata_contracts import PlanningMetadataV1
    from app.planning_catalog.projection_v2 import project_v2
    from app.planning_documents.context import AccountRef
    from app.planning_documents.ports import CatalogEvidence, EvidenceGap
    from app.planning_documents.selected_plan_bundle import (
        SelectedPlanEvidenceBundleV1,
        SelectedReportingGapV1,
    )
    from app.planning_documents.selected_plan_local import capture_selected_proof
    from app.publication.contracts import fingerprint as source_digest
    from app.publication.customer_intents import account as owned_account
    from app.workspaces.models import WorkspaceIntegration
    from sqlalchemy import delete

    reader, original_ticket, f, _ = prepared(customer_engine, configuration, replicas, monkeypatch)
    original = reader.collect(original_ticket)
    with Session(customer_engine) as db:
        old = db.get(AdvertisingAccount, f.aid)
        assert old is not None
        integration = WorkspaceIntegration(
            workspace_id=f.wid,
            integration_key="partial-extra",
            provider="google_ads",
            display_name="Extra",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        row = AdvertisingAccount(
            workspace_id=f.wid,
            connection_id=integration.id,
            platform=old.platform,
            external_account_id="9999999999",
            name="Extra",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(row)
        db.flush()
        source = GoogleCustomerConnection(
            id=uuid4().hex,
            workspace_id=f.wid,
            integration_id=integration.id,
            account_id=row.id,
            external_account_id=row.external_account_id,
            status="connected",
            generation=1,
            history_floor=f.day,
            backfill_through=f.day,
            window_start=f.day,
            window_end=f.day,
        )
        db.add(source)
        db.flush()
        scope = owned_account(db, f.wid, row.id)
        ref = AccountRef(
            workspace_id=f.wid,
            account_id=row.id,
            connection_id=integration.id,
            platform="google_ads",
            connection_version=scope.connection_version,
        )
        db.commit()
    reads = PlanningReadContexts(
        lambda: Session(customer_engine), reader.principal, f.provider, f.wid, f.actor
    )
    inputs = original_ticket.inputs.model_copy(
        update={"accounts": (*original_ticket.inputs.accounts, ref)}
    )
    with reads.open() as db:
        fences = resolve_source_fences(
            db, principal=reader.principal, accounts=inputs.accounts, now=datetime.now(UTC)
        )
    ticket = GenerationTicket.model_validate(
        original_ticket.model_copy(update={"inputs": inputs, "sources": fences})
    )
    # Explicit synthetic native catalog for the extra account: no HTTP claim.
    prior = original.catalogs[0]
    from tests.test_planning_metadata_binding import bundle as native_fixture

    inv, meta = native_fixture("google")
    raw = json.loads(inv.model_dump_json().replace("1234567890", "9999999999"))
    raw["request"]["account"] = scope.model_dump(mode="json")
    raw["request"].update(
        currency="USD",
        time_zone="UTC",
        period_start=inputs.reporting_window.starts_at,
        period_end=inputs.reporting_window.ends_at_exclusive,
    )
    raw.update(
        observation_started_at=prior.reference.observation_started_at,
        observed_at=prior.reference.observed_at,
        expires_at=prior.reference.expires_at,
    )
    inv = type(inv).model_validate(raw)
    binding = source_digest("inlet.planning-source.v1", scope.model_dump(mode="json"))
    raw_meta = json.loads(meta.model_dump_json().replace("1234567890", "9999999999"))
    raw_meta.update(
        workspace_id=f.wid,
        account_id=ref.account_id,
        connection_id=ref.connection_id,
        connection_version=ref.connection_version,
        source_binding_digest=binding,
        native_inventory_digest=inv.digest(),
        request_digest=inv.request.digest(),
        reporting_starts_at=inputs.reporting_window.starts_at,
        reporting_ends_at=inputs.reporting_window.ends_at_exclusive,
        observation_started_at=prior.reference.observation_started_at,
        observed_at=prior.reference.observed_at,
        expires_at=prior.reference.expires_at,
    )
    meta = PlanningMetadataV1.model_validate(raw_meta)
    catalog = project_v2(inv, meta)
    cat = CatalogEvidence(
        catalog=catalog,
        reference=prior.reference.model_copy(
            update={
                "key": f"catalog:{ref.account_id}",
                "account": ref,
                "document_digest": catalog.composite_digest,
                "source_binding_digest": binding,
                "source_revision": ref.connection_version,
            }
        ),
    )
    with reads.open() as db:
        proof = capture_selected_proof(
            db,
            principal=reader.principal,
            ticket=ticket,
            authorize=reads.authorize,
            clock=reader.clock,
        )
    by_account = {p.source_fence.account: p for p in proof.accounts}
    from app.planning_documents.composer import targets

    gaps = [
        SelectedReportingGapV1(
            account=original_ticket.inputs.accounts[0],
            target=None,
            requested_window=inputs.reporting_window,
            reason="catalog_unavailable",
            reporting_pin_digest=proof.accounts[0].state_digest(),
            explanation="Explicit synthetic partial catalog boundary.",
        )
    ]
    for target in targets(cat):
        if target.kind == "campaign":
            gaps.append(
                SelectedReportingGapV1(
                    account=ref,
                    target=target,
                    requested_window=inputs.reporting_window,
                    reason="selected_capture_not_requested",
                    reporting_pin_digest=by_account[ref].state_digest(),
                    explanation="No selected capture requested.",
                )
            )
    context = tuple(
        c.model_copy(
            update={
                "document": inputs,
                "reference": c.reference.model_copy(
                    update={
                        "document_digest": inputs.digest(),
                        "source_binding_digest": inputs.digest(),
                    }
                ),
            }
        )
        if c.reference.kind == "customer_context"
        else c
        for c in original.context
    )
    bundle = SelectedPlanEvidenceBundleV1.model_validate(
        original.model_copy(
            update={
                "input_digest": inputs.digest(),
                "catalogs": (cat,),
                "performance": (),
                "reporting_proof": proof,
                "context": context,
                "gaps": (
                    EvidenceGap(
                        account=original_ticket.inputs.accounts[0],
                        section="catalog",
                        reason="unsupported_reporting_window",
                        explanation="Synthetic partial catalog boundary only.",
                    ),
                ),
                "window_gaps": tuple(gaps),
            }
        )
    )
    bundle.assert_ticket(ticket)
    with reads.open() as db:
        recheck_selected_sources(
            db,
            principal=reader.principal,
            ticket=ticket,
            bundle=bundle,
            authorize=reads.authorize,
            clock=reader.clock,
        )
    with Session(customer_engine) as db:
        db.execute(delete(SelectedCaptureRow).where(SelectedCaptureRow.account_id == f.aid))
        db.commit()
    with reads.open() as db, pytest.raises((HTTPException, ValueError, RetainedSourcesChanged)):
        recheck_selected_sources(
            db,
            principal=reader.principal,
            ticket=ticket,
            bundle=bundle,
            authorize=reads.authorize,
            clock=reader.clock,
        )
