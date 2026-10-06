"""Required policy inputs are explicit fixtures, never production calibration."""

from decimal import Decimal

import pytest
from app.initial_planning.contracts import InitialPlanningConfiguration, RuleParametersV1
from app.initial_planning.runtime import get_initial_planning_configuration
from pydantic import ValidationError


def rule(**changes: object) -> RuleParametersV1:
    return RuleParametersV1.model_validate(
        {
            "name": "fixture",
            "increase_below_ratio": "0.8",
            "decrease_above_ratio": "1.2",
            "minimum_reported_conversions": "2",
            "minimum_spend_micros": 1,
            "budget_step_micros": 1000000,
            **changes,
        }
    )


def test_policy_unset_and_no_numeric_defaults() -> None:
    assert get_initial_planning_configuration() is None
    with pytest.raises(ValidationError):
        InitialPlanningConfiguration.model_validate({"environment": "live"})
    with pytest.raises(ValidationError):
        RuleParametersV1.model_validate({"name": "guess"})


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "0", "1"])
def test_nonfinite_or_unbounded_ratio_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        rule(increase_below_ratio=value)


def test_fixture_rule_does_not_imply_default_or_empirical_profile() -> None:
    item = rule()
    assert item.increase_below_ratio == Decimal("0.8")
    with pytest.raises(ValidationError):
        item.__setattr__("name", "changed")
    assert get_initial_planning_configuration() is None
