"""Versioned native-read commitment without changing qualified v1 serialization."""

from datetime import timedelta

import pytest
from app.initial_planning.contracts import InitialPreviewV1
from app.initial_planning.preview_v2 import InitialPreviewV2, parse_initial_preview
from pydantic import ValidationError

from tests.test_native_budget_contracts import observation


def document() -> InitialPreviewV2:
    native = observation()
    return InitialPreviewV2.model_validate(
        {
            "id": "e" * 32,
            "calibration_id": "f" * 32,
            "observation_id": "0" * 32,
            "objective": {
                "cohort": native.request.cohort.model_dump(),
                "goal_id": native.request.goal_id,
                "goal_revision": native.request.goal_revision,
                "maximum_reported_cpa_micros": 10000000,
            },
            "profile_digest": native.request.profile_digest,
            "environment": "contract_test",
            "policy_digest": "1" * 64,
            "evidence_digest": "2" * 64,
            "recommendation_status": "proposed",
            "direction": "increase",
            "before_budget_micros": 5000000,
            "after_budget_micros": 6000000,
            "native_observation": native.model_dump(),
            "reasons": ["explicit_fixture_rule"],
            "created_at": native.observed_at,
            "expires_at": native.expires_at,
        }
    )


def test_versions_preserve_v1_bytes_and_never_fabricate_qualified_digest() -> None:
    value = document()
    assert parse_initial_preview(value.model_dump()) == value
    assert "native_state_digest" not in value.model_dump()
    assert not value.review_available and not value.spending_authorized
    legacy = value.model_dump(
        exclude={"profile_digest", "environment", "native_observation", "handoff_reason"}
    )
    legacy["schema_version"] = "inlet.initial-efficiency-preview.v1"
    legacy["native_state_digest"] = "3" * 64
    v1 = InitialPreviewV1.model_validate(legacy)
    parsed = parse_initial_preview(v1.model_dump())
    assert isinstance(parsed, InitialPreviewV1)
    assert parsed.model_dump_json() == v1.model_dump_json() and parsed.digest() == v1.digest()
    with pytest.raises(ValidationError):
        InitialPreviewV1.model_validate(value.model_dump())


@pytest.mark.parametrize(
    "field", ["profile", "goal", "amount", "quantum", "expiry", "environment", "absent"]
)
def test_native_commitment_bindings(field: str) -> None:
    value = document().model_dump()
    if field == "profile":
        value["profile_digest"] = "9" * 64
    elif field == "goal":
        value["objective"]["goal_revision"] = 2
    elif field == "amount":
        value["before_budget_micros"] = 4000000
    elif field == "quantum":
        value["after_budget_micros"] = 6000001
    elif field == "expiry":
        value["expires_at"] += timedelta(seconds=1)
    elif field == "environment":
        value["environment"] = "live"
    else:
        value["native_observation"] = None
    with pytest.raises(ValidationError):
        parse_initial_preview(value)
