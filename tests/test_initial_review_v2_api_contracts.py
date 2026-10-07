"""UI contract freeze only; no route or configured runtime acceptance claim."""

from datetime import timedelta
from typing import Any

import pytest
from app.initial_planning.review_v2_api_contracts import (
    InitialPreviewExecutionOptionsV1,
    InitialPreviewExecutionOptionV1,
)
from pydantic import ValidationError

from tests.test_provider_publication_contracts import NOW


def option() -> InitialPreviewExecutionOptionV1:
    return InitialPreviewExecutionOptionV1(
        mandate_id="a" * 32,
        mandate_revision=1,
        policy_digest="b" * 64,
        account_label="Shop",
        target_label="Existing Sales Campaign",
        currency="USD",
        time_zone="UTC",
        starts_at=NOW,
        ends_at=NOW + timedelta(days=1),
        total_cap_micros=10_000_000,
        per_plan_cap_micros=5_000_000,
        positive_change_cap_micros=1_000_000,
    )


def test_available_is_not_qualification_and_nested_options_are_immutable() -> None:
    value = InitialPreviewExecutionOptionsV1(
        preview_id="c" * 32,
        preview_digest="d" * 64,
        options=(option(),),
        truncated=False,
        status="available",
        unavailable_reason=None,
    )
    assert value.financial_qualification == "not_checked" and value.spending_authority == "none"
    assert value == InitialPreviewExecutionOptionsV1.model_validate_json(value.model_dump_json())
    with pytest.raises(ValidationError):
        value.options[0].__setattr__("mandate_revision", 2)


@pytest.mark.parametrize(
    "reason",
    [
        "execution_runtime_unavailable",
        "separate_execution_consent_required",
        "matching_execution_mandate_unavailable",
    ],
)
def test_concrete_unavailable(reason: str) -> None:
    value = InitialPreviewExecutionOptionsV1.model_validate(
        dict(
            preview_id="c" * 32,
            preview_digest="d" * 64,
            options=[],
            truncated=False,
            status="unavailable",
            unavailable_reason=reason,
        )
    )
    with pytest.raises(ValidationError):
        InitialPreviewExecutionOptionsV1.model_validate(
            {**value.model_dump(), "options": [option().model_dump()]}
        )


@pytest.mark.parametrize("change", ["duplicate", "capacity", "authority", "empty_available"])
def test_invalid_availability_denies(change: str) -> None:
    body: dict[str, Any] = dict(
        preview_id="c" * 32,
        preview_digest="d" * 64,
        options=[option().model_dump()],
        truncated=False,
        status="available",
        unavailable_reason=None,
    )
    if change == "duplicate":
        body["options"] *= 2
    if change == "capacity":
        body["options"] *= 51
    if change == "authority":
        body["spending_authority"] = "approved"
    if change == "empty_available":
        body["options"] = []
    with pytest.raises(ValidationError):
        InitialPreviewExecutionOptionsV1.model_validate(body)
