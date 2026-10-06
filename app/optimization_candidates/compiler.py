"""Deterministic bounded suggestions, never exposure or dispatch qualification."""

from datetime import datetime, timedelta

from app.optimization_candidates.contracts import (
    CandidateDecision,
    CandidateObservation,
    CandidatePolicy,
)
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.optimization_contracts import (
    GoogleBudgetSetV1,
    GoogleCurrentState,
    MetaBudgetSetV1,
    MetaCurrentState,
    OptimizationAction,
    TikTokBudgetSetV1,
)


def compile_candidate(
    observation: CandidateObservation,
    policy: CandidatePolicy,
    mandate: ProviderMandatePolicy,
    positive_changes_used_micros: int,
    actions_used: int,
    now: datetime,
) -> CandidateDecision:
    scope, state, evidence = observation.scope, observation.state, observation.evidence
    reasons: list[str] = []
    expires = min(
        evidence.expires_at,
        state.observed_at + timedelta(seconds=mandate.freshness_seconds),
        mandate.ends_at,
    )
    if (
        policy.workspace_id != scope.account.workspace_id
        or policy.environment != scope.mandate.environment
        or mandate.digest() != scope.mandate.policy_digest
        or mandate.environment != policy.environment
        or scope.account not in mandate.accounts
        or mandate.goal_id != scope.goal_id
        or mandate.goal_revision != scope.goal_revision
        or mandate.allowed_target_set_digest != scope.target_set_digest
        or "existing_campaign_optimize" not in mandate.allowed_purposes
        or state.money.currency != mandate.currency
        or state.money.period_start != mandate.starts_at
        or state.money.period_end != mandate.ends_at
    ):
        reasons.append("current_owned_mandate_required")
    if (
        not mandate.starts_at <= now < expires
        or not evidence.observed_at <= now
        or state.observed_at > now
    ):
        reasons.append("fresh_observations_required")
    if not state.complete or state.unsupported_features:
        reasons.append("complete_supported_state_required")
    if policy.budget_step_micros is None or policy.minimum_observations is None:
        reasons.append("numeric_policy_unconfigured")
    if evidence.qualification == "unqualified":
        reasons.append("measured_learning_unqualified")
    if policy.minimum_observations is not None and (
        evidence.observation_count is None
        or evidence.observation_count < policy.minimum_observations
    ):
        reasons.append("insufficient_observations")
    if actions_used >= mandate.action_limit or min(actions_used, positive_changes_used_micros) < 0:
        reasons.append("cumulative_limits_unavailable")
    action: OptimizationAction | None = None
    status = "blocked" if reasons else "no_change"
    if not reasons and evidence.direction != "none":
        assert policy.budget_step_micros is not None
        previous = (
            state.budget_amount_micros
            if isinstance(state, GoogleCurrentState)
            else (state.daily_budget_micros or state.lifetime_budget_micros or 0)
            if isinstance(state, MetaCurrentState)
            else (state.budget_micros or 0)
        )
        step = policy.budget_step_micros
        if evidence.direction == "increase":
            step = min(
                step,
                previous * mandate.aggressiveness_percent // 100,
                max(0, mandate.positive_change_cap_micros - positive_changes_used_micros),
            )
        unit = 10 ** (6 - state.money.currency_exponent)
        step = step // unit * unit
        amount = previous + step if evidence.direction == "increase" else previous - step
        if step <= 0 or amount <= 0:
            reasons.append("no_positive_precise_step")
        elif isinstance(state, GoogleCurrentState):
            action = GoogleBudgetSetV1(amount_micros=amount)
        elif isinstance(state, MetaCurrentState):
            if bool(state.daily_budget_micros) == bool(state.lifetime_budget_micros):
                reasons.append("native_budget_ambiguous")
            else:
                action = MetaBudgetSetV1(
                    amount_micros=amount,
                    budget_field="daily_budget" if state.daily_budget_micros else "lifetime_budget",
                )
        elif state.budget_mode in {"BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL"}:
            action = TikTokBudgetSetV1(amount_micros=amount, budget_mode=state.budget_mode)
        else:
            reasons.append("native_budget_unsupported")
        if action is not None:
            status = "suggested"
            reasons.append("non_authorizing_budget_suggestion")
    if not reasons:
        reasons.append("no_qualified_directional_change")
    return CandidateDecision(
        scope=scope,
        policy_digest=policy.digest(),
        state_digest=state.digest(),
        evidence_digest=evidence.digest(),
        evidence=evidence,
        status=status,
        reasons=reasons,
        action=action,
        observed_at=now,
        expires_at=expires,
    )
