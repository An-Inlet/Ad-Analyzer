"""Real customer Start/Stop and current original-session authority, without provider IO."""

from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.optimization_candidates import review_bridge
from app.optimization_candidates import service as candidates
from app.optimization_candidates.contracts import CandidatePolicy
from app.publication import execution_mandates as mandates
from app.publication.execution_contracts import ProviderMandateBinding, ProviderMandatePolicy
from app.publication.service import owner
from app.reported_feedback.automatic_contracts import (
    ReportedRuleAutomaticPolicyV1,
    StartReportedRuleAutomationV1,
)
from app.reported_feedback.candidate_contracts import ReportedRulePolicyV1
from app.session_automation.contracts import (
    AutomaticPolicyRef,
    SessionAutomationStatus,
    StartSessionAutomation,
)
from app.session_automation.models import SessionAutomationRun
from app.session_automation.runtime import AutomaticPolicyDocument, SessionAutomationRuntime
from app.shopify.security import utc

SESSION_MESSAGE = (
    "Runs only while the session that started it remains valid. Signing out stops future "
    "changes. Stopping cannot undo a change already sent."
)


def binding(row: SessionAutomationRun) -> ProviderMandateBinding:
    return ProviderMandateBinding(
        mandate_id=row.mandate_id,
        revision=row.mandate_revision,
        consent_id=row.consent_id,
        policy_digest=row.mandate_digest,
        ledger_id=row.ledger_id,
        environment=row.environment,
    )


def policy_for(
    db: Session, runtime: SessionAutomationRuntime, wid: int, ref: AutomaticPolicyRef
) -> AutomaticPolicyDocument:
    matches = [
        p
        for p in runtime.policies
        if p.workspace_id == wid and p.policy_id == ref.policy_id and p.revision == ref.revision
    ]
    if len(matches) != 1 or matches[0].environment != runtime.review.execution.environment:
        raise HTTPException(409, "policy_not_available")
    policy = matches[0]
    numeric = candidates.registered_policy(
        db,
        wid,
        policy.candidate_policy.policy_id,
        policy.candidate_policy.revision,
        runtime.selection.candidate,
    )
    if (
        numeric is None
        or numeric.digest() != policy.candidate_policy_digest
        or (
            isinstance(policy, ReportedRuleAutomaticPolicyV1)
            != isinstance(numeric, ReportedRulePolicyV1)
        )
        or (
            isinstance(numeric, CandidatePolicy)
            and (numeric.budget_step_micros is None or numeric.minimum_observations is None)
        )
        or (policy.environment == "live" and not runtime.review.execution.live_enabled)
    ):
        raise HTTPException(409, "policy_not_available")
    if (
        runtime.selection.candidate.environment != policy.environment
        or runtime.review.candidate.environment != policy.environment
        or runtime.review.execution.environment != policy.environment
        or (
            not isinstance(policy, ReportedRuleAutomaticPolicyV1)
            and not any(
                p.environment == policy.environment
                and p.family in policy.semantic_producer_families
                and (p.authorized_read is not None or p.read is not None)
                for p in runtime.epoch_producers
            )
        )
    ):
        raise HTTPException(409, "evidence_not_ready")
    return policy


def load(db: Session, wid: int, identifier: str) -> SessionAutomationRun:
    row = db.get(SessionAutomationRun, identifier, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "automation unavailable")
    return row


def current(
    db: Session, wid: int, identifier: str, runtime: SessionAutomationRuntime
) -> tuple[SessionAutomationRun, CustomerPrincipal, AutomaticPolicyDocument, ProviderMandatePolicy]:
    row = load(db, wid, identifier)
    principal = review_bridge.original(db, row.actor_id, row.original_session_digest)
    candidates.authorize(db, principal, wid, runtime.review.candidate)
    ledger, mandate = mandates.checked(db, wid, binding(row), row.actor_id, runtime.clock)
    policy = policy_for(
        db, runtime, wid, AutomaticPolicyRef(policy_id=row.policy_id, revision=row.policy_revision)
    )
    db.refresh(row, with_for_update=True)
    if (
        row.stopped_at is not None
        or row.state == "stopped"
        or utc(row.expires_at) <= runtime.clock()
        or policy.digest() != row.policy_digest
        or policy.policy_family != row.policy_family
        or ledger.id != row.ledger_id
        or "existing_campaign_optimize" not in mandate.allowed_purposes
    ):
        raise HTTPException(409, "original_session_ended")
    # Session/provider eligibility may wait; always sample policy expiry afterwards.
    candidates.authorize(db, principal, wid, runtime.review.candidate)
    if utc(row.expires_at) <= runtime.clock():
        raise HTTPException(409, "original_session_ended")
    return row, principal, policy, mandate


def start(
    db: Session,
    principal: CustomerPrincipal,
    wid: int,
    intent: StartSessionAutomation | StartReportedRuleAutomationV1,
    runtime: SessionAutomationRuntime,
) -> SessionAutomationRun:
    candidates.authorize(db, principal, wid, runtime.review.candidate)
    policy = policy_for(db, runtime, wid, intent.policy)
    if isinstance(policy, ReportedRuleAutomaticPolicyV1):
        if (
            not isinstance(intent, StartReportedRuleAutomationV1)
            or intent.expected_policy_digest != policy.digest()
        ):
            raise HTTPException(409, "explicit_reported_rule_start_required")
    elif not isinstance(intent, StartSessionAutomation):
        raise HTTPException(409, "automatic_policy_basis_changed")
    ledger, mandate = mandates.checked(db, wid, intent.mandate, principal.user.id, runtime.clock)
    if policy.environment != intent.mandate.environment or (
        "existing_campaign_optimize" not in mandate.allowed_purposes
    ):
        raise HTTPException(409, "mandate_changed")
    existing = db.scalar(
        select(SessionAutomationRun).where(
            SessionAutomationRun.workspace_id == wid,
            SessionAutomationRun.actor_id == principal.user.id,
            SessionAutomationRun.original_session_digest == principal.session.digest,
            SessionAutomationRun.mandate_id == intent.mandate.mandate_id,
            SessionAutomationRun.mandate_revision == intent.mandate.revision,
            SessionAutomationRun.consent_id == intent.mandate.consent_id,
            SessionAutomationRun.policy_digest == policy.digest(),
            SessionAutomationRun.stopped_at.is_(None),
            SessionAutomationRun.expires_at > runtime.clock(),
        )
    )
    if existing is not None:
        current(db, wid, existing.id, runtime)
        db.commit()
        return existing
    candidates.authorize(db, principal, wid, runtime.review.candidate)
    now = runtime.clock()
    expires = min(now + timedelta(seconds=policy.lifetime_seconds), mandate.ends_at)
    if expires <= now:
        raise HTTPException(409, "mandate_changed")
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
        ledger_id=ledger.id,
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
    current(db, wid, row.id, runtime)
    db.commit()
    return row


def stop(
    db: Session,
    principal: CustomerPrincipal,
    wid: int,
    identifier: str,
    identity: IdentityProvider,
    runtime: SessionAutomationRuntime | None,
) -> SessionAutomationRun:
    # A fresh current owner may revoke an expired original session's run. This is
    # revocation only; it never reuses that session for admission or emission.
    lock_customer_mutation(db, principal, wid, identity)
    owner(db, wid, principal.user.id)
    row = load(db, wid, identifier)
    db.refresh(row, with_for_update=True)
    if row.stopped_at is None:
        from datetime import UTC, datetime

        row.stopped_at = runtime.clock() if runtime else datetime.now(UTC)
        row.stopped_by = principal.user.id
        row.state, row.reason = "stopped", "customer_stopped"
    db.commit()
    return row


def status(
    db: Session, wid: int, identifier: str, runtime: SessionAutomationRuntime | None
) -> SessionAutomationStatus:
    row = load(db, wid, identifier)
    values: dict[str, object] = dict(
        run_id=row.id,
        status=row.state,
        reason=row.reason,
        environment=row.environment,
        message=SESSION_MESSAGE,
    )
    if row.stopped_at is not None:
        values.update(status="stopped", reason="customer_stopped")
    elif runtime is None:
        values.update(status="unavailable", reason="automation_not_available")
    elif utc(row.expires_at) <= runtime.clock():
        values.update(status="expired", reason="original_session_ended")
    else:
        try:
            current(db, wid, identifier, runtime)
        except HTTPException as exc:
            known = {
                "policy_not_available",
                "evidence_not_ready",
                "original_session_ended",
                "mandate_changed",
                "source_changed",
            }
            reason = (
                exc.detail
                if isinstance(exc.detail, str) and exc.detail in known
                else "original_session_ended"
                if exc.status_code in {401, 403, 404}
                else "mandate_changed"
            )
            values.update(status="blocked", reason=reason)
    return SessionAutomationStatus.model_validate(values)
