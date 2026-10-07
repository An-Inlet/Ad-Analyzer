"""Operational reporting contracts do not silently become strict mature evidence."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.initial_planning.contracts import CohortV1
from app.reported_feedback.contracts import (
    ConfigurationObservationAnchorV1,
    ReportedDayV1,
    ReportedWindowCapsuleV1,
    ReportedWindowPolicyV1,
    ReportWindowV1,
)
from app.reported_feedback.runtime import get_reported_feedback_runtime
from pydantic import ValidationError

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def cohort() -> CohortV1:
    return CohortV1(
        workspace_id=1,
        account_id=2,
        campaign_id=3,
        selected_event="offsite_conversion.fb_pixel_purchase",
        currency="USD",
        time_zone="UTC",
        query_version="meta.v26.0.campaign-day.v1",
    )


def anchor() -> ConfigurationObservationAnchorV1:
    return ConfigurationObservationAnchorV1(
        environment="contract_test",
        cohort=cohort(),
        integration_id=4,
        source_connection_id=5,
        source_generation=1,
        external_account_id="123",
        external_campaign_id="456",
        original_attempt_id="a" * 32,
        original_request_digest="b" * 64,
        original_plan_digest="c" * 64,
        reservation_id="d" * 32,
        ledger_id="e" * 32,
        latest_receipt_id="f" * 32,
        latest_receipt_digest="1" * 64,
        latest_receipt_sequence=1,
        dispatched_at=NOW,
        configuration_observed_at=NOW + timedelta(seconds=1),
        before_configuration_digest="2" * 64,
        after_configuration_digest="3" * 64,
        budget_field="daily_budget",
        before_budget_micros=100_000_000,
        after_budget_micros=110_000_000,
        goal_id="4" * 32,
        goal_revision=1,
        goal_digest="5" * 64,
        privacy_revision=0,
    )


def test_receipt_revision_does_not_create_another_original_opportunity() -> None:
    first = anchor()
    changed = ConfigurationObservationAnchorV1.model_validate(
        first.model_copy(
            update={
                "latest_receipt_id": "6" * 32,
                "latest_receipt_sequence": 2,
                "latest_receipt_digest": "7" * 64,
                "privacy_revision": 4,
            }
        ).model_dump()
    )
    assert first.digest() != changed.digest()
    assert first.opportunity_digest("8" * 32) == changed.opportunity_digest("8" * 32)
    assert first.delivery_time == "unavailable" and first.causal_lift == "unavailable"


def test_missing_dates_cannot_be_reconstructed_from_a_count_or_filled_zero() -> None:
    window = ReportWindowV1(starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 7))
    row = ReportedDayV1(
        day=window.starts_on, spend_micros=0, conversions=Decimal(0), conversion_value_micros=None
    )
    capsule = ReportedWindowCapsuleV1(
        id="1" * 32,
        job_id="2" * 32,
        acquisition_run_id="3" * 32,
        completion_id="4" * 32,
        completion_manifest_digest="5" * 64,
        environment="contract_test",
        cohort=cohort(),
        source_generation=1,
        captured_privacy_revision=0,
        policy_digest="6" * 64,
        window=window,
        acquisition_started_at=NOW,
        acquisition_completed_at=NOW,
        captured_at=NOW,
        expires_at=NOW + timedelta(days=1),
        days=(row,),
    )
    assert len(capsule.missing_dates()) == 6
    assert capsule.days[0].spend_micros == 0
    with pytest.raises(ValidationError):
        ReportedWindowCapsuleV1.model_validate(
            capsule.model_copy(update={"days": (row, row)}).model_dump()
        )
    with pytest.raises(ValidationError):
        ReportedWindowCapsuleV1.model_validate({**capsule.model_dump(), "reported_day_count": 7})


def test_configuration_has_no_numeric_defaults_or_installed_production_runtime() -> None:
    fields = ReportedWindowPolicyV1.model_fields
    assert all(field.is_required() for name, field in fields.items() if name != "schema_version")
    with pytest.raises(ValidationError):
        ReportedWindowPolicyV1.model_validate({"environment": "live"})
    assert get_reported_feedback_runtime() is None


def test_configuration_observation_cannot_claim_delivery_onset() -> None:
    with pytest.raises(ValidationError):
        ConfigurationObservationAnchorV1.model_validate(
            {**anchor().model_dump(), "delivery_time": "authoritative_interval"}
        )
