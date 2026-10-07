"""Pure bounded recommendation-score contribution, never execution authority.

No policy is installed. Storage, invalidation and producer qualification are separate.
"""

from decimal import ROUND_DOWN, Decimal, localcontext
from fractions import Fraction
from typing import Literal

from pydantic import Field, model_validator

from app.commerce.evidence import digest
from app.outcomes.contracts import Code, Digest, Frozen, Positive
from app.outcomes.owned_v3 import OwnedV3Assessment


class FeedbackDecisionPolicy(Frozen):
    schema_version: Literal["inlet.feedback-decision-policy.v1"] = (
        "inlet.feedback-decision-policy.v1"
    )
    family: Code
    version: Positive
    metric_definition_digest: Digest
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    preferred_direction: Literal["higher", "lower"]
    minimum_absolute_relative_signal: Decimal = Field(ge=0, le=1000)
    score_gain: Decimal = Field(gt=0, le=1000)
    maximum_absolute_contribution: Decimal = Field(gt=0, le=1)
    maximum_absolute_total: Decimal = Field(gt=0, le=1)
    allowed_purposes: tuple[Literal["activate", "existing_campaign_optimize"], ...] = Field(
        min_length=1, max_length=2
    )
    basis: Literal["descriptive_association"] = "descriptive_association"

    @property
    def policy_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class FeedbackContribution(Frozen):
    schema_version: Literal["inlet.feedback-contribution.v1"] = "inlet.feedback-contribution.v1"
    environment: Literal["contract_test", "live"]
    workspace_id: Positive
    original_attempt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    assessment_digest: Digest
    policy_digest: Digest | None
    status: Literal["eligible", "ineligible"]
    score: Decimal | None = Field(ge=-1, le=1)
    reasons: tuple[Code, ...]
    interpretation: Literal["policy_weighted_association_not_causal"] = (
        "policy_weighted_association_not_causal"
    )
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def eligibility(self) -> "FeedbackContribution":
        if self.status == "eligible":
            if self.score is None or self.reasons or self.policy_digest is None:
                raise ValueError("eligible contribution requires policy and score")
        elif self.score is not None or not self.reasons:
            raise ValueError("ineligible contribution cannot carry a score")
        return self


def decision_policy_for(family: str) -> FeedbackDecisionPolicy | None:
    return None


def prepare_feedback(
    assessment: OwnedV3Assessment,
    policy: FeedbackDecisionPolicy | None,
    *,
    environment: Literal["contract_test", "live"],
    expected_assessment_digest: str,
) -> FeedbackContribution:
    """Server-only pure preparation; persisted eligibility needs fresh owned rechecks."""
    assessment = OwnedV3Assessment.model_validate(assessment.model_dump())
    if policy is not None:
        policy = FeedbackDecisionPolicy.model_validate(policy.model_dump())
    fingerprint = digest(assessment.model_dump(mode="json"))
    reasons: set[str] = set()
    if fingerprint != expected_assessment_digest:
        reasons.add("assessment_digest_changed")
    if assessment.context.environment != environment:
        reasons.add("assessment_environment_mismatch")
    if assessment.status != "operational_association_as_of":
        reasons.add("assessment_insufficient")
    if policy is None:
        reasons.add("decision_policy_unavailable")
    elif (policy.metric_definition_digest, policy.currency, policy.time_zone) != (
        assessment.context.scope.metric_definition_digest,
        assessment.context.scope.currency,
        assessment.context.scope.time_zone,
    ):
        reasons.add("decision_policy_basis_mismatch")
    if policy is not None and assessment.receipt.purpose not in policy.allowed_purposes:
        reasons.add("action_purpose_unsupported")
    # Recompute from exact totals instead of treating a stored rounded ratio as proof.
    before, after = assessment.before_value_micros, assessment.after_value_micros
    if before is None or after is None or before <= 0:
        reasons.add("positive_baseline_required")
    score = None
    if not reasons and policy is not None and before is not None and after is not None:
        with localcontext() as context:
            context.prec = 60
            context.rounding = ROUND_DOWN
            relative = Fraction(int(after) - int(before), int(before))
            if abs(relative) < Fraction(policy.minimum_absolute_relative_signal):
                reasons.add("signal_below_policy_threshold")
            else:
                oriented = relative if policy.preferred_direction == "higher" else -relative
                raw = oriented * Fraction(policy.score_gain)
                bound = Fraction(policy.maximum_absolute_contribution)
                bounded = max(-bound, min(bound, raw))
                converted = Decimal(bounded.numerator) / Decimal(bounded.denominator)
                score = max(
                    policy.maximum_absolute_contribution.copy_negate(),
                    min(policy.maximum_absolute_contribution, converted),
                )
    return FeedbackContribution(
        environment=environment,
        workspace_id=assessment.context.scope.workspace_id,
        original_attempt_id=assessment.receipt.attempt_id,
        assessment_digest=fingerprint,
        policy_digest=policy.policy_digest if policy else None,
        status="ineligible" if reasons else "eligible",
        score=score,
        reasons=tuple(sorted(reasons)),
    )


def recompute_active_score(
    policy: FeedbackDecisionPolicy,
    contributions: tuple[FeedbackContribution, ...],
    *,
    workspace_id: int,
    environment: Literal["contract_test", "live"],
) -> Decimal:
    """Idempotent read-time projection from active slots; caller handles owned selection."""
    policy = FeedbackDecisionPolicy.model_validate(policy.model_dump())
    if len(contributions) > 1000:
        raise ValueError("active contribution bound exceeded")
    seen: set[str] = set()
    scores = []
    for value in contributions:
        value = FeedbackContribution.model_validate(value.model_dump())
        if (
            value.workspace_id != workspace_id
            or value.environment != environment
            or value.policy_digest != policy.policy_digest
            or value.status != "eligible"
            or value.score is None
            or abs(value.score) > policy.maximum_absolute_contribution
            or value.original_attempt_id in seen
        ):
            raise ValueError("invalid active contribution set")
        seen.add(value.original_attempt_id)
        scores.append(value.score)
    with localcontext() as context:
        context.prec = 80
        context.rounding = ROUND_DOWN
        exact = sum((Fraction(score) for score in scores), Fraction(0))
        bound = Fraction(policy.maximum_absolute_total)
        bounded = max(-bound, min(bound, exact))
        total = Decimal(bounded.numerator) / Decimal(bounded.denominator)
        return max(
            policy.maximum_absolute_total.copy_negate(), min(policy.maximum_absolute_total, total)
        )
