from datetime import timedelta
from typing import Any

import pytest
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    NormalizedProviderReceipt,
    ProviderMandateBinding,
    ProviderMandatePolicy,
)
from app.publication.optimization_contracts import (
    BudgetOwnerRef,
    MetaCurrentState,
    OptimizationIntent,
    OptimizationRequest,
    OptimizationTarget,
)

from tests.test_provider_publication_contracts import NOW


def policy() -> ProviderMandatePolicy:
    scope = ExecutionAccount(
        workspace_id=1,
        account={"account_id": 1, "connection_id": 2, "platform": "meta_ads"},
        external_advertiser_id="123",
        connection_version="meta:fixture:1",
    )
    return ProviderMandatePolicy(
        environment="contract_test",
        workspace_id=1,
        goal_id="a" * 32,
        goal_revision=1,
        currency="USD",
        time_zone="UTC",
        starts_at=NOW,
        ends_at=NOW + timedelta(days=1),
        accounts=[scope],
        total_cap_micros=100_000_000,
        per_plan_cap_micros=80_000_000,
        positive_change_cap_micros=20_000_000,
        action_limit=10,
        cooldown_seconds=10,
        freshness_seconds=300,
        aggressiveness_percent=5,
        allowed_purposes=["create_paused", "activate"],
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )


def binding(p: ProviderMandatePolicy) -> ProviderMandateBinding:
    return ProviderMandateBinding(
        mandate_id="b" * 32,
        revision=1,
        consent_id="c" * 32,
        policy_digest=p.digest(),
        ledger_id="d" * 32,
        environment=p.environment,
    )


def exposure(p: ProviderMandatePolicy) -> ExposureEvidence:
    return ExposureEvidence(
        environment=p.environment,
        mandate=binding(p),
        account=p.accounts[0],
        covered_account_ids=[1],
        budget_owner_key="meta/123/campaign/5",
        target_set_digest="e" * 64,
        state_digest="f" * 64,
        currency="USD",
        period_start=p.starts_at,
        period_end=p.ends_at,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        reporting_watermark=NOW,
        completeness="complete",
        qualification_id="e" * 32,
        model_version="contract_case_v1",
        cap_semantics="contract_scenario",
        reported_spend_micros=10_000_000,
        unreported_upper_micros=5_000_000,
        unchanged_future_upper_micros=10_000_000,
        proposed_owner_upper_micros=20_000_000,
        existing_reservations_micros=10_000_000,
        portfolio_upper_micros=55_000_000,
    )


def test_full_portfolio_bound_includes_lag_and_reservations() -> None:
    p = policy()
    e = exposure(p)
    assert e.eligible(p, NOW)
    data = e.model_dump()
    data["portfolio_upper_micros"] = 30_000_000
    with pytest.raises(ValueError):
        ExposureEvidence.model_validate(data)
    data.update(portfolio_upper_micros=None, unreported_upper_micros=None)
    assert not ExposureEvidence.model_validate(data).eligible(p, NOW)
    assert not e.eligible(p, NOW + timedelta(minutes=6))


def test_contract_scenario_cannot_be_live_authority() -> None:
    data = exposure(policy()).model_dump()
    data["environment"] = "live"
    data["mandate"]["environment"] = "live"
    with pytest.raises(ValueError):
        ExposureEvidence.model_validate(data)


def test_aggressiveness_never_modifies_total_cap() -> None:
    p = policy()
    data = p.model_dump()
    data["aggressiveness_percent"] = 20
    changed = ProviderMandatePolicy.model_validate(data)
    assert changed.total_cap_micros == p.total_cap_micros
    assert changed.digest() != p.digest()
    assert not exposure(p).eligible(changed, NOW)


def projection() -> dict[str, Any]:
    p = policy()
    return dict(
        receipt_id="1" * 32,
        receipt_digest="1" * 64,
        sequence=1,
        supersedes_receipt_id=None,
        run_id="2" * 32,
        action_id="3" * 32,
        plan_id="4" * 32,
        step_id="campaign",
        attempt_id="5" * 32,
        review_digest="2" * 64,
        plan_digest="3" * 64,
        request_digest="4" * 64,
        fence="6" * 32,
        environment="contract_test",
        purpose="create_paused",
        account=p.accounts[0],
        mandate=binding(p),
        source_draft_id="7" * 32,
        source_revision=1,
        goal_id=p.goal_id,
        goal_revision=1,
        budget_owner_key="meta/123/campaign/5",
        target_set_digest="e" * 64,
        before_state_digest=None,
        after_state_digest=None,
        dispatched_at=NOW,
        observed_at=NOW,
        outcome="verified_effect",
        evidence="exact_readback",
        resource_kind="campaigns",
        resource_name="meta/123/campaigns/5",
        readback_digest="f" * 64,
    )


def test_status_receipt_cannot_invent_delivery_time_or_foreign_resource() -> None:
    body = projection()
    receipt = NormalizedProviderReceipt.model_validate(body)
    assert receipt.effective_lower is None and receipt.effective_upper is None
    body.update(
        effective_time_evidence="authoritative_interval", effective_lower=NOW, effective_upper=NOW
    )
    with pytest.raises(ValueError):
        NormalizedProviderReceipt.model_validate(body)
    body = projection()
    body["resource_name"] = "meta/999/campaigns/5"
    with pytest.raises(ValueError):
        NormalizedProviderReceipt.model_validate(body)


def optimization() -> OptimizationRequest:
    p = policy()
    target = OptimizationTarget(kind="campaign", external_id="5", campaign_id="5")
    owner = BudgetOwnerRef(
        provider="meta_ads",
        owner=target,
        mode="independent",
        affected_targets=[target],
        topology_digest="9" * 64,
    )
    state = MetaCurrentState(
        scope=p.accounts[0],
        target=target,
        budget_owner=owner,
        money={
            "currency": "USD",
            "currency_exponent": 2,
            "account_timezone": "UTC",
            "period_start": p.starts_at,
            "period_end": p.ends_at,
        },
        account_status="ACTIVE",
        configured_status="ACTIVE",
        effective_status="ACTIVE",
        parent_configured_status="ACTIVE",
        starts_at=NOW,
        ends_at=p.ends_at,
        sharing_enabled=False,
        schedule_adjustments_enabled=False,
        rebalance_enabled=False,
        unaffected_settings_digest="8" * 64,
        qualification_id="e" * 32,
        qualification_revision=1,
        unsupported_features=[],
        complete=True,
        observation_started_at=NOW,
        observed_at=NOW,
        objective="OUTCOME_SALES",
        buying_type="AUCTION",
        daily_budget_micros=10_000_000,
        lifetime_budget_micros=None,
    )
    intent = OptimizationIntent(
        scope=p.accounts[0],
        mandate=binding(p),
        target=target,
        budget_owner=owner,
        action={
            "kind": "meta_budget_set_v1",
            "budget_field": "daily_budget",
            "amount_micros": 20_000_000,
        },
        expected_state_digest=state.digest(),
        approved_target_set_digest=owner.target_set_digest(),
        qualification_id="e" * 32,
        qualification_revision=1,
        rationale_reference="7" * 64,
    )
    e = exposure(p).model_copy(
        update={"state_digest": state.digest(), "target_set_digest": owner.target_set_digest()}
    )
    return OptimizationRequest(
        intent=intent,
        intent_digest=intent.digest(),
        before=state,
        exposure=e,
        action_id="1" * 32,
        attempt_id="2" * 32,
        fence="3" * 32,
        dispatched_at=NOW,
    )


def test_exact_optimization_before_scope_budget_owner_and_precision() -> None:
    request = optimization()
    assert request.before.provider_cas == "unavailable"
    for field, value in [("amount_micros", 20_000_001), ("amount_micros", 0)]:
        data = request.model_dump()
        data["intent"]["action"][field] = value
        if value:
            data["intent_digest"] = OptimizationIntent.model_validate(data["intent"]).digest()
        with pytest.raises(ValueError):
            OptimizationRequest.model_validate(data)
    data = request.model_dump()
    data["before"]["budget_owner"]["owner"]["external_id"] = "99"
    with pytest.raises(ValueError):
        OptimizationRequest.model_validate(data)


def test_optimization_pause_cannot_smuggle_resume_or_budget() -> None:
    data = optimization().intent.model_dump()
    for action in [
        {"kind": "meta_status_set_v1", "status": "ACTIVE"},
        {"kind": "meta_status_set_v1", "status": "PAUSED", "amount_micros": 1},
    ]:
        data["action"] = action
        with pytest.raises(ValueError):
            OptimizationIntent.model_validate(data)
