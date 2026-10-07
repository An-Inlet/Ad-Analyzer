"""Nominal budget rule, explicitly independent of execution/exposure qualification."""

from datetime import datetime, timedelta

from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.optimization_contracts import MetaBudgetSetV1
from app.reported_feedback.candidate_contracts import (
    ReportedRuleCandidateV1,
    ReportedRuleObservationV1,
    ReportedRulePolicyV1,
)


def compile_reported_rule(
    observation: ReportedRuleObservationV1,
    policy: ReportedRulePolicyV1,
    mandate: ProviderMandatePolicy,
    positive_changes_used_micros: int,
    actions_used: int,
    now: datetime,
) -> ReportedRuleCandidateV1:
    observation = ReportedRuleObservationV1.model_validate_json(observation.model_dump_json())
    policy = ReportedRulePolicyV1.model_validate_json(policy.model_dump_json())
    mandate = ProviderMandatePolicy.model_validate_json(mandate.model_dump_json())
    scope, state, evidence = observation.scope, observation.state, observation.evidence
    reasons: list[str] = []
    expires = min(
        evidence.expires_at,
        evidence.observed_at + timedelta(seconds=policy.maximum_candidate_age_seconds),
        state.observed_at + timedelta(seconds=mandate.freshness_seconds),
        mandate.ends_at,
    )
    if (
        policy.workspace_id != scope.account.workspace_id
        or policy.environment != scope.mandate.environment
        or evidence.rule_policy_digest != policy.digest()
        or evidence.comparison_policy_digest != policy.comparison_policy_digest
        or mandate.digest() != scope.mandate.policy_digest
        or mandate.environment != policy.environment
        or scope.account not in mandate.accounts
        or mandate.allowed_target_set_digest != scope.target_set_digest
        or mandate.goal_id != scope.goal_id
        or mandate.goal_revision != scope.goal_revision
        or "existing_campaign_optimize" not in mandate.allowed_purposes
        or state.money.currency != mandate.currency
        or state.money.period_start != mandate.starts_at
        or state.money.period_end != mandate.ends_at
    ):
        reasons.append("current_owned_mandate_required")
    if (
        not mandate.starts_at <= now < expires
        or evidence.observed_at > now
        or state.observed_at > now
    ):
        reasons.append("fresh_observations_required")
    if not state.complete or state.unsupported_features or state.budget_owner.owner != state.target:
        reasons.append("complete_supported_campaign_owner_required")
    if actions_used >= mandate.action_limit or min(actions_used, positive_changes_used_micros) < 0:
        reasons.append("cumulative_limits_unavailable")
    before = state.daily_budget_micros or state.lifetime_budget_micros or 0
    if bool(state.daily_budget_micros) == bool(state.lifetime_budget_micros) or before <= 0:
        # No plausible numeric document for an ambiguous/absent native amount.
        raise ValueError("unambiguous positive native budget required")
    delta = evidence.signed_delta_micros
    if abs(delta) > policy.feedback_policy.maximum_preview_delta_micros:
        reasons.append("rule_limit_changed")
    unit = 10 ** (6 - state.money.currency_exponent)
    if before % unit or delta % unit:
        reasons.append("native_currency_quantum_required")
    action = None
    status = "blocked" if reasons else "no_change"
    after = None
    if not reasons and delta:
        if delta > 0:
            limited = min(
                delta,
                before * mandate.aggressiveness_percent // 100,
                max(0, mandate.positive_change_cap_micros - positive_changes_used_micros),
            )
            limited = limited // unit * unit
            if limited != delta:
                reasons.append("adjustment_clipped_to_approved_limits")
            delta = limited
        after = before + delta
        if delta == 0 or after <= 0:
            reasons.append("no_positive_precise_step")
            after = None
            status = "blocked"
        else:
            action = MetaBudgetSetV1(
                amount_micros=after,
                budget_field="daily_budget" if state.daily_budget_micros else "lifetime_budget",
            )
            status = "suggested"
            reasons.append("non_authorizing_reported_rule_suggestion")
    if not reasons:
        reasons.append("reported_rule_no_change")
    return ReportedRuleCandidateV1(
        scope=scope,
        policy_digest=policy.digest(),
        state_digest=state.digest(),
        evidence_digest=evidence.digest(),
        evidence=evidence,
        status=status,
        reasons=tuple(reasons),
        action=action,
        nominal_before_micros=before,
        nominal_after_micros=after,
        observed_at=now,
        expires_at=expires,
    )
