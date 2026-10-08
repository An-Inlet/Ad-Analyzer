"""DB-only v3 source reconstruction; callers own identity refresh and transactions."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.billing.entitlements import paid_work
from app.campaign_performance.service import Authorize
from app.customers.access import CustomerPrincipal
from app.goals.progress import _read_goal_progress_locked
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents.catalog_receipts import resolve_saved_input_catalogs
from app.planning_documents.composer import targets
from app.planning_documents.context import ReportingWindow
from app.planning_documents.evidence_local import (
    changed,
    check_goal,
    commerce_binding,
    resolve_source_fences,
)
from app.planning_documents.models import PlanInputRow
from app.planning_documents.policy_capabilities import ticket_reporting_capability
from app.planning_documents.ports import CatalogEvidence, GenerationTicket
from app.planning_documents.retained_sources import capture_reporting_presence_pin
from app.planning_documents.window_evidence import (
    KnownWindowGap,
    WindowEvidenceBundleV1,
    _window_instants,
)
from app.planning_documents.window_reader import prepare_owned_window_context
from app.shopify.security import utc


def requested_windows(ticket: GenerationTicket) -> tuple[ReportingWindow, ...]:
    return (ticket.inputs.reporting_window,) + (
        (ticket.inputs.comparison_window,) if ticket.inputs.comparison_window is not None else ()
    )


def saved_catalogs(
    db: Session,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    clock: Callable[[], datetime],
) -> tuple[CatalogEvidence, ...]:
    inputs = ticket.inputs
    if (
        inputs.excluded_entity_keys
        or inputs.fixed_allocations
        or any(s.allocations for s in inputs.scenario_intents)
        or db.get(PlanInputRow, (inputs.workspace_id, inputs.plan_id, inputs.revision)) is not None
    ):
        return resolve_saved_input_catalogs(
            db,
            principal=principal,
            ticket=ticket,
            now=max(utc(clock()), database_utc_now(db)),
        ).catalogs
    return ()


def check_start(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    authorize: Authorize,
    clock: Callable[[], datetime],
) -> None:
    if (
        ticket_reporting_capability(ticket.policy_version, ticket.policy_digest).mode
        != "presence_requested_window"
    ):
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


def recheck_window_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    bundle: WindowEvidenceBundleV1,
    authorize: Authorize,
    clock: Callable[[], datetime],
) -> None:
    """Reconstruct all reports/gaps locally; never assert current provider absence."""
    ticket = GenerationTicket.model_validate(ticket)
    bundle = WindowEvidenceBundleV1.model_validate(bundle)
    bundle.assert_ticket(ticket)
    check_start(db, principal=principal, ticket=ticket, authorize=authorize, clock=clock)
    if not bundle.catalogs or len(bundle.context) != 2 or bundle.commerce is None:
        raise changed()
    catalogs = {c.reference.account: c for c in bundle.catalogs}
    for retained in saved_catalogs(db, principal, ticket, clock):
        if catalogs.get(retained.reference.account) != retained:
            raise changed()
    fences = {f.account: f for f in ticket.sources}
    pins = {p.account: p for p in bundle.reporting_pins}
    for account in sorted(ticket.inputs.accounts, key=lambda a: a.account_id):
        catalog = catalogs.get(account)
        if catalog is None:
            # Operation-owned catalog gap is historical collection status, not native truth.
            if (
                capture_reporting_presence_pin(db, principal, account, ticket.privacy_revision)
                != pins[account].document_digest
            ):
                raise changed()
            continue
        row = db.get(AdvertisingAccount, account.account_id, populate_existing=True)
        native = catalog.catalog.native_observation
        if row is None or (row.currency_code, row.time_zone) != (native.currency, native.time_zone):
            raise changed()
        with prepare_owned_window_context(
            db,
            principal=principal,
            account=account,
            expected_source=fences[account],
            expected_reporting_pin=pins[account],
            catalog=catalog,
            authorize=authorize,
            clock=clock,
        ) as context:
            for target in targets(catalog):
                if target.kind != "campaign":
                    continue
                for window in requested_windows(ticket):
                    current = context.read(target, window)
                    if isinstance(current, KnownWindowGap):
                        matches = [
                            g
                            for g in bundle.window_gaps
                            if g.target == target
                            and _window_instants(g.requested_window) == _window_instants(window)
                        ]
                        if len(matches) != 1 or matches[0].reason != current.reason:
                            raise changed()
                    else:
                        matches_reports = [
                            p
                            for p in bundle.performance
                            if p.target == target
                            and _window_instants(p.document.requested_window)
                            == _window_instants(window)
                        ]
                        if len(matches_reports) != 1 or matches_reports[0].document != current:
                            raise changed()
        # No context/listener survives into commerce, final checks, or caller writes.
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
