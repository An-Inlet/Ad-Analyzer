"""The browser submits selections and its explicit objective, never source proof."""

import pytest
from app.initial_planning.api_contracts import CalibrationIntent, CaptureIntent, PreviewIntent
from pydantic import ValidationError


@pytest.mark.parametrize("proof", ["cohort", "document", "spending_authorized", "environment"])
def test_customer_cannot_submit_report_proof(proof: str) -> None:
    with pytest.raises(ValidationError):
        CaptureIntent.model_validate({"account_id": 1, "campaign_id": 2, proof: {}})
    with pytest.raises(ValidationError):
        CalibrationIntent.model_validate(
            {
                "observation_id": "a" * 32,
                "goal_id": "b" * 32,
                "goal_revision": 1,
                "maximum_reported_cpa_micros": 1000000,
                proof: {},
            }
        )


@pytest.mark.parametrize("amount", [0, -1, True, 1.5, "100"])
def test_customer_objective_requires_explicit_positive_integer_micros(amount: object) -> None:
    with pytest.raises(ValidationError):
        CalibrationIntent.model_validate(
            {
                "observation_id": "a" * 32,
                "goal_id": "b" * 32,
                "goal_revision": 1,
                "maximum_reported_cpa_micros": amount,
            }
        )


def test_native_selection_cannot_be_partial() -> None:
    with pytest.raises(ValidationError):
        PreviewIntent(calibration_id="a" * 32, observation_id="b" * 32, mandate_id="c" * 32)
    value = PreviewIntent(calibration_id="a" * 32, observation_id="b" * 32)
    assert value.choice is None
