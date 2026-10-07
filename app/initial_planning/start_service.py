"""Exact initial Start: read outside locks, then atomically bind original authority."""

from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.goals import service as goals
from app.initial_planning.automatic_contracts import (
    InitialReportedRulePolicyV1,
    InitialReportedRuleWorkV1,
)
from app.initial_planning.automatic_dependencies import require_initial_dependency
from app.initial_planning.automatic_models import InitialRuleCandidateDependency
from app.initial_planning.automatic_source import INITIAL_RULE_PRODUCER_FAMILY, resolve_initial_work
from app.initial_planning.review_v2_owned import current_preview
from app.initial_planning.start_contracts import (
    InitialRuleAutomaticPolicyV1,
    StartInitialReportedRuleAutomationV1,
)
from app.initial_planning.start_models import InitialRuleSessionStart
from app.optimization_candidates import selection
from app.optimization_candidates import service as candidates
from app.optimization_candidates.contracts import CandidateScope
from app.optimization_candidates.models import CandidateJob
from app.optimization_candidates.selection_contracts import SelectionProvenance
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_contracts import TargetRequest
from app.session_automation import service
from app.session_automation.models import SessionAutomationRun
from app.session_automation.runtime import SessionAutomationRuntime
from app.shopify.security import utc


def unavailable() -> HTTPException:
    return HTTPException(409, "initial_start_basis_unavailable")


def linked_work(
    db: Session, row: SessionAutomationRun, runtime: SessionAutomationRuntime
) -> tuple[CandidateJob, InitialReportedRuleWorkV1]:
    link = db.get(InitialRuleSessionStart, row.id, populate_existing=True)
    job = (
        db.get(CandidateJob, link.candidate_job_id, populate_existing=True)
        if link and link.candidate_job_id
        else None
    )
    if link is None or job is None:
        raise unavailable()
    try:
        work = InitialReportedRuleWorkV1.model_validate(job.work)
    except ValueError as exc:
        raise unavailable() from exc
    if (
        link.workspace_id != row.workspace_id
        or link.candidate_workspace_id != row.workspace_id
        or job.workspace_id != row.workspace_id
        or job.actor_id != row.actor_id
        or job.auth_session_digest != row.original_session_digest
        or job.input_digest != link.input_digest
        or work.digest() != link.input_digest
        or work.basis.preview_digest != link.preview_digest
        or work.basis.semantic_key_digest != link.semantic_key_digest
        or work.scope.mandate != service.binding(row)
        or row.policy_digest != link.policy_digest
        or utc(link.expires_at) <= runtime.clock()
    ):
        raise unavailable()
    matches = [
        p
        for p in runtime.policies
        if isinstance(p, InitialRuleAutomaticPolicyV1)
        and p.workspace_id == row.workspace_id
        and p.digest() == row.policy_digest
    ]
    if len(matches) != 1 or work.policy.digest() != matches[0].candidate_policy_digest:
        raise unavailable()
    require_initial_dependency(db, job, work)
    return job, work


def existing_start(
    db: Session,
    principal: CustomerPrincipal,
    wid: int,
    intent: StartInitialReportedRuleAutomationV1,
    runtime: SessionAutomationRuntime,
) -> SessionAutomationRun | None:
    existing = db.scalar(
        select(SessionAutomationRun).where(
            SessionAutomationRun.workspace_id == wid,
            SessionAutomationRun.actor_id == principal.user.id,
            SessionAutomationRun.original_session_digest == principal.session.digest,
            SessionAutomationRun.mandate_id == intent.mandate.mandate_id,
            SessionAutomationRun.consent_id == intent.mandate.consent_id,
            SessionAutomationRun.policy_digest == intent.expected_policy_digest,
            SessionAutomationRun.stopped_at.is_(None),
            SessionAutomationRun.expires_at > runtime.clock(),
        )
    )
    if existing is not None:
        service.current(db, wid, existing.id, runtime)
        _, work = linked_work(db, existing, runtime)
        if (
            work.basis.preview_id != intent.preview_id
            or work.basis.preview_digest != intent.expected_preview_digest
        ):
            raise unavailable()
        candidates.current(db, work, principal, runtime.review.candidate)
        db.commit()
        return existing
    return None


def start_initial(
    db: Session,
    principal: CustomerPrincipal,
    wid: int,
    intent: StartInitialReportedRuleAutomationV1,
    runtime: SessionAutomationRuntime,
) -> SessionAutomationRun:
    candidates.authorize(db, principal, wid, runtime.review.candidate)
    policy = service.policy_for(db, runtime, wid, intent.policy)
    if (
        not isinstance(policy, InitialRuleAutomaticPolicyV1)
        or policy.digest() != intent.expected_policy_digest
        or policy.semantic_producer_families != (INITIAL_RULE_PRODUCER_FAMILY,)
    ):
        raise unavailable()
    planning = runtime.review.candidate.initial_planning
    numeric = candidates.registered_policy(
        db,
        wid,
        policy.candidate_policy.policy_id,
        policy.candidate_policy.revision,
        runtime.review.candidate,
    )
    if planning is None or not isinstance(numeric, InitialReportedRulePolicyV1):
        raise unavailable()
    _, mandate = mandates.checked(db, wid, intent.mandate, principal.user.id, runtime.clock)
    value, _, _ = current_preview(
        db, principal, runtime.review.candidate.identity, wid, intent.preview_id, planning
    )
    if value.digest() != intent.expected_preview_digest or value.native_observation is None:
        raise unavailable()
    existing = existing_start(db, principal, wid, intent, runtime)
    if existing is not None:
        return existing
    native_request = value.native_observation.request
    request = TargetRequest(
        goal_id=native_request.goal_id,
        goal_revision=native_request.goal_revision,
        goal_digest=fingerprint(
            "inlet.optimization-goal.v1",
            {"definition": goals.current(db, goals.owned(db, wid, mandate.goal_id)).definition},
        ),
        scope=native_request.scope.model_dump(),
    )
    selected = runtime.selected(intent.mandate)
    db.commit()
    catalog = selection.read_catalog(selected, request)
    source = selected.source_fence_reader(
        db,
        selection.SelectionReadRequest(target_request=request, mandate=intent.mandate),
        runtime.clock(),
    )
    db.commit()
    repeated = selection.read_catalog(selected, request)
    if selection.catalog_digest(catalog) != selection.catalog_digest(repeated):
        raise unavailable()
    candidates.authorize(db, principal, wid, runtime.review.candidate)
    _, checked = mandates.checked(db, wid, intent.mandate, principal.user.id, runtime.clock)
    if checked != mandate or service.policy_for(db, runtime, wid, intent.policy) != policy:
        raise unavailable()
    # A competing Start may have committed while provider reads held no locks.
    existing = existing_start(db, principal, wid, intent, runtime)
    if existing is not None:
        return existing
    option, _ = selection.owner_option(repeated, mandate.allowed_target_set_digest)
    if option is None:
        raise unavailable()
    state = option.state
    scope = CandidateScope(
        account=state.scope,
        mandate=intent.mandate,
        goal_id=mandate.goal_id,
        goal_revision=mandate.goal_revision,
        goal_digest=request.goal_digest,
        target=state.target,
        budget_owner_key=state.budget_owner.key(state.scope),
        target_set_digest=state.budget_owner.target_set_digest(),
        source=source,
    )
    provenance = SelectionProvenance(
        actor_id=principal.user.id,
        scope_digest=scope.digest(),
        policy_digest=numeric.digest(),
        catalog_digest=selection.catalog_digest(repeated),
        option_id=option.identifier(request),
        state_digest=state.digest(),
        manifest_digest=fingerprint(
            "inlet.initial-start-selection.v1",
            {
                "preview": intent.expected_preview_digest,
                "catalog": selection.catalog_digest(repeated),
                "mandate": intent.mandate.model_dump(mode="json"),
            },
        ),
        observed_at=repeated.observed_at,
        expires_at=min(repeated.expires_at, value.expires_at),
    )
    work = resolve_initial_work(
        db,
        principal,
        runtime.review.candidate.identity,
        scope,
        provenance,
        intent.preview_id,
        intent.expected_preview_digest,
        numeric,
        planning,
    )
    candidates.current(db, work, principal, runtime.review.candidate)
    job = candidates._insert_checked(db, principal, work, runtime.review.candidate)
    dependency = db.get(InitialRuleCandidateDependency, job.id)
    if dependency is None:
        raise unavailable()
    now = runtime.clock()
    expires = min(
        utc(dependency.expires_at),
        now + timedelta(seconds=policy.lifetime_seconds),
        mandate.ends_at,
        value.expires_at,
        provenance.expires_at,
    )
    if expires <= now:
        raise unavailable()
    row = SessionAutomationRun(
        id=uuid4().hex,
        workspace_id=wid,
        actor_id=principal.user.id,
        original_session_digest=principal.session.digest,
        environment=policy.environment,
        mandate_id=intent.mandate.mandate_id,
        mandate_revision=intent.mandate.revision,
        consent_id=intent.mandate.consent_id,
        mandate_digest=intent.mandate.policy_digest,
        ledger_id=intent.mandate.ledger_id,
        policy_family=policy.policy_family,
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        policy_digest=policy.digest(),
        created_at=now,
        expires_at=expires,
        next_due_at=now,
        state="running",
        reason="ready",
    )
    db.add(row)
    db.flush()
    db.add(
        InitialRuleSessionStart(
            session_run_id=row.id,
            workspace_id=wid,
            candidate_job_id=job.id,
            candidate_workspace_id=wid,
            input_digest=work.digest(),
            preview_digest=value.digest(),
            semantic_key_digest=work.basis.semantic_key_digest,
            policy_digest=policy.digest(),
            created_at=now,
            expires_at=expires,
        )
    )
    db.flush()
    service.current(db, wid, row.id, runtime)
    linked_work(db, row, runtime)
    candidates.current(db, work, principal, runtime.review.candidate)
    db.commit()
    return row
