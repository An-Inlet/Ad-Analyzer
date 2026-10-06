from datetime import timedelta

import pytest
from app.publication.optimization_execution_contracts import (
    OptimizationExecutionReview,
    OptimizationPlan,
    OptimizationQualification,
    get_optimization_runtime,
    positive_delta,
)
from pydantic import ValidationError

from tests.test_social_optimization_http import setup


def plan(provider: str = "meta_ads", action: str = "budget") -> OptimizationPlan:
    req = setup(provider, action)[2]
    now = req.before.observed_at
    return OptimizationPlan(
        intent=req.intent,
        before=req.before,
        exposure=req.exposure,
        qualification=OptimizationQualification(
            environment=req.intent.mandate.environment,
            scope=req.intent.scope,
            target=req.intent.target,
            money=req.before.money,
            qualification_id=req.intent.qualification_id,
            qualification_revision=req.intent.qualification_revision,
            profile="controlled_contract_profile",
            allowed_operations=[req.intent.action.kind],
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            evidence_digest="f" * 64,
            unresolved=[],
        ),
        positive_change_micros=positive_delta(req.intent, req.before),
    )


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("action", ["budget", "pause"])
def test_exact_compilation_preserves_original_transport_request(provider: str, action: str) -> None:
    value = plan(provider, action)
    old = setup(provider, action)[2]
    request = value.request(old.action_id, old.attempt_id, old.fence, old.dispatched_at)
    assert request == old and request.digest() == old.digest()
    assert value.positive_change_micros == 0
    assert OptimizationExecutionReview(plan=value).purpose == "existing_campaign_optimize"


@pytest.mark.parametrize("change", ["delta", "qualification", "scope", "operation", "state"])
def test_review_cannot_substitute_plan_bindings(change: str) -> None:
    raw = plan().model_dump(mode="json")
    if change == "delta":
        raw["positive_change_micros"] = 100
    elif change == "qualification":
        raw["qualification"]["qualification_id"] = "0" * 32
    elif change == "scope":
        raw["qualification"]["scope"]["external_advertiser_id"] = "999"
    elif change == "operation":
        raw["qualification"]["allowed_operations"] = ["meta_status_set_v1"]
    else:
        raw["before"]["daily_budget_micros"] = 100
    with pytest.raises(ValidationError):
        OptimizationPlan.model_validate(raw)


def test_runtime_remains_disabled() -> None:
    assert get_optimization_runtime() is None
