"""Malformed customer assertions fail request validation, before event construction."""

from datetime import UTC, datetime, timedelta

import pytest
from app.planning_documents.requests import AssertionIntent
from pydantic import ValidationError


@pytest.mark.parametrize(
    "change",
    [
        {"reported_applied_at": None},
        {"reported_applied_at": datetime.now(UTC) + timedelta(days=1)},
        {"assertion": "retracted", "supersedes_event_id": None, "reported_applied_at": None},
        {"assertion": "retracted", "supersedes_event_id": "b" * 32},
    ],
)
def test_invalid_assertion_request_rejected(change: dict[str, object]) -> None:
    values = dict(
        expected_version=1,
        expected_event_sequence=0,
        document_digest="a" * 64,
        action_key="review",
        action_digest="b" * 64,
        assertion="customer_reports_applied",
        reported_applied_at=datetime.now(UTC),
        statement="Customer report",
        supersedes_event_id=None,
        request_key="assertion-request-01",
    )
    AssertionIntent.model_validate(values)
    with pytest.raises(ValidationError):
        AssertionIntent.model_validate({**values, **change})
