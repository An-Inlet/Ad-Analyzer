"""Resolve exactly one durable authority origin; failure never falls back to approval."""

from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionReview,
    ProviderExecutionRun,
)
from app.publication.optimization_execution_contracts import OptimizationRuntime
from app.publication.service import owner
from app.session_automation.contracts import (
    CustomerExactApprovalAuthority,
    SessionMandateDecisionAuthority,
)
from app.session_automation.models import AutomaticDecisionAdmission


def automatic(row: ProviderExecutionReview) -> bool:
    # Historical non-candidate reviews do not load later optional marker columns.
    return bool(row.candidate_provenance_required and row.automatic_authority_required)


def resolve(
    db: Session,
    row: ProviderExecutionReview,
    authority: CustomerExactApprovalAuthority | SessionMandateDecisionAuthority,
    actor: str,
    runtime: OptimizationRuntime,
    clock: Callable[[], datetime],
) -> None:
    if isinstance(authority, CustomerExactApprovalAuthority):
        if automatic(row):
            raise HTTPException(409, "automatic authority cannot become customer approval")
        approval = db.get(ProviderExecutionApproval, row.id)
        if approval is None or (approval.review_digest, approval.plan_digest) != (
            row.digest,
            row.plan_digest,
        ):
            raise HTTPException(409, "exact optimization approval required")
        owner(db, row.workspace_id, approval.actor)
        return
    if not automatic(row) or runtime.automatic_authority_guard is None:
        raise HTTPException(409, "automatic decision authority unavailable")
    admission = db.get(AutomaticDecisionAdmission, authority.admission_id, populate_existing=True)
    if admission is None or (
        admission.workspace_id,
        admission.review_id,
        admission.review_digest,
        admission.plan_digest,
        admission.actor_id,
    ) != (row.workspace_id, row.id, row.digest, row.plan_digest, actor):
        raise HTTPException(409, "automatic decision binding changed")
    runtime.automatic_authority_guard(db, row.workspace_id, row.id, actor, clock)


def for_run(
    run: ProviderExecutionRun,
) -> CustomerExactApprovalAuthority | SessionMandateDecisionAuthority:
    if run.authority_kind == "customer_exact_approval" and run.automatic_decision_id is None:
        return CustomerExactApprovalAuthority()
    if run.authority_kind == "mandate_automatic_decision" and run.automatic_decision_id is not None:
        return SessionMandateDecisionAuthority(admission_id=run.automatic_decision_id)
    raise HTTPException(409, "optimization authority unavailable")
