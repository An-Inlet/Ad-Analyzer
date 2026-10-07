"""Exact initial Start rejects client-created evidence and generic Start substitution."""

import pytest
from app.initial_planning.start_contracts import StartInitialReportedRuleAutomationV1
from pydantic import ValidationError


def test_initial_start_requires_every_exact_binding() -> None:
    # A generic Start remains a different schema: missing basis/preview never defaults.
    with pytest.raises(ValidationError):
        StartInitialReportedRuleAutomationV1.model_validate(
            {
                "schema_version": "inlet.start-initial-reported-rule-automation.v1",
                "decision_basis": "initial_reported_efficiency_rule",
                "preview_id": "a" * 32,
                "expected_preview_digest": "b" * 64,
                "policy": {"policy_id": "c" * 32, "revision": 1},
                "expected_policy_digest": "d" * 64,
            }
        )
