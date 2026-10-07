"""Real bounded file loader and explicit fixture policy; no runtime overrides."""

import json
from pathlib import Path

import pytest
from app.planning_reporting.configuration import (
    MAXIMUM_PROFILE_BYTES,
    PlanningReportingConfigurationError,
    load_planning_reporting_profile,
)
from app.planning_reporting.contracts import NativeBudgetReadPolicyV1, PlanningReportingProfileV1
from pydantic import ValidationError

from tests.reported_feedback_fixture import feedback_policy, window_policy
from tests.test_initial_planning_api import explicit_policy


def profile() -> PlanningReportingProfileV1:
    return PlanningReportingProfileV1(
        profile_id="f" * 32,
        revision=1,
        environment="contract_test",
        initial=explicit_policy(),
        windows=window_policy(),
        feedback=feedback_policy(),
        native_read=NativeBudgetReadPolicyV1(
            http_timeout_seconds=5,
            total_deadline_seconds=20,
            maximum_pages=3,
            maximum_targets=100,
            observation_lifetime_seconds=30,
            credential_minimum_remaining_seconds=60,
        ),
    )


def test_load_actual_file_pin_and_no_reload_of_returned_profile(tmp_path: Path) -> None:
    original = profile()
    path = tmp_path / "profile.json"
    path.write_text(original.model_dump_json())
    loaded = load_planning_reporting_profile(str(path), original.digest())
    assert loaded == original
    path.write_text("invalid replacement")
    assert loaded is not None and loaded.digest() == original.digest()
    with pytest.raises(PlanningReportingConfigurationError):
        load_planning_reporting_profile(str(path), original.digest())
    with pytest.raises(ValidationError):
        loaded.__setattr__("revision", 2)


def test_absent_and_partial_configuration(tmp_path: Path) -> None:
    assert load_planning_reporting_profile(None, None) is None
    for path, digest in [(None, "a" * 64), ("", None), (str(tmp_path / "absent"), "a" * 64)]:
        with pytest.raises(PlanningReportingConfigurationError) as error:
            load_planning_reporting_profile(path, digest)
        assert str(error.value) == "planning_reporting_configuration_invalid"


@pytest.mark.parametrize("invalid", ["duplicate", "large", "digest", "unknown", "nonfinite"])
def test_reject_file_without_leaking_contents(tmp_path: Path, invalid: str) -> None:
    value = profile()
    payload = value.model_dump_json()
    if invalid == "duplicate":
        payload = '{"revision":1,"revision":2,"secret":"do-not-show"}'
    elif invalid == "large":
        payload = "x" * (MAXIMUM_PROFILE_BYTES + 1)
    elif invalid == "unknown":
        payload = payload[:-1] + ',"credential":"do-not-show"}'
    elif invalid == "nonfinite":
        body = value.model_dump(mode="json")
        body["initial"]["rules"][0]["increase_below_ratio"] = "NaN"
        payload = json.dumps(body)
    path = tmp_path / "profile.json"
    path.write_text(payload)
    with pytest.raises(PlanningReportingConfigurationError) as error:
        load_planning_reporting_profile(
            str(path), "0" * 64 if invalid == "digest" else value.digest()
        )
    assert str(error.value) == "planning_reporting_configuration_invalid"
    assert error.value.__cause__ is None


@pytest.mark.parametrize("field", ["initial", "windows", "feedback", "native_read"])
def test_required_sections_even_optional_feedback(field: str) -> None:
    body = profile().model_dump(mode="json")
    del body[field]
    with pytest.raises(ValidationError):
        PlanningReportingProfileV1.model_validate(body)


@pytest.mark.parametrize("change", ["environment", "event", "query", "feedback", "count"])
def test_cross_policy_bindings(change: str) -> None:
    body = profile().model_dump(mode="json")
    if change == "environment":
        body["environment"] = "live"
    elif change == "event":
        body["initial"]["supported_event"] = "other"
    elif change == "query":
        body["windows"]["query_version"] = "unrecognized"
    elif change == "feedback":
        body["feedback"]["comparison_policy_digest"] = "0" * 64
    else:
        body["feedback"]["minimum_distinct_original_attempts"] = 2
    with pytest.raises(ValidationError):
        PlanningReportingProfileV1.model_validate(body)


def test_every_native_numeric_parameter_required() -> None:
    body = profile().native_read.model_dump()
    for name in body:
        with pytest.raises(ValidationError):
            NativeBudgetReadPolicyV1.model_validate({k: v for k, v in body.items() if k != name})
    with pytest.raises(ValidationError):
        NativeBudgetReadPolicyV1.model_validate({**body, "credential_minimum_remaining_seconds": 1})
