"""Pure explicit heuristic; actual source guarantees must come from trusted facts."""

from datetime import datetime, timedelta

from app.commerce.evidence import digest
from app.directional_feedback.contracts import (
    Direction,
    DirectionalAssociationPolicyV1,
    DirectionalInputsV1,
    DirectionalQualificationV1,
    DirectionalRecommendationV1,
)


def evaluate_directional_association(
    inputs: DirectionalInputsV1,
    policy: DirectionalAssociationPolicyV1 | None,
    qualification: DirectionalQualificationV1 | None,
    now: datetime,
) -> DirectionalRecommendationV1:
    inputs = DirectionalInputsV1.model_validate(inputs.model_dump())
    snapshot, opportunity, facts = inputs.snapshot, inputs.opportunity, inputs.facts
    reasons: set[str] = set()
    if policy is None:
        reasons.add("directional_policy_unavailable")
    if qualification is None:
        reasons.add("directional_qualification_unavailable")
    if facts is None:
        reasons.add("qualified_source_facts_unavailable")
    if snapshot.status != "available" or snapshot.score is None:
        reasons.add("active_association_unavailable")
    if (
        opportunity.workspace_id != snapshot.scope.source.workspace_id
        or opportunity.environment != snapshot.scope.environment
        or opportunity.native_account_digest
        != digest(
            [
                "inlet.native-feedback-account.v1",
                snapshot.scope.account.account.platform,
                snapshot.scope.account.external_advertiser_id,
            ]
        )
        or opportunity.budget_owner_key != snapshot.scope.budget_owner_key
        or opportunity.original_attempt_id
        not in {c.original_attempt_id for c in snapshot.contributions}
    ):
        reasons.add("original_opportunity_mismatch")
    if len(inputs.original_changes) != len(snapshot.contributions):
        reasons.add("complete_intervention_cohort_required")
    if policy is not None:
        policy = DirectionalAssociationPolicyV1.model_validate(policy.model_dump())
        if (
            policy.environment != snapshot.scope.environment
            or policy.scope_digest != snapshot.scope.scope_digest
            or policy.feedback_policy_digest != snapshot.policy_digest
            or policy.feedback_family != snapshot.family
        ):
            reasons.add("directional_policy_scope_changed")
        if len(snapshot.contributions) < policy.minimum_contributions:
            reasons.add("insufficient_active_contributions")
        if any(change != policy.original_change for change in inputs.original_changes):
            reasons.add("intervention_cohort_mismatch")
        if any(
            not 0 <= (now - c.assessed_at).total_seconds() <= policy.maximum_assessment_age_seconds
            for c in snapshot.contributions
        ):
            reasons.add("assessment_age_unqualified")
    if qualification is not None:
        qualification = DirectionalQualificationV1.model_validate(qualification.model_dump())
        if policy is None or (
            qualification.policy_digest != policy.policy_digest
            or qualification.profile_id != policy.qualification_profile
            or qualification.calibration_digest != policy.calibration_digest
            or qualification.scope_digest != policy.scope_digest
            or qualification.environment != policy.environment
        ):
            reasons.add("qualification_policy_mismatch")
        if not qualification.starts_at <= now < qualification.ends_at:
            reasons.add("qualification_expired")
        if (
            snapshot.scope.environment == "live"
            and qualification.evidence_mode != "qualified_server_producer"
        ):
            reasons.add("contract_qualification_cannot_enable_live")
    if facts is not None:
        if (
            facts.environment != snapshot.scope.environment
            or facts.snapshot_digest != snapshot.snapshot_digest
            or qualification is None
            or facts.producer_family != qualification.producer_family
            or facts.evidence_mode != qualification.evidence_mode
        ):
            reasons.add("qualified_facts_scope_changed")
        if (
            facts.correction_state != "settled_as_of"
            or facts.delivery_time != "authoritative_interval"
        ):
            reasons.add("source_or_delivery_assurance_unavailable")
        if (
            snapshot.scope.environment == "live"
            and facts.evidence_mode != "qualified_server_producer"
        ):
            reasons.add("contract_facts_cannot_enable_live")
        if policy is not None:
            if len(facts.completion_digests) < policy.minimum_qualified_completions:
                reasons.add("insufficient_qualified_completions")
            if (
                not 0
                <= (now - facts.fresh_through).total_seconds()
                <= policy.maximum_facts_age_seconds
                or now >= facts.valid_until
            ):
                reasons.add("qualified_facts_expired")
    direction: Direction = "none"
    expires = None
    if not reasons:
        assert (
            policy is not None
            and qualification is not None
            and facts is not None
            and snapshot.score is not None
        )
        if snapshot.score >= policy.positive_cutoff:
            direction = policy.above_direction
        elif snapshot.score <= policy.negative_cutoff:
            direction = policy.below_direction
        expires = min(
            now + timedelta(seconds=policy.decision_lifetime_seconds),
            qualification.ends_at,
            facts.valid_until,
            facts.fresh_through + timedelta(seconds=policy.maximum_facts_age_seconds),
            min(c.assessed_at for c in snapshot.contributions)
            + timedelta(seconds=policy.maximum_assessment_age_seconds),
        )
        if expires <= now:
            reasons.add("no_positive_decision_lifetime")
            direction, expires = "none", None
    return DirectionalRecommendationV1(
        status="blocked" if reasons else "recommended" if direction != "none" else "no_change",
        direction=direction,
        reasons=tuple(sorted(reasons)),
        snapshot_digest=snapshot.snapshot_digest,
        policy_digest=policy.policy_digest if policy else None,
        qualification_digest=qualification.qualification_digest if qualification else None,
        facts_digest=digest(facts.model_dump(mode="json")) if facts else None,
        opportunity=opportunity,
        qualified_completion_count=len(facts.completion_digests) if facts and not reasons else None,
        evaluated_at=now,
        expires_at=expires,
    )
