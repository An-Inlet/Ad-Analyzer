"""SQL-only paired reconstruction under caller-owned original-session authority."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.billing.entitlements import paid_work
from app.campaign_performance.service import Authorize
from app.customers.access import CustomerPrincipal
from app.lifecycle.privacy import database_utc_now
from app.planning_documents.context import AccountRef
from app.planning_documents.evidence_local import changed
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from app.planning_documents.selected_plan_local import (
    check_selected_start,
    recheck_selected_sources,
)
from app.planning_documents.selected_traffic import RawRangeTrafficGraphV1
from app.planning_documents.selected_traffic_reader import KnownTrafficGap, load_raw_range_traffic
from app.shopify.security import utc


def load_paired_traffic(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    selected: SelectedPlanEvidenceBundleV1,
    authorize: Authorize,
    clock: Callable[[], datetime],
) -> dict[AccountRef, RawRangeTrafficGraphV1 | KnownTrafficGap]:
    check_selected_start(db, principal=principal, ticket=ticket, authorize=authorize, clock=clock)
    graphs: dict[AccountRef, RawRangeTrafficGraphV1 | KnownTrafficGap] = {}
    for proof in selected.reporting_proof.accounts:
        if proof.capture_pin is None:
            continue
        fence = proof.source_fence
        graph = load_raw_range_traffic(
            db, account=fence.account, expected_source=fence, selected_pin=proof.capture_pin
        )
        if (
            graph.pin() if isinstance(graph, RawRangeTrafficGraphV1) else None
        ) != proof.traffic_pin:
            raise changed()
        graphs[fence.account] = graph
    authorize(db, ticket.inputs.workspace_id, ticket.actor_id)
    return graphs


def recheck_selected_paired_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    bundle: SelectedPairedEvidenceV1,
    authorize: Authorize,
    clock: Callable[[], datetime],
) -> None:
    ticket = GenerationTicket.model_validate(ticket)
    bundle = SelectedPairedEvidenceV1.model_validate(bundle)
    bundle.assert_ticket(ticket)
    root = db.get_transaction()
    if root is None or not root.is_active or db.in_nested_transaction():
        raise changed()
    connection = db.connection()
    transaction = connection.get_transaction()
    graphs = load_paired_traffic(
        db,
        principal=principal,
        ticket=ticket,
        selected=bundle.selected,
        authorize=authorize,
        clock=clock,
    )
    if {a: g for a, g in graphs.items() if isinstance(g, RawRangeTrafficGraphV1)} != {
        g.source_fence.account: g for g in bundle.traffic_graphs
    }:
        raise changed()
    for gap in bundle.traffic_gaps:
        actual = graphs.get(gap.account)
        if not isinstance(actual, KnownTrafficGap) or (gap.reason, gap.explanation) != (
            actual.reason,
            actual.explanation,
        ):
            raise changed()
    recheck_selected_sources(
        db,
        principal=principal,
        ticket=ticket,
        bundle=bundle.selected,
        authorize=authorize,
        clock=clock,
    )
    bundle.assert_ticket(ticket)
    selected = bundle.selected
    refs = [c.reference for c in selected.catalogs]
    refs += [p.reference for p in selected.performance]
    refs += [c.reference for c in selected.context]
    refs += [p.reference for p in bundle.traffic]
    if selected.commerce is not None:
        refs.append(selected.commerce.reference)
    authorize(db, ticket.inputs.workspace_id, ticket.actor_id)
    now = max(utc(clock()), database_utc_now(db))
    paid_work(db, ticket.inputs.workspace_id, now)
    authorize(db, ticket.inputs.workspace_id, ticket.actor_id)
    final = max(utc(clock()), database_utc_now(db))
    if (
        db.get_transaction() is not root
        or not root.is_active
        or connection.get_transaction() is not transaction
        or db.in_nested_transaction()
        or db.new
        or db.dirty
        or db.deleted
        or any(final >= utc(ref.expires_at) for ref in refs)
        or final.timestamp() >= principal.session.expires_at
    ):
        raise changed()
