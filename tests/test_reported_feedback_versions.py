"""Pure version/precision coverage; actual producer journey is a separate acceptance gate."""

import pytest
from app.reported_feedback.service import require_native_quantum
from fastapi import HTTPException

from tests.test_initial_preview_v2 import document


@pytest.mark.parametrize("amount", [6000001, 6009999, 5999999])
def test_adjusted_amount_cannot_ignore_observed_currency_precision(amount: int) -> None:
    baseline = document()
    original = baseline.model_dump_json()
    with pytest.raises(HTTPException, match="native_amount_unrepresentable"):
        require_native_quantum(baseline, amount)
    assert baseline.model_dump_json() == original


@pytest.mark.parametrize("amount", [6000000, 6010000, 5990000])
def test_exact_currency_amount_retains_unqualified_native_commitment(amount: int) -> None:
    baseline = document()
    before = baseline.digest()
    require_native_quantum(baseline, amount)
    assert baseline.digest() == before
    assert not baseline.spending_authorized and not baseline.review_available
