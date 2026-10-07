import pytest
from app.optimization_candidates.customer_contracts import (
    CandidateCapabilities,
    CandidateReadIntent,
    CandidateReadStatus,
)
from pydantic import ValidationError


def test_candidate_intent_cannot_supply_evidence() -> None:
    value = dict(
        mandate_id="b" * 32, mandate_revision=1, policy=dict(policy_id="a" * 32, revision=1)
    )
    assert CandidateReadIntent.model_validate(value).mandate_revision == 1
    for field in ("scope", "source", "evidence", "actor_id", "session_digest", "amount_micros"):
        with pytest.raises(ValidationError):
            CandidateReadIntent.model_validate({**value, field: "caller"})


def test_candidate_capability_cannot_advertise_automatic_authority() -> None:
    value = dict(configured=True, policies=[], mandates=[], truncated=False)
    parsed = CandidateCapabilities.model_validate(value)
    assert parsed.spending_authority == "none"
    assert not parsed.automatic_available
    with pytest.raises(ValidationError):
        CandidateCapabilities.model_validate({**value, "automatic_available": True})


def test_pending_candidate_digest_is_explicitly_absent() -> None:
    value = dict(
        job_id="a" * 32, state="pending", result_id=None, decision=None, decision_digest=None
    )
    assert CandidateReadStatus.model_validate(value).decision_digest is None
    with pytest.raises(ValidationError):
        CandidateReadStatus.model_validate({**value, "decision_digest": "b" * 64})
