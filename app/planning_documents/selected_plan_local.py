"""Standalone v4 source checks; external authority remains caller-owned."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.billing.entitlements import paid_work
from app.campaign_performance.service import Authorize
from app.customers.access import CustomerPrincipal
from app.goals.progress import _read_goal_progress_locked
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents.creative_inputs import validate_creative_policy
from app.planning_documents.evidence_local import (
    changed,
    check_goal,
    commerce_binding,
    resolve_source_fences,
)
from app.planning_documents.ports import (
    GenerationTicket,
)
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1
from app.planning_documents.selected_plan_reader import load_selected_plan_graph
from app.planning_documents.selected_plan_retained import capture_selected_reporting_pin
from app.planning_documents.selected_policy_contract import assert_selected_ticket_policy
from app.planning_documents.window_local import requested_windows as requested_windows
from app.planning_documents.window_local import saved_catalogs as saved_catalogs
from app.shopify.security import utc


def check_selected_start(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    authorize: Authorize,
    clock: Callable[[], datetime],
) -> None:
    try:
        ticket = GenerationTicket.model_validate(ticket)
        contract = assert_selected_ticket_policy(ticket.policy_version, ticket.policy_digest)
        validate_creative_policy(
            ticket.inputs.creative, contract.policy_version, contract.generator_version
        )
    except ValueError:
        raise changed() from None
    if ticket.inputs.selected_reporting is None:
        raise changed()
    if (principal.user.id, principal.session.digest) != (ticket.actor_id, ticket.session_digest):
        raise changed()
    wid = ticket.inputs.workspace_id
    authorize(db, wid, ticket.actor_id)
    check_goal(db, ticket)
    fresh = resolve_source_fences(
        db,
        principal=principal,
        accounts=ticket.inputs.accounts,
        now=max(utc(clock()), database_utc_now(db)),
    )
    if {s.account: s for s in fresh} != {s.account: s for s in ticket.sources}:
        raise changed()
    if workspace_export_revision(db, wid) != ticket.privacy_revision:
        raise changed()
    authorize(db, wid, ticket.actor_id)


def recheck_selected_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    bundle: SelectedPlanEvidenceBundleV1,
    authorize: Authorize,
    clock: Callable[[], datetime],
) -> None:
    """Reconstruct all reports/gaps locally; never assert current provider absence."""
    ticket = GenerationTicket.model_validate(ticket)
    bundle = SelectedPlanEvidenceBundleV1.model_validate(bundle)
    bundle.assert_ticket(ticket)
    check_selected_start(db, principal=principal, ticket=ticket, authorize=authorize, clock=clock)
    if not bundle.catalogs or len(bundle.context) != 2 or bundle.commerce is None:
        raise changed()
    catalogs = {c.reference.account: c for c in bundle.catalogs}
    for retained in saved_catalogs(db, principal, ticket, clock):
        if catalogs.get(retained.reference.account) != retained:
            raise changed()
    fences = {f.account: f for f in ticket.sources}
    if (
        capture_selected_proof(
            db, principal=principal, ticket=ticket, authorize=authorize, clock=clock
        )
        != bundle.reporting_proof
    ):
        raise changed()
    graphs = {g.source_fence.account: g for g in bundle.selected_captures}
    for account in sorted(ticket.inputs.accounts, key=lambda a: a.account_id):
        catalog = catalogs.get(account)
        if catalog is not None:
            row = db.get(AdvertisingAccount, account.account_id, populate_existing=True)
            native = catalog.catalog.native_observation
            if row is None or (row.currency_code, row.time_zone) != (
                native.currency,
                native.time_zone,
            ):
                raise changed()
        if account in graphs:
            current = load_selected_plan_graph(
                db,
                account=account,
                expected_source=fences[account],
                capture_id=graphs[account].capture.request.capture_id,
            )
            if current != graphs[account]:
                raise changed()
    # Strict bundle validation reconstructs all success/gap slots against these
    # actual whole graphs, including chosen accounts lacking a native catalog.
    bundle.assert_ticket(ticket)
    commerce = bundle.commerce
    current_goal = _read_goal_progress_locked(
        db,
        principal,
        ticket.inputs.workspace_id,
        ticket.inputs.goal.goal_id,
        ticket.inputs.goal.revision,
        clock=clock,
    )
    if (
        current_goal.model_dump(exclude={"as_of"})
        != commerce.document.model_dump(exclude={"as_of"})
        or current_goal.as_of < commerce.document.as_of
        or commerce.reference.source_binding_digest
        != commerce_binding(current_goal, ticket.privacy_revision)
    ):
        raise changed()
    wid = ticket.inputs.workspace_id
    authorize(db, wid, ticket.actor_id)
    final = max(utc(clock()), database_utc_now(db))
    refs = [c.reference for c in bundle.catalogs] + [p.reference for p in bundle.performance]
    refs += [c.reference for c in bundle.context] + [commerce.reference]
    if (
        any(final >= ref.expires_at for ref in refs)
        or final.timestamp() >= principal.session.expires_at
    ):
        raise changed()
    paid_work(db, wid, final)
    authorize(db, wid, ticket.actor_id)
    if max(utc(clock()), database_utc_now(db)) >= min(ref.expires_at for ref in refs):
        raise changed()


def capture_selected_proof(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    authorize: Authorize,
    clock: Callable[[], datetime],
) -> SelectedRetainedProofV1:
    check_selected_start(db, principal=principal, ticket=ticket, authorize=authorize, clock=clock)
    assert ticket.inputs.selected_reporting is not None
    selectors = {s.account_id: s for s in ticket.inputs.selected_reporting}
    proof = SelectedRetainedProofV1(
        accounts=tuple(
            capture_selected_reporting_pin(
                db,
                principal,
                account,
                ticket.privacy_revision,
                selectors.get(account.account_id),
                max(utc(clock()), database_utc_now(db)),
            )
            for account in sorted(ticket.inputs.accounts, key=lambda a: a.account_id)
        )
    )
    proof.assert_inputs(ticket.inputs, ticket.privacy_revision)
    if {p.source_fence.account: p.source_fence for p in proof.accounts} != {
        f.account: f for f in ticket.sources
    }:
        raise changed()
    check_selected_start(db, principal=principal, ticket=ticket, authorize=authorize, clock=clock)
    return proof
