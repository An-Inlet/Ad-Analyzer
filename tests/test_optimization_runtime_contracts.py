from typing import Any

import pytest
from app.production_runtime.optimization_contracts import (
    OptimizationEvidenceDescriptor,
    OptimizationExecutionManifestV1,
    RegisteredOptimizationEvidenceSource,
    admit_optimization_source,
)
from app.production_runtime.optimization_policy_contracts import (
    OptimizationCustomerIntentV1,
    OptimizationOperatingPolicyV1,
    PrepareOptimizationMandateV1,
)
from pydantic import ValidationError


def manifest() -> OptimizationExecutionManifestV1:
    return OptimizationExecutionManifestV1(
        manifest_id="explicit_fixture",
        revision=1,
        environment="contract_test",
        providers=("google_ads", "meta_ads"),
        evidence_source_id="explicit_fixture",
        evidence_profile_digest="a" * 64,
        operating_policy_digest="b" * 64,
        live_execution_enabled=False,
        replacement_enabled=True,
        settlement_enabled=False,
        credential_minimum_remaining_seconds=300,
        context_lifetime_seconds=60,
    )


def test_no_unsupported_provider_or_promoted_source_is_admitted() -> None:
    def forbidden(*args: Any) -> Any:
        raise AssertionError("pure admission must not build evidence")

    m = manifest()
    source = RegisteredOptimizationEvidenceSource(
        OptimizationEvidenceDescriptor(
            source_id=m.evidence_source_id,
            profile_digest=m.evidence_profile_digest,
            providers=m.providers,
            environment="contract_test",
            kind="contract_scenario",
        ),
        forbidden,
    )
    assert admit_optimization_source(m, source, "meta_ads") is source
    assert admit_optimization_source(m, source, "tiktok_ads") is None
    assert admit_optimization_source(m, None, "google_ads") is None
    live = OptimizationExecutionManifestV1.model_validate(
        {**m.model_dump(), "environment": "live", "live_execution_enabled": True}
    )
    assert admit_optimization_source(live, source, "google_ads") is None
    for extra in (
        {"providers": ["meta_ads", "google_ads"]},
        {"providers": ["tiktok_ads"]},
        {"live_execution_enabled": True},
        {"context_lifetime_seconds": 301},
    ):
        with pytest.raises(ValidationError):
            OptimizationExecutionManifestV1.model_validate({**m.model_dump(), **extra})


def policy() -> OptimizationOperatingPolicyV1:
    return OptimizationOperatingPolicyV1.model_validate(
        {
            "policy_id": "explicit_fixture",
            "revision": 1,
            "environment": "contract_test",
            "evidence_profile_digest": "a" * 64,
            "currency": "USD",
            "currency_exponent": 2,
            "rules": [
                {
                    "name": name,
                    "aggressiveness_percent": percent,
                    "per_plan_cap_micros": 10000,
                    "positive_change_cap_micros": 10000,
                    "action_limit": 1,
                    "cooldown_seconds": 0,
                    "freshness_seconds": 30,
                }
                for name, percent in (("conservative", 5), ("balanced", 10), ("assertive", 20))
            ],
        }
    )


def test_explicit_operating_numbers_have_no_missing_defaults_or_legacy_profile_alias() -> None:
    p = policy()
    assert p.rule("balanced").aggressiveness_percent == 10
    for field in (
        "per_plan_cap_micros",
        "positive_change_cap_micros",
        "freshness_seconds",
        "cooldown_seconds",
        "action_limit",
    ):
        raw = p.model_dump()
        del raw["rules"][0][field]
        with pytest.raises(ValidationError):
            OptimizationOperatingPolicyV1.model_validate(raw)
    with pytest.raises(ValidationError):
        OptimizationOperatingPolicyV1.model_validate(
            {**p.model_dump(), "planning_reporting_profile_digest": "a" * 64}
        )
    raw = p.model_dump()
    raw["rules"][0]["action_limit"] = 1001
    with pytest.raises(ValidationError):
        OptimizationOperatingPolicyV1.model_validate(raw)


def test_customer_can_only_confirm_meaningful_intent_and_complete_revision_identity() -> None:
    raw = {
        "selection": {
            "goal_id": "a" * 32,
            "goal_revision": 1,
            "account_id": 1,
            "option_id": "b" * 64,
        },
        "total_cap_micros": 10000,
        "aggressiveness": "balanced",
    }
    intent = OptimizationCustomerIntentV1.model_validate(raw)
    assert PrepareOptimizationMandateV1(intent=intent).expected_revision is None
    with pytest.raises(ValidationError):
        OptimizationCustomerIntentV1.model_validate({**raw, "freshness_seconds": 1})
    with pytest.raises(ValidationError):
        OptimizationCustomerIntentV1.model_validate({**raw, "total_cap_micros": 1})
    with pytest.raises(ValidationError):
        PrepareOptimizationMandateV1(intent=intent, mandate_id="a" * 32)
