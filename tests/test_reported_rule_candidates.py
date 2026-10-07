"""Separate operational evidence cannot be parsed as qualified-learning v1."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from app.commerce.evidence import digest as source_digest
from app.directional_feedback.contracts import DecisionOpportunityV1
from app.optimization_candidates.contracts import CandidateEvidence, CandidateScope, SourceFence
from app.publication.optimization_contracts import MetaCurrentState
from app.reported_feedback.candidate_compiler import compile_reported_rule
from app.reported_feedback.candidate_contracts import (
    ReportedRuleCandidateV1,
    ReportedRuleEvidenceV1,
    ReportedRuleObservationV1,
    ReportedRulePolicyV1,
)
from app.reported_feedback.contracts import ReportedFeedbackPolicyV1
from app.reported_feedback.evaluator import bounded_delta, compare
from pydantic import ValidationError

from tests.test_execution_contracts import binding, policy
from tests.test_reported_feedback_evaluator import evidence
from tests.test_social_optimization_http import setup


def fixture() -> tuple[Any, ...]:
    request, capsules, now = evidence()
    comparison = compare(request, capsules, now)
    feedback = ReportedFeedbackPolicyV1(
        policy_id="a" * 32,
        family="b" * 32,
        revision=1,
        environment="contract_test",
        comparison_policy_digest=request.policy.digest(),
        original_change="increase",
        favorable_direction="decrease",
        unfavorable_direction="increase",
        minimum_distinct_original_attempts=1,
        neutral_band=Decimal("0.1"),
        weight=Decimal("1"),
        contribution_clamp=Decimal("1"),
        aggregate_clamp=Decimal("1"),
        maximum_preview_delta_micros=1_000_000,
        lifetime_seconds=120,
    )
    rule = ReportedRulePolicyV1(
        workspace_id=1,
        environment="contract_test",
        policy_id="c" * 32,
        revision=1,
        policy_family="d" * 32,
        feedback_policy=feedback,
        comparison_policy_digest=request.policy.digest(),
        allowed_operation="meta_budget_set_v1",
        maximum_candidate_age_seconds=120,
    )
    _, _, native, _ = setup("meta_ads", "budget", campaign=True)
    state = MetaCurrentState.model_validate(native.before.model_dump())
    mandate = policy().model_copy(
        update={
            "accounts": [state.scope],
            "starts_at": now - timedelta(hours=1),
            "ends_at": now + timedelta(hours=1),
            "allowed_purposes": ["existing_campaign_optimize"],
            "allowed_target_set_digest": state.budget_owner.target_set_digest(),
        }
    )
    state = state.model_copy(
        update={
            "observed_at": now,
            "money": state.money.model_copy(
                update={
                    "period_start": mandate.starts_at,
                    "period_end": mandate.ends_at,
                }
            ),
        }
    )
    scope = CandidateScope(
        account=state.scope,
        mandate=binding(mandate),
        goal_id=mandate.goal_id,
        goal_revision=1,
        goal_digest="a" * 64,
        target=state.target,
        budget_owner_key=state.budget_owner.key(state.scope),
        target_set_digest=state.budget_owner.target_set_digest(),
        source=SourceFence(
            workspace_privacy_revision=0,
            store_id="e" * 32,
            publication_id="f" * 32,
            generation=1,
            privacy_epoch=1,
            publication_revision=1,
            source_revision=1,
            manifest_digest="b" * 64,
        ),
    )
    value = ReportedRuleEvidenceV1(
        scope_digest=scope.digest(),
        environment="contract_test",
        source_reference=comparison.anchor.original_attempt_id,
        comparison_id=comparison.id,
        comparison_digest=comparison.digest(),
        acquisition_request_id=request.id,
        comparison_policy_digest=request.policy.digest(),
        rule_policy_digest=rule.digest(),
        opportunity=DecisionOpportunityV1(
            workspace_id=1,
            environment="contract_test",
            ledger_id=scope.mandate.ledger_id,
            original_attempt_id=comparison.anchor.original_attempt_id,
            original_request_digest=comparison.anchor.original_request_digest,
            native_account_digest=source_digest(
                [
                    "inlet.native-feedback-account.v1",
                    scope.account.account.platform,
                    scope.account.external_advertiser_id,
                ]
            ),
            budget_owner_key=scope.budget_owner_key,
        ),
        direction="decrease",
        signed_delta_micros=bounded_delta((comparison,), feedback),
        before=comparison.before,
        after=comparison.after,
        reported_completion_count=4,
        observed_at=now,
        expires_at=min(comparison.expires_at, now + timedelta(seconds=120)),
    )
    observation = ReportedRuleObservationV1(scope=scope, state=state, evidence=value)
    return observation, rule, mandate, now


def test_actual_report_arithmetic_separate_nominal_candidate_no_authority() -> None:
    observation, rule, mandate, now = fixture()
    result = compile_reported_rule(observation, rule, mandate, 0, 0, now)
    assert result.status == "suggested" and result.action is not None
    assert result.action.amount_micros == 49_500_000
    assert result.nominal_before_micros == 50_000_000
    assert result.evidence.reported_completion_count == 4
    assert result.evidence.causal_lift == result.evidence.delivery_time == "unavailable"
    assert result.spending_authority == "none" and not result.dispatch_ready
    assert ReportedRuleCandidateV1.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        CandidateEvidence.model_validate_json(result.evidence.model_dump_json())


@pytest.mark.parametrize("change", ["direction", "duplicate", "missing", "environment", "extra"])
def test_evidence_rejects_contradictions_without_mature_cast(change: str) -> None:
    observation, _, _, _ = fixture()
    data = observation.evidence.model_dump(mode="json")
    if change == "direction":
        data["direction"] = "increase"
    elif change == "duplicate":
        data["after"]["capsules"][0]["completion_id"] = data["before"]["capsules"][0][
            "completion_id"
        ]
    elif change == "missing":
        data["after"]["missing_dates"] = [data["after"]["window"]["starts_on"]]
    elif change == "environment":
        data["environment"] = "live"
    else:
        data["qualification"] = "qualified_learning"
    with pytest.raises(ValidationError):
        ReportedRuleEvidenceV1.model_validate_json(__import__("json").dumps(data))


@pytest.mark.parametrize("case", ["stale", "actions", "unrepresentable", "native_partial"])
def test_existing_limits_still_block_nominal_rule(case: str) -> None:
    observation, rule, mandate, now = fixture()
    actions = 0
    if case == "stale":
        now = observation.evidence.expires_at
    elif case == "actions":
        actions = mandate.action_limit
    elif case == "unrepresentable":
        observation = observation.model_copy(
            update={
                "evidence": observation.evidence.model_copy(
                    update={"signed_delta_micros": -500_001}
                ),
            }
        )
    else:
        observation = observation.model_copy(
            update={
                "state": observation.state.model_copy(update={"complete": False}),
            }
        )
    result = compile_reported_rule(observation, rule, mandate, 0, actions, now)
    assert result.status == "blocked" and result.action is None
    assert result.nominal_after_micros is None


def test_increase_clips_to_cumulative_limits_without_raising_total_cap() -> None:
    observation, rule, mandate, now = fixture()
    value = observation.evidence.model_copy(
        update={
            "direction": "increase",
            "signed_delta_micros": 500_000,
        }
    )
    observation = observation.model_copy(update={"evidence": value})
    before = mandate.model_dump_json()
    result = compile_reported_rule(
        observation, rule, mandate, mandate.positive_change_cap_micros - 100_000, 0, now
    )
    assert result.action is not None
    assert result.action.amount_micros == 50_100_000
    assert "adjustment_clipped_to_approved_limits" in result.reasons
    assert mandate.model_dump_json() == before
