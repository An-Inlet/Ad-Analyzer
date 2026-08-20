from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import Recommendation, RecommendationAudit

DECISION_LEARNING_POLICY_VERSION = "v1"
DECISION_LEARNING_EFFECT = "context_and_equal_impact_tie_break_only"
ESTABLISHED_EVIDENCE_DECISIONS = 5

DecisionEvidenceState = Literal["no_history", "limited", "established"]
_DECISION_ACTIONS = frozenset({"approved", "rejected"})
_SCOPE_TYPES = frozenset({"account", "campaign", "ad_group", "keyword", "search_term"})
_RATE_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True)
class DecisionLearningProfile:
    recommendation_type: str
    scope_type: str
    review_action: str
    approved_count: int
    rejected_count: int
    acceptance_rate: Decimal
    smoothed_acceptance_rate: Decimal
    evidence_state: DecisionEvidenceState
    last_decision_at: datetime

    @property
    def decision_count(self) -> int:
        return self.approved_count + self.rejected_count

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.recommendation_type, self.scope_type, self.review_action)


@dataclass(frozen=True)
class DecisionLearningContext:
    recommendation_type: str
    scope_type: str
    review_action: str
    approved_count: int
    rejected_count: int
    acceptance_rate: Decimal | None
    smoothed_acceptance_rate: Decimal
    evidence_state: DecisionEvidenceState

    @property
    def decision_count(self) -> int:
        return self.approved_count + self.rejected_count

    def as_payload(self) -> dict[str, object]:
        return {
            "policy_version": DECISION_LEARNING_POLICY_VERSION,
            "approved_count": self.approved_count,
            "rejected_count": self.rejected_count,
            "decision_count": self.decision_count,
            "acceptance_rate": (
                str(self.acceptance_rate) if self.acceptance_rate is not None else None
            ),
            "smoothed_acceptance_rate": str(self.smoothed_acceptance_rate),
            "evidence_state": self.evidence_state,
            "effect": DECISION_LEARNING_EFFECT,
            "reason_text_used": False,
        }


@dataclass(frozen=True)
class DecisionLearningSnapshot:
    workspace_id: int
    profiles: tuple[DecisionLearningProfile, ...]

    @property
    def approved_count(self) -> int:
        return sum(profile.approved_count for profile in self.profiles)

    @property
    def rejected_count(self) -> int:
        return sum(profile.rejected_count for profile in self.profiles)

    @property
    def decision_count(self) -> int:
        return self.approved_count + self.rejected_count

    def context_for(
        self,
        recommendation_type: str,
        scope_type: str,
        review_action: str,
    ) -> DecisionLearningContext:
        key = (recommendation_type, scope_type, review_action)
        profile = next((item for item in self.profiles if item.key == key), None)
        if profile is None:
            return DecisionLearningContext(
                recommendation_type=recommendation_type,
                scope_type=scope_type,
                review_action=review_action,
                approved_count=0,
                rejected_count=0,
                acceptance_rate=None,
                smoothed_acceptance_rate=Decimal("0.5000"),
                evidence_state="no_history",
            )
        return DecisionLearningContext(
            recommendation_type=profile.recommendation_type,
            scope_type=profile.scope_type,
            review_action=profile.review_action,
            approved_count=profile.approved_count,
            rejected_count=profile.rejected_count,
            acceptance_rate=profile.acceptance_rate,
            smoothed_acceptance_rate=profile.smoothed_acceptance_rate,
            evidence_state=profile.evidence_state,
        )


@dataclass
class _ProfileAccumulator:
    approved_count: int = 0
    rejected_count: int = 0
    last_decision_at: datetime | None = None


def _rate(numerator: int, denominator: int) -> Decimal:
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        _RATE_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _signal_code(value: object, fallback: str) -> str:
    if (
        isinstance(value, str)
        and 1 <= len(value) <= 96
        and all(
            character.islower() or character.isdigit() or character == "_" for character in value
        )
    ):
        return value
    return fallback


def _profile_key(
    recommendation_type_value: object,
    planned_action_value: object,
) -> tuple[str, str, str]:
    planned_action = planned_action_value
    if not isinstance(planned_action, dict):
        planned_action = {}
    scope = planned_action.get("scope")
    scope_type_value = scope.get("type") if isinstance(scope, dict) else None
    scope_type = (
        scope_type_value
        if isinstance(scope_type_value, str) and scope_type_value in _SCOPE_TYPES
        else "account"
    )
    recommendation_type = _signal_code(recommendation_type_value, "unknown_signal")
    review_action = _signal_code(
        planned_action.get("review_action"),
        recommendation_type,
    )
    return recommendation_type, str(scope_type), review_action


class DecisionLearningService:
    """Derive bounded learning signals from immutable approve/reject audit actions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshot(
        self,
        workspace_id: int,
        *,
        through: datetime | None = None,
    ) -> DecisionLearningSnapshot:
        statement = (
            select(
                Recommendation.id,
                Recommendation.recommendation_type,
                Recommendation.planned_action,
                RecommendationAudit.action,
                RecommendationAudit.created_at,
            )
            .join(
                RecommendationAudit,
                RecommendationAudit.recommendation_id == Recommendation.id,
            )
            .where(
                Recommendation.workspace_id == workspace_id,
                RecommendationAudit.action.in_(_DECISION_ACTIONS),
            )
            .order_by(RecommendationAudit.created_at.asc(), RecommendationAudit.id.asc())
        )
        if through is not None:
            statement = statement.where(RecommendationAudit.created_at < through)
        rows = self.session.execute(statement).tuples().all()
        accumulators: dict[tuple[str, str, str], _ProfileAccumulator] = {}
        decided_recommendations: set[int] = set()
        for recommendation_id, recommendation_type, planned_action, action, created_at in rows:
            if recommendation_id in decided_recommendations:
                continue
            decided_recommendations.add(recommendation_id)
            key = _profile_key(recommendation_type, planned_action)
            accumulator = accumulators.setdefault(key, _ProfileAccumulator())
            if action == "approved":
                accumulator.approved_count += 1
            else:
                accumulator.rejected_count += 1
            accumulator.last_decision_at = created_at

        profiles: list[DecisionLearningProfile] = []
        for key, accumulator in accumulators.items():
            decision_count = accumulator.approved_count + accumulator.rejected_count
            last_decision_at = accumulator.last_decision_at
            if decision_count == 0 or last_decision_at is None:
                continue
            evidence_state: DecisionEvidenceState = (
                "established" if decision_count >= ESTABLISHED_EVIDENCE_DECISIONS else "limited"
            )
            profiles.append(
                DecisionLearningProfile(
                    recommendation_type=key[0],
                    scope_type=key[1],
                    review_action=key[2],
                    approved_count=accumulator.approved_count,
                    rejected_count=accumulator.rejected_count,
                    acceptance_rate=_rate(accumulator.approved_count, decision_count),
                    smoothed_acceptance_rate=_rate(
                        accumulator.approved_count + 1,
                        decision_count + 2,
                    ),
                    evidence_state=evidence_state,
                    last_decision_at=last_decision_at,
                )
            )
        profiles.sort(
            key=lambda profile: (
                -profile.decision_count,
                profile.recommendation_type,
                profile.scope_type,
                profile.review_action,
            )
        )
        return DecisionLearningSnapshot(
            workspace_id=workspace_id,
            profiles=tuple(profiles),
        )
