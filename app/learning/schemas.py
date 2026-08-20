from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.learning.decision import (
    DECISION_LEARNING_EFFECT,
    DECISION_LEARNING_POLICY_VERSION,
    DecisionLearningProfile,
    DecisionLearningSnapshot,
)


class DecisionLearningProfileResponse(BaseModel):
    recommendation_type: str
    scope_type: str
    review_action: str
    decision_count: int
    approved_count: int
    rejected_count: int
    acceptance_rate: Decimal
    smoothed_acceptance_rate: Decimal
    evidence_state: str
    last_decision_at: datetime

    @classmethod
    def from_profile(
        cls,
        profile: DecisionLearningProfile,
    ) -> "DecisionLearningProfileResponse":
        return cls(
            recommendation_type=profile.recommendation_type,
            scope_type=profile.scope_type,
            review_action=profile.review_action,
            decision_count=profile.decision_count,
            approved_count=profile.approved_count,
            rejected_count=profile.rejected_count,
            acceptance_rate=profile.acceptance_rate,
            smoothed_acceptance_rate=profile.smoothed_acceptance_rate,
            evidence_state=profile.evidence_state,
            last_decision_at=profile.last_decision_at,
        )


class DecisionLearningSnapshotResponse(BaseModel):
    workspace_id: int
    policy_version: str
    decision_count: int
    approved_count: int
    rejected_count: int
    reason_text_used: bool
    generation_effect: str
    profiles: list[DecisionLearningProfileResponse]

    @classmethod
    def from_snapshot(
        cls,
        snapshot: DecisionLearningSnapshot,
    ) -> "DecisionLearningSnapshotResponse":
        return cls(
            workspace_id=snapshot.workspace_id,
            policy_version=DECISION_LEARNING_POLICY_VERSION,
            decision_count=snapshot.decision_count,
            approved_count=snapshot.approved_count,
            rejected_count=snapshot.rejected_count,
            reason_text_used=False,
            generation_effect=DECISION_LEARNING_EFFECT,
            profiles=[
                DecisionLearningProfileResponse.from_profile(profile)
                for profile in snapshot.profiles
            ],
        )
