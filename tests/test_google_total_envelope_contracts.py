from datetime import UTC, datetime, timedelta

import pytest
from app.publication.google_total_envelope_contracts import GoogleTotalEnvelopeViewV1
from pydantic import ValidationError


def document():
    now = datetime(2026, 10, 7, tzinfo=UTC)
    return dict(
        run_id="a" * 32,
        environment="contract_test",
        status="matching_configuration",
        currency="USD",
        time_zone="America/New_York",
        campaign_starts_at=now,
        campaign_ends_at=now + timedelta(days=7),
        original_total_micros=100000000,
        observed_total_micros=100000000,
        reservation_micros=150000000,
        reservation_state="held",
        original_binding_digest="b" * 64,
        inventory_digest="c" * 64,
        observation_started_at=now,
        observed_at=now,
        expires_at=now + timedelta(minutes=1),
        reasons=["financial_basis_unqualified", "historical_liabilities_unverified"],
    )


def test_observation_preserves_distinct_native_and_reserved_amounts():
    result = GoogleTotalEnvelopeViewV1.model_validate(document())
    assert result.original_total_micros != result.reservation_micros
    assert result.financial_upper_micros is None
    assert result.spending_authority == "none"


@pytest.mark.parametrize(
    "change",
    [
        {"financial_upper_micros": 100},
        {"spending_authority": "approved"},
        {"observed_total_micros": None},
        {"observed_total_micros": 1},
        {"reasons": ["financial_basis_unqualified", "financial_basis_unqualified"]},
        {"status": "configuration_drift"},
    ],
)
def test_inconsistent_or_authorizing_projection_rejected(change):
    with pytest.raises(ValidationError):
        GoogleTotalEnvelopeViewV1.model_validate(document() | change)
