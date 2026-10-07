"""Exact v2 persisted intent/row semantics, no fabricated qualified target choice."""

from datetime import timedelta
from typing import Any

import pytest
from app.initial_planning.native_budget_contracts import native_budget_choice_digest
from app.initial_planning.preview_binding import bind_preview_row, preview_mandate_reference
from app.initial_planning.preview_v2 import PreviewIntentV2

from tests.test_initial_preview_v2 import document


def bound_row() -> dict[str, Any]:
    value = document()
    assert value.native_observation is not None
    intent = PreviewIntentV2(
        objective=value.objective,
        calibration_id=value.calibration_id,
        observation_id=value.observation_id,
        environment=value.environment,
        profile_digest=value.profile_digest,
        goal_digest=value.native_observation.request.goal_digest,
        native_option_id=native_budget_choice_digest(value.native_observation),
        mandate_id="9" * 32,
        mandate_revision=1,
    )
    return dict(
        document=value.model_dump(mode="json"),
        document_digest=value.digest(),
        intent=intent.model_dump(mode="json"),
        id=value.id,
        calibration_id=value.calibration_id,
        observation_id=value.observation_id,
        workspace_id=1,
        account_id=2,
        campaign_id=5,
        goal_digest=intent.goal_digest,
        source_generation=1,
        native_state_digest=None,
        mandate_digest="a" * 64,
        created_at=value.created_at,
        expires_at=value.expires_at,
    )


def test_bound_v2_intent_mandate_reference_and_unqualified_state_null() -> None:
    row = bound_row()
    value = bind_preview_row(row)
    assert value == document()
    assert preview_mandate_reference(row, value) == ("9" * 32, 1)
    assert "choice" not in row["intent"]
    assert row["native_state_digest"] is None


@pytest.mark.parametrize(
    "field",
    [
        "account_id",
        "goal_digest",
        "native_state_digest",
        "source_generation",
        "document_digest",
        "intent",
    ],
)
def test_reject_wrong_row_binding(field: str) -> None:
    row = bound_row()
    row[field] = 99 if field in {"account_id", "source_generation"} else "0" * 64
    with pytest.raises(ValueError):
        bind_preview_row(row)


def test_choice_stable_across_rereads_but_full_observation_commits_time() -> None:
    value = document().native_observation
    assert value is not None
    new = type(value).model_validate(
        {
            **value.model_dump(),
            "observation_started_at": value.observation_started_at + timedelta(seconds=1),
            "observed_at": value.observed_at + timedelta(seconds=1),
            "expires_at": value.expires_at + timedelta(seconds=1),
        }
    )
    assert new.digest() != value.digest()
    assert native_budget_choice_digest(new) == native_budget_choice_digest(value)
    changed = type(value).model_validate({**new.model_dump(), "amount_micros": 6000000})
    assert native_budget_choice_digest(changed) != native_budget_choice_digest(value)
