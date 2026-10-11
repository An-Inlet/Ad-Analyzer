"""Declared optional Meta schedule is not an optional catalog observation clock."""

from datetime import datetime
from typing import Any

import pytest
from app.planning_catalog.contracts import MetaSettingsV1
from app.planning_documents.google_budget_input_bindings import _times
from app.planning_documents.google_budget_owner_contracts import _originals


def settings() -> MetaSettingsV1:
    return MetaSettingsV1(
        configured_status="PAUSED",
        effective_status="PAUSED",
        daily_budget_native=None,
        lifetime_budget_native=None,
        spend_cap_native=None,
        starts_at=None,
        ends_at=None,
        budget_schedule_enabled=None,
        budget_sharing_enabled=None,
        budget_rebalance_enabled=None,
    )


@pytest.mark.parametrize("shape", ["model", "raw", "copy"])
def test_exact_optional_native_schedule(shape: str) -> None:
    value: Any = settings()
    if shape == "raw":
        value = value.model_dump(mode="python")
    elif shape == "copy":
        value = value.model_copy(update={"starts_at": None, "ends_at": None})
    _originals(value)
    _times(value)
    MetaSettingsV1.model_validate(value)


@pytest.mark.parametrize("field", ["starts_at", "ends_at"])
@pytest.mark.parametrize(
    "value", [1, "2026-10-06T00:00:00", datetime(2026, 10, 6), b"2026-10-06T00:00:00Z"]
)
def test_nonnull_schedule_remains_strict(field: str, value: Any) -> None:
    copied = settings().model_copy(update={field: value})
    for check in (_originals, _times):
        with pytest.raises(ValueError):
            check(copied)


@pytest.mark.parametrize("case", ["report", "spoof", "extra", "missing"])
def test_required_envelopes_cannot_claim_schedule_exception(case: str) -> None:
    if case == "report":
        raw: Any = {"reporting_starts_at": None}
    elif case == "spoof":
        raw = {"platform": "meta_ads", "starts_at": None, "ends_at_exclusive": None}
    else:
        raw = settings().model_dump(mode="python")
        if case == "extra":
            raw["reporting_starts_at"] = None
        else:
            raw.pop("configured_status")
    for check in (_originals, _times):
        with pytest.raises(ValueError):
            check(raw)


def test_aware_optional_schedule_retains_exact_instants() -> None:
    value = settings().model_copy(
        update={"starts_at": "2026-10-06T03:30:00+03:30", "ends_at": "2026-10-06T04:30:00+03:30"}
    )
    _originals(value)
    _times(value)
    checked = MetaSettingsV1.model_validate(value)
    assert checked.starts_at is not None and checked.ends_at is not None
    assert (checked.ends_at - checked.starts_at).total_seconds() == 3600
