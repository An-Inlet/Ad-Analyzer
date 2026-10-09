"""The sole test-fixture reconciliation opt-in is explicit, aware and one-shot."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from tests.reported_original_fixture import ExpectedUnknownReadback


def test_unknown_readback_expectation_requires_explicit_one_shot_time() -> None:
    value = ExpectedUnknownReadback()
    with pytest.raises(AssertionError):
        _ = value.observed_at
    stamp = datetime(2026, 10, 9, tzinfo=UTC)
    value.arm(stamp)
    assert value.observed_at == stamp
    with pytest.raises(AssertionError):
        value.arm(stamp + timedelta(seconds=1))
    assert value.observed_at == stamp


@pytest.mark.parametrize("zone", [None, timezone(timedelta(hours=1))])
def test_unknown_readback_expectation_rejects_non_utc_time(zone: timezone | None) -> None:
    value = ExpectedUnknownReadback()
    with pytest.raises(AssertionError):
        value.arm(datetime(2026, 10, 9, tzinfo=zone))
    with pytest.raises(AssertionError):
        _ = value.observed_at
