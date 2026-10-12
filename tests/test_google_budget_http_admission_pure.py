"""Pinned pre-admission v22 canonical bytes and exact request version separation."""

import hashlib

import pytest
from app.planning_documents.google_budget_events import BudgetReadIntent
from app.planning_documents.google_budget_http_events import BudgetHTTPIntent
from app.planning_documents.storage import canonical
from pydantic import ValidationError

from tests.google_budget_event_fixture import history


def test_pre_admission_v22_bytes_and_profile_separation() -> None:
    # SHA-256 of original canonical events from b273e3e4's frozen renderer artifacts.
    expected = [
        "1889b33288af4c64046fa202588ae4e6f7a00153f18aa2c969c3bc30210970e6",
        "88c40b9bcecc032f117039d2f52d1857ef1d55f07fd7000be0195254a9da2a86",
    ]
    events = history()
    assert [hashlib.sha256(canonical(e).encode()).hexdigest() for e in events] == expected
    body = dict(
        **events[0].binding().model_dump(),
        expected_event_sequence=0,
        request_key="separate-http-profile",
    )
    legacy, http = BudgetReadIntent(**body), BudgetHTTPIntent(**body)
    assert legacy.profile_digest != http.profile_digest and legacy.digest() != http.digest()
    with pytest.raises(ValidationError):
        BudgetReadIntent.model_validate(http.model_dump())
    with pytest.raises(ValidationError):
        BudgetHTTPIntent.model_validate(legacy.model_dump())
