"""Explicit authenticated local candidate binding; never native IO or authority.

The application installs no adapter by default. Live profiles still require the
candidate runtime's independently explicit learning-profile allowlist.
"""

from dataclasses import dataclass, replace
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.directional_feedback.contracts import (
    DirectionalAssociationPolicyV1,
    DirectionalQualificationV1,
    DirectionalRecommendationV1,
)
from app.directional_feedback.evaluator import evaluate_directional_association
from app.directional_feedback.reader import (
    DirectionalReadRuntime,
    Work,
    read_directional_inputs,
    resolve_original_opportunity,
)
from app.optimization_candidates import service as candidates
from app.optimization_candidates.contracts import (
    CandidateDecision,
    CandidateEvidence,
    CandidateObservation,
    CandidateWork,
)
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.selection_contracts import CandidateWorkV2
from app.outcome_feedback.models import ContributionSlot, FeedbackRecord
from app.session_automation.contracts import SemanticDecisionEpoch
from app.session_automation.runtime import SemanticEpochProducer

SCHEMA = "inlet.directional-feedback-candidate.v1"


@dataclass(frozen=True)
class DirectionalCandidateAdapter:
    runtime: DirectionalReadRuntime
    policy_family: str

    def configured(
        self, work: Work
    ) -> tuple[DirectionalAssociationPolicyV1, DirectionalQualificationV1]:
        policy = self.runtime.policies(self.policy_family)
        if (
            policy is None
            or policy.family != self.policy_family
            or policy.candidate_policy_digest != work.policy.digest()
        ):
            raise HTTPException(409, "directional policy unavailable")
        profile = self.runtime.qualifications(policy)
        if profile is None:
            raise HTTPException(409, "directional qualification unavailable")
        return policy, profile

    def recommend(
        self, db: Session, principal: CustomerPrincipal, work: Work
    ) -> tuple[DirectionalRecommendationV1, DirectionalQualificationV1]:
        policy, profile = self.configured(work)
        opportunity = resolve_original_opportunity(db, principal, work, self.runtime.candidate)
        # Choose the active CAS slot for this exact current original action. Never
        # choose a favorable/most-recent assessment by numeric value or timestamp.
        rows = list(
            db.scalars(
                select(FeedbackRecord)
                .join(
                    ContributionSlot,
                    (ContributionSlot.feedback_id == FeedbackRecord.id)
                    & (ContributionSlot.workspace_id == FeedbackRecord.workspace_id),
                )
                .where(
                    ContributionSlot.workspace_id == work.scope.account.workspace_id,
                    ContributionSlot.environment == work.policy.environment,
                    ContributionSlot.attempt_id == opportunity.original_attempt_id,
                    ContributionSlot.policy_family == policy.feedback_family,
                    ContributionSlot.scope_digest == policy.scope_digest,
                )
                .limit(2)
            )
        )
        if len(rows) != 1:
            raise HTTPException(409, "current original feedback unavailable")
        inputs = read_directional_inputs(
            db, principal, work, rows[0].assessment_id, policy, self.runtime
        )
        # Local callbacks may wait on DB locks. Sample after the complete owned read.
        result = evaluate_directional_association(
            inputs, policy, profile, self.runtime.candidate.clock()
        )
        if self.configured(work) != (policy, profile):
            raise HTTPException(409, "directional registration changed during read")
        if result.status == "blocked":
            raise HTTPException(409, "qualified directional evidence unavailable")
        return result, profile

    def transform(
        self,
        db: Session,
        principal: CustomerPrincipal,
        work: Work,
        observation: CandidateObservation,
        now: datetime,
        /,
    ) -> CandidateObservation:
        result, profile = self.recommend(db, principal, work)
        if result.evaluated_at < now or result.expires_at is None:
            raise HTTPException(409, "directional evidence clock changed")
        evidence = CandidateEvidence(
            scope_digest=work.scope.digest(),
            source_schema=SCHEMA,
            source_digest=result.decision_input_digest,
            source_reference=result.opportunity.original_attempt_id,
            qualification="contract_scenario"
            if profile.evidence_mode == "contract_scenario"
            else "qualified_learning",
            qualification_profile=profile.profile_id,
            qualification_revision=profile.revision,
            qualification_digest=profile.qualification_digest,
            direction=result.direction,
            observation_count=result.qualified_completion_count,
            observed_at=result.evaluated_at,
            expires_at=result.expires_at,
        )
        return CandidateObservation(
            scope=observation.scope, state=observation.state, evidence=evidence
        )

    def final_current(
        self,
        db: Session,
        principal: CustomerPrincipal,
        work: Work,
        observation: CandidateObservation,
        /,
    ) -> None:
        self.check_current(db, principal, work, observation.evidence)

    def check_current(
        self, db: Session, principal: CustomerPrincipal, work: Work, evidence: CandidateEvidence
    ) -> tuple[DirectionalRecommendationV1, DirectionalQualificationV1]:
        result, profile = self.recommend(db, principal, work)
        now = self.runtime.candidate.clock()
        expected_qualification = (
            "contract_scenario"
            if profile.evidence_mode == "contract_scenario"
            else "qualified_learning"
        )
        if (
            evidence.source_schema != SCHEMA
            or evidence.scope_digest != work.scope.digest()
            or evidence.source_reference != result.opportunity.original_attempt_id
            or evidence.source_digest != result.decision_input_digest
            or evidence.direction != result.direction
            or evidence.observation_count != result.qualified_completion_count
            or evidence.qualification != expected_qualification
            or evidence.qualification_profile != profile.profile_id
            or evidence.qualification_revision != profile.revision
            or evidence.qualification_digest != profile.qualification_digest
            or not evidence.observed_at <= now < evidence.expires_at
            or result.expires_at is None
            or evidence.expires_at > result.expires_at
        ):
            raise HTTPException(409, "directional evidence changed before candidate publication")

        return result, profile

    def epoch_producer(self) -> SemanticEpochProducer | None:
        policy = self.runtime.policies(self.policy_family)
        profile = self.runtime.qualifications(policy) if policy is not None else None
        if policy is None or profile is None:
            return None

        def authorized_read(
            db: Session, principal: CustomerPrincipal, decision: CandidateDecision
        ) -> SemanticDecisionEpoch:
            wid = decision.scope.account.workspace_id
            candidates.authorize(db, principal, wid, self.runtime.candidate)
            matches = list(
                db.execute(
                    select(CandidateResult, CandidateJob)
                    .join(
                        CandidateJob,
                        (CandidateJob.id == CandidateResult.job_id)
                        & (CandidateJob.workspace_id == CandidateResult.workspace_id),
                    )
                    .where(
                        CandidateResult.workspace_id == wid,
                        CandidateResult.decision_digest == decision.digest(),
                        CandidateJob.state == "completed",
                        CandidateJob.actor_id == principal.user.id,
                        CandidateJob.auth_session_digest == principal.session.digest,
                    )
                    .limit(2)
                )
            )
            if len(matches) != 1:
                raise HTTPException(409, "unique original-session directional candidate required")
            row, job = matches[0]
            saved = candidates.read_result(
                db, wid, row.id, principal, self.runtime.candidate, erase_invalid=False
            )
            if saved != decision or saved.status != "suggested":
                raise HTTPException(409, "current directional candidate required")
            work = candidates.owned_work(job)
            if not isinstance(work, (CandidateWork, CandidateWorkV2)):
                raise HTTPException(409, "directional source kind mismatch")
            result, current_profile = self.check_current(db, principal, work, decision.evidence)
            if (
                current_profile.producer_family != profile.producer_family
                or current_profile.environment != policy.environment
            ):
                raise HTTPException(409, "directional epoch registration changed")
            candidates.authorize(db, principal, wid, self.runtime.candidate)
            return SemanticDecisionEpoch(
                producer_family=profile.producer_family,
                source_schema=SCHEMA,
                source_reference=result.opportunity.original_attempt_id,
                semantic_digest=result.opportunity.semantic_digest,
            )

        return SemanticEpochProducer(
            family=profile.producer_family,
            source_schema=SCHEMA,
            environment=policy.environment,
            authorized_read=authorized_read,
        )

    def bind(self) -> candidates.CandidateRuntime:
        candidate = self.runtime.candidate
        if (
            candidate.authorized_evidence_transform is not None
            or candidate.authorized_final_evidence_current is not None
        ):
            raise ValueError("directional adapter cannot replace existing authorized callbacks")
        return replace(
            candidate,
            feedback_dependent_schemas=candidate.feedback_dependent_schemas | {SCHEMA},
            authorized_evidence_transform=self.transform,
            authorized_final_evidence_current=self.final_current,
        )
