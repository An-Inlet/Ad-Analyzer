"""Explicit server mappings cannot be replaced by technical customer input."""

import json
from pathlib import Path

import pytest
from app.initial_planning.budget_mandate_configuration import (
    BudgetMandateConfigurationError,
    load_budget_mandate_policy,
)
from app.initial_planning.budget_mandate_contracts import (
    BudgetMandateCustomerIntentV1,
    BudgetMandateOperatingPolicyV1,
)
from pydantic import ValidationError


def operating_policy() -> BudgetMandateOperatingPolicyV1:
    return BudgetMandateOperatingPolicyV1.model_validate(
        dict(
            policy_id="test_explicit",
            revision=1,
            environment="contract_test",
            planning_reporting_profile_digest="a" * 64,
            currency="USD",
            currency_exponent=2,
            rules=[
                dict(
                    name=name,
                    aggressiveness_percent=10,
                    per_plan_cap_micros=50000000,
                    positive_change_cap_micros=5000000,
                    action_limit=2,
                    cooldown_seconds=60,
                    freshness_seconds=30,
                )
                for name in ("conservative", "balanced", "assertive")
            ],
        )
    )


def test_policy_loader_pinned_immutable_and_no_inferred_mapping(tmp_path: Path) -> None:
    policy = operating_policy()
    path = tmp_path / "policy.json"
    path.write_text(policy.model_dump_json())
    assert load_budget_mandate_policy(str(path), policy.digest()) == policy
    assert policy.rule("conservative").aggressiveness_percent == 10
    with pytest.raises(ValidationError):
        setattr(policy.rules[0], "action_limit", 3)
    assert load_budget_mandate_policy(None, None) is None
    for location, digest in ((str(path), None), (None, policy.digest()), (str(path), "b" * 64)):
        with pytest.raises(
            BudgetMandateConfigurationError, match="^budget_mandate_configuration_invalid$"
        ):
            load_budget_mandate_policy(location, digest)
    path.write_text('{"revision":1,"revision":2}')
    with pytest.raises(BudgetMandateConfigurationError):
        load_budget_mandate_policy(str(path), policy.digest())


def test_required_rules_quantum_and_customer_fields() -> None:
    value = operating_policy().model_dump(mode="json")
    for field in ("freshness_seconds", "cooldown_seconds", "action_limit", "per_plan_cap_micros"):
        document = json.loads(json.dumps(value))
        del document["rules"][0][field]
        with pytest.raises(ValidationError):
            BudgetMandateOperatingPolicyV1.model_validate(document)
    value["rules"][0]["per_plan_cap_micros"] = 1
    with pytest.raises(ValidationError):
        BudgetMandateOperatingPolicyV1.model_validate(value)
    customer = dict(
        selection=dict(calibration_id="a" * 32, observation_id="b" * 32, native_option_id="c" * 64),
        total_cap_micros=50000000,
        aggressiveness="balanced",
    )
    assert BudgetMandateCustomerIntentV1.model_validate(customer).total_cap_micros == 50000000
    for field in (
        "freshness_seconds",
        "action_limit",
        "cooldown_seconds",
        "aggressiveness_percent",
    ):
        with pytest.raises(ValidationError):
            BudgetMandateCustomerIntentV1.model_validate({**customer, field: 10})
