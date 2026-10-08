"""Configured operational automation, reconstructed for each actual original session."""

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app import advertising_capabilities
from app.automation import AutomationControlKey, AutomationControlService
from app.commerce.evidence import lock_workspace
from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.initial_planning.start_configuration import InitialRulePolicyBundleV1
from app.optimization_candidates import review_bridge
from app.optimization_candidates.selection import CandidateSelectionRuntime
from app.production_runtime import candidate_assembly
from app.production_runtime.candidate_assembly import configured_candidates
from app.production_runtime.candidate_configuration import (
    load_candidate_configuration,
    validate_candidate_source,
)
from app.production_runtime.candidate_sources import (
    RegisteredInitialRuleSource,
    RegisteredReportedRuleSource,
)
from app.production_runtime.optimization_assembly import pinned
from app.publication.customer_optimization_contracts import TargetCatalog
from app.reported_feedback.candidate_configuration import ReportedRulePolicyBundleV1
from app.session_automation import service, worker
from app.session_automation.models import SessionAutomationRun
from app.session_automation.runtime import SessionAutomationRuntime
from app.settings import Settings
from app.shopify.security import utc


@contextmanager
def configured_session_automation(
    db: Session,
    principal: CustomerPrincipal,
    identity: IdentityProvider,
    configuration: Settings,
) -> Iterator[SessionAutomationRuntime | None]:
    if (
        not advertising_capabilities.advertising_writes_enabled()
        or not configuration.customer_session_automation_enabled
    ):
        yield None
        return
    with configured_candidates(db, principal, identity, configuration) as bundle:
        if (
            bundle is None
            or bundle.mode != "session_automatic"
            or not isinstance(
                bundle.policies, (ReportedRulePolicyBundleV1, InitialRulePolicyBundleV1)
            )
        ):
            yield None
            return

        def unbound_catalog(*_args: object) -> TargetCatalog:
            raise HTTPException(409, "exact_automation_mandate_required")

        yield SessionAutomationRuntime(
            selection=CandidateSelectionRuntime(
                bundle.candidate, unbound_catalog, bundle.owned.source_fence, bundle.candidate.clock
            ),
            review=bundle.review,
            policies=bundle.policies.automatic_policies,
            epoch_producers=(),
            clock=bundle.candidate.clock,
            selection_factory=bundle.selection_for,
        )


def run_configured_session_automation(
    engine: Engine, configuration: Settings, *, limit: int = 10
) -> dict[str, int]:
    if (
        not advertising_capabilities.advertising_writes_enabled()
        or not configuration.customer_session_automation_enabled
    ):
        return {}
    with Session(engine) as db:
        if not AutomationControlService(db).master_enabled(AutomationControlKey.ALL_DATA_SYNCS):
            return {}
    if not 1 <= limit <= 100:
        raise ValueError("bounded automation batch required")
    optimization = pinned(
        configuration.optimization_execution_manifest_path,
        configuration.optimization_execution_manifest_digest,
        configuration.optimization_operating_policy_path,
    )
    if optimization is None:
        return {}
    parsed = load_candidate_configuration(
        configuration.candidate_assembly_manifest_path,
        configuration.candidate_assembly_manifest_digest,
        configuration.candidate_policy_bundle_path,
        optimization_manifest=optimization[0],
    )
    if parsed is None:
        return {}
    manifest, policies = parsed
    source = candidate_assembly.registered_candidate_source(manifest.evidence_source_id)
    if manifest.mode != "session_automatic" or not isinstance(
        source, (RegisteredReportedRuleSource, RegisteredInitialRuleSource)
    ):
        return {}
    validate_candidate_source(manifest, policies, source.descriptor)
    from app.customers.identity import get_identity_provider
    from app.publication.clock import utc_now

    identity = get_identity_provider()
    with Session(engine) as db:
        due = (
            SessionAutomationRun.environment == manifest.environment,
            SessionAutomationRun.stopped_at.is_(None),
            SessionAutomationRun.expires_at > utc_now(),
            SessionAutomationRun.next_due_at <= utc_now(),
        )
        tenants = list(
            db.scalars(
                select(SessionAutomationRun.workspace_id)
                .where(*due)
                .group_by(SessionAutomationRun.workspace_id)
                .order_by(
                    func.min(SessionAutomationRun.next_due_at), SessionAutomationRun.workspace_id
                )
                .limit(limit)
            )
        )
        selected = []
        for wid in tenants:
            identifier = db.scalar(
                select(SessionAutomationRun.id)
                .where(*due, SessionAutomationRun.workspace_id == wid)
                .order_by(SessionAutomationRun.next_due_at, SessionAutomationRun.id)
                .limit(1)
            )
            if identifier:
                selected.append((wid, identifier))
    results: dict[str, int] = {}
    for wid, identifier in selected:
        outcome = "blocked"
        try:
            with Session(engine) as admission_db:
                lock_workspace(admission_db, wid, active=True)
                row = service.load(admission_db, wid, identifier)
                principal = review_bridge.original(
                    admission_db, row.actor_id, row.original_session_digest
                )
                lock_customer_mutation(admission_db, principal, wid, identity)
                admission_db.commit()
                with configured_session_automation(
                    admission_db, principal, identity, configuration
                ) as runtime:
                    if runtime is not None:
                        outcome = worker.advance(engine, wid, identifier, runtime)
        except Exception:
            outcome = "blocked"
        if outcome == "blocked":
            # Failed original authority must not shadow newer sessions in this workspace.
            # This maintenance never creates a claim, changes its fence or releases money.
            with suppress(Exception), Session(engine) as maintenance:
                lock_workspace(maintenance, wid, active=True)
                row = service.load(maintenance, wid, identifier)
                maintenance.refresh(row, with_for_update=True)
                now = utc_now()
                if (
                    row.environment == manifest.environment
                    and row.stopped_at is None
                    and utc(row.next_due_at) <= now
                ):
                    row.next_due_at = now + timedelta(seconds=60)
                    row.state, row.reason = "blocked", "evidence_not_ready"
                    maintenance.commit()
        results[outcome] = results.get(outcome, 0) + 1
    return results
