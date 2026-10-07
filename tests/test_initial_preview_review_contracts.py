"""Initial provenance is separate from candidate evidence and cannot accept client proofs."""

import pytest
from app.initial_planning.review_contracts import (
    InitialPreviewReviewIntent,
    InitialPreviewReviewPrepared,
)
from pydantic import ValidationError


def test_intent_is_only_exact_preview_digest() -> None:
    assert InitialPreviewReviewIntent(expected_preview_digest="a" * 64)
    with pytest.raises(ValidationError):
        InitialPreviewReviewIntent.model_validate(
            {"expected_preview_digest": "a" * 64, "amount_micros": 1}
        )


def test_prepared_result_never_approves_spending() -> None:
    result = InitialPreviewReviewPrepared(
        preview_id="a" * 32,
        preview_digest="b" * 64,
        review_id="c" * 32,
        review_digest="d" * 64,
        plan_digest="e" * 64,
    )
    assert result.status == "review_required" and result.spending_authority == "none"
