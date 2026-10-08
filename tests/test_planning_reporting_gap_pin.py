"""Private mismatch pins reject missing/unsafe nested values before database resolution."""

from datetime import UTC, datetime, timedelta

import pytest
from app.planning_documents.context import AccountRef, ReportingWindow
from app.planning_documents.ports import EvidenceGap, ReportingGapPin
from pydantic import ValidationError


def pin() -> ReportingGapPin:
    end = datetime(2026, 10, 8, tzinfo=UTC)
    return ReportingGapPin(
        completion_id="a" * 32,
        campaign_id=1,
        native_campaign_id="5",
        document_digest="b" * 64,
        reporting_window=ReportingWindow(starts_at=end - timedelta(days=1), ends_at_exclusive=end),
    )


def gap(value: ReportingGapPin | None) -> EvidenceGap:
    return EvidenceGap(
        account=AccountRef(
            workspace_id=1,
            account_id=2,
            connection_id=3,
            platform="meta_ads",
            connection_version="meta:1:1",
        ),
        section="reported_metrics",
        reason="reporting_window_mismatch",
        explanation="Current reporting uses another window.",
        reporting_pin=value,
    )


def test_required_pin_and_unknown_gap_rejection() -> None:
    with pytest.raises(ValidationError):
        gap(None)
    original = gap(pin())
    with pytest.raises(ValidationError):
        EvidenceGap.model_validate(
            original.model_copy(update={"reason": "current_reporting_unavailable"})
        )
    with pytest.raises(ValidationError):
        EvidenceGap.model_validate(original.model_copy(update={"account": None}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("campaign_id", True),
        ("campaign_id", "1"),
        ("native_campaign_id", 5),
        ("completion_id", "invalid"),
        ("document_digest", "invalid"),
    ],
)
def test_unsafe_nested_pin_is_reparsed(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        gap(pin().model_copy(update={field: value}))
