from decimal import Decimal

import pytest
from app.optimization_candidates.customer_contracts import CandidateReadStatus
from app.reported_feedback.automatic_contracts import (
    REPORTED_RULE_EPOCH_FAMILY,
    REPORTED_RULE_FAMILY,
    ReportedRuleAutomaticPolicyV1,
    StartReportedRuleAutomationV1,
)
from app.reported_feedback.candidate_compiler import compile_reported_rule
from app.reported_feedback.customer_contracts import decimal_text, rule_parameters
from app.session_automation.contracts import StartSessionAutomation
from pydantic import ValidationError

from tests.test_reported_rule_candidates import fixture


@pytest.mark.parametrize(
    "raw,expected", [("1E+7", "10000000"), ("0.0000100", "0.00001"), ("-0", "0")]
)
def test_exact_decimal_display_without_exponents(raw: str, expected: str) -> None:
    assert decimal_text(Decimal(raw)) == expected


def test_reported_start_is_distinct_and_policy_family_cannot_reset() -> None:
    observation, rule, mandate, now = fixture()
    policy = ReportedRuleAutomaticPolicyV1(
        decision_basis="operational_reported_efficiency_rule",
        workspace_id=rule.workspace_id,
        environment=rule.environment,
        policy_family=REPORTED_RULE_FAMILY,
        policy_id="a" * 32,
        revision=1,
        candidate_policy={"policy_id": rule.policy_id, "revision": rule.revision},
        candidate_policy_digest=rule.digest(),
        allowed_operations=("meta_budget_set_v1",),
        semantic_producer_families=(REPORTED_RULE_EPOCH_FAMILY,),
        lifetime_seconds=60,
        cadence_seconds=30,
    )
    intent = StartReportedRuleAutomationV1(
        schema_version="inlet.start-reported-rule-automation.v1",
        decision_basis="operational_reported_efficiency_rule",
        mandate=observation.scope.mandate,
        policy={"policy_id": policy.policy_id, "revision": policy.revision},
        expected_policy_digest=policy.digest(),
    )
    with pytest.raises(ValidationError):
        StartSessionAutomation.model_validate_json(intent.model_dump_json())
    with pytest.raises(ValidationError):
        ReportedRuleAutomaticPolicyV1.model_validate(
            {**policy.model_dump(), "policy_family": "b" * 32}
        )
    params = rule_parameters(rule)
    assert (
        params.maximum_nominal_adjustment_micros
        == rule.feedback_policy.maximum_preview_delta_micros
    )
    assert params.weight == "1"
    decision = compile_reported_rule(observation, rule, mandate, 0, 0, now)
    with pytest.raises(ValidationError, match="basis details"):
        CandidateReadStatus(
            job_id="a" * 32,
            state="completed",
            result_id="b" * 32,
            decision=decision,
            decision_digest=decision.digest(),
        )
