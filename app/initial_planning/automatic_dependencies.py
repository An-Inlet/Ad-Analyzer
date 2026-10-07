"""Atomic initial candidate ownership links. Caller retains workspace fence and transaction."""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.customers.access import CustomerPrincipal
    from app.initial_planning.automatic_contracts import InitialReportedRuleCandidateV1

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.initial_planning.automatic_contracts import InitialReportedRuleWorkV1
from app.initial_planning.automatic_keys import native_identity, opportunity_key, owner_identity
from app.initial_planning.automatic_models import (
    InitialRuleAdmissionOrigin,
    InitialRuleCandidateDependency,
    InitialRuleCandidateObservation,
    InitialRuleOpportunity,
)
from app.optimization_candidates.contracts import CandidateScope
from app.optimization_candidates.models import CandidateJob
from app.shopify.security import utc


def unavailable() -> HTTPException:
    return HTTPException(409, "initial_rule_dependency_unavailable")


def ensure_opportunity(
    db: Session,
    scope: CandidateScope,
    now: datetime,
    expires_at: datetime,
    *,
    allowed_admission_id: str | None = None,
) -> InitialRuleOpportunity:
    key = opportunity_key(scope)
    row = db.get(InitialRuleOpportunity, key[:32], populate_existing=True)
    if row is None:
        if now >= expires_at:
            raise unavailable()
        row = InitialRuleOpportunity(
            id=key[:32],
            workspace_id=scope.account.workspace_id,
            environment=scope.mandate.environment,
            ledger_id=scope.mandate.ledger_id,
            native_account_identity_digest=native_identity(scope),
            budget_owner_identity_digest=owner_identity(scope),
            semantic_key_digest=key,
            created_at=now,
            pending_expires_at=expires_at,
        )
        db.add(row)
        db.flush()
    if (
        row.semantic_key_digest != key
        or row.workspace_id != scope.account.workspace_id
        or row.environment != scope.mandate.environment
        or row.ledger_id != scope.mandate.ledger_id
        or row.native_account_identity_digest != native_identity(scope)
        or row.budget_owner_identity_digest != owner_identity(scope)
        or utc(row.pending_expires_at) <= now
    ):
        raise unavailable()
    if db.scalar(
        select(InitialRuleAdmissionOrigin.admission_id).where(
            InitialRuleAdmissionOrigin.opportunity_id == row.id,
            InitialRuleAdmissionOrigin.admission_id != (allowed_admission_id or ""),
        )
    ):
        raise unavailable()
    return row


def require_initial_dependency(
    db: Session,
    job: CandidateJob,
    work: InitialReportedRuleWorkV1,
) -> None:
    row = db.get(InitialRuleCandidateDependency, job.id, populate_existing=True)
    wid, basis = work.scope.account.workspace_id, work.basis
    if (
        row is None
        or job.workspace_id != wid
        or job.attempt_id is not None
        or job.environment != work.policy.environment
        or job.work != work.model_dump(mode="json")
        or job.input_digest != work.digest()
        or row.workspace_id != wid
        or row.account_id != work.scope.account.account.account_id
        or row.opportunity_id != basis.opportunity_id
        or row.preview_id != basis.preview_id
        or row.calibration_id != basis.calibration_id
        or row.selected_observation_id != basis.selected_observation_id
    ):
        raise unavailable()
    ids = set(
        db.scalars(
            select(InitialRuleCandidateObservation.observation_id).where(
                InitialRuleCandidateObservation.candidate_job_id == job.id,
                InitialRuleCandidateObservation.workspace_id == wid,
            )
        )
    )
    if ids != {r.observation_id for r in basis.observation_references}:
        raise unavailable()


def bind_initial_dependency(
    db: Session, job: CandidateJob, work: InitialReportedRuleWorkV1
) -> None:
    from app.initial_planning.models import PreviewRow

    basis = work.basis
    preview = db.get(PreviewRow, basis.preview_id, populate_existing=True)
    if (
        preview is None
        or preview.workspace_id != job.workspace_id
        or preview.original_actor_id != job.actor_id
        or preview.original_session_digest != job.auth_session_digest
    ):
        raise unavailable()
    if db.get(InitialRuleCandidateDependency, job.id) is None:
        origin = db.get(InitialRuleOpportunity, basis.opportunity_id)
        if origin is None:
            raise unavailable()
        expires = min(utc(preview.expires_at), utc(origin.pending_expires_at))
        db.add(
            InitialRuleCandidateDependency(
                candidate_job_id=job.id,
                workspace_id=preview.workspace_id,
                account_id=preview.account_id,
                campaign_id=preview.campaign_id,
                opportunity_id=basis.opportunity_id,
                preview_id=basis.preview_id,
                calibration_id=basis.calibration_id,
                selected_observation_id=basis.selected_observation_id,
                expires_at=expires,
            )
        )
        db.flush()
        db.add_all(
            [
                InitialRuleCandidateObservation(
                    candidate_job_id=job.id,
                    workspace_id=preview.workspace_id,
                    account_id=preview.account_id,
                    campaign_id=preview.campaign_id,
                    observation_id=ref.observation_id,
                    expires_at=expires,
                )
                for ref in basis.observation_references
            ]
        )
        db.flush()
    require_initial_dependency(db, job, work)


def consume_origin(
    db: Session,
    principal: "CustomerPrincipal",
    work: InitialReportedRuleWorkV1,
    decision: "InitialReportedRuleCandidateV1",
    admission_id: str,
    clock: "Callable[[], datetime]",
) -> None:
    """Called only after the real admission flush, before creating its provider run."""
    from app.initial_planning.automatic_contracts import InitialReportedRuleCandidateV1
    from app.initial_planning.automatic_source import INITIAL_RULE_PRODUCER_FAMILY
    from app.lifecycle.privacy import database_utc_now
    from app.session_automation.contracts import SemanticDecisionEpoch
    from app.session_automation.models import AutomaticDecisionAdmission

    decision = InitialReportedRuleCandidateV1.model_validate_json(decision.model_dump_json())
    job = db.scalar(
        select(CandidateJob)
        .where(
            CandidateJob.workspace_id == work.scope.account.workspace_id,
            CandidateJob.input_digest == work.digest(),
        )
        .execution_options(populate_existing=True)
    )
    if (
        job is None
        or job.actor_id != principal.user.id
        or job.auth_session_digest != principal.session.digest
    ):
        raise unavailable()
    require_initial_dependency(db, job, work)
    row = db.get(InitialRuleOpportunity, work.basis.opportunity_id, populate_existing=True)
    admission = db.get(AutomaticDecisionAdmission, admission_id, populate_existing=True)
    now = max(clock(), database_utc_now(db))
    epoch = SemanticDecisionEpoch(
        producer_family=INITIAL_RULE_PRODUCER_FAMILY,
        source_schema=decision.evidence.source_schema,
        source_reference=work.basis.opportunity_id,
        semantic_digest=work.basis.semantic_key_digest,
    )
    if (
        row is None
        or admission is None
        or row.semantic_key_digest != work.basis.semantic_key_digest
        or utc(row.pending_expires_at) <= now
        or decision.expires_at <= now
        or decision.scope != work.scope
        or decision.evidence.basis != work.basis
        or decision.policy_digest != work.policy.digest()
        or decision.status != "suggested"
        or admission.actor_id != principal.user.id
        or admission.workspace_id != work.scope.account.workspace_id
        or admission.environment != work.policy.environment
        or admission.ledger_id != work.scope.mandate.ledger_id
        or admission.account_identity_digest != native_identity(work.scope)
        or admission.budget_owner_key != work.scope.budget_owner_key
        or admission.candidate_digest != decision.digest()
        or admission.epoch_digest != epoch.digest()
        or admission.producer_family != INITIAL_RULE_PRODUCER_FAMILY
        or admission.evidence_digest != decision.evidence_digest
    ):
        raise unavailable()
    prior = db.get(InitialRuleAdmissionOrigin, admission.id, populate_existing=True)
    if prior is None:
        # Another session/period/policy cannot bootstrap the same owned native budget.
        other = db.scalar(
            select(AutomaticDecisionAdmission.id)
            .where(
                AutomaticDecisionAdmission.workspace_id == admission.workspace_id,
                AutomaticDecisionAdmission.environment == admission.environment,
                AutomaticDecisionAdmission.account_identity_digest
                == admission.account_identity_digest,
                AutomaticDecisionAdmission.budget_owner_key == admission.budget_owner_key,
                AutomaticDecisionAdmission.id != admission.id,
            )
            .limit(1)
        )
        if other is not None:
            raise unavailable()
        db.add(
            InitialRuleAdmissionOrigin(
                admission_id=admission.id,
                workspace_id=admission.workspace_id,
                opportunity_id=row.id,
            )
        )
        db.flush()
    elif prior.workspace_id != admission.workspace_id or prior.opportunity_id != row.id:
        raise unavailable()
