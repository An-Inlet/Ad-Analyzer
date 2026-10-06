import pytest
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import (
    CurrentStateBase,
    GoogleBudgetOwnerRef,
    GoogleCurrentState,
    OptimizationTarget,
)
from pydantic import ValidationError

from tests.test_social_optimization_http import setup


@pytest.mark.parametrize(
    "provider,action,campaign,digest",
    [
        (
            "meta_ads",
            "budget",
            False,
            "ff30f817259b99ef1513fc425391713933b0d694064cb692f3497439e15838da",
        ),
        (
            "meta_ads",
            "budget",
            True,
            "af3b529018d49bf5a971c181ff1c1d7032e1d900f3d4c34ce6d9f67cb4ffced0",
        ),
        (
            "meta_ads",
            "pause",
            False,
            "b43ad42f11841ab62272b4cc77d4a27f443b02e8eef6c9368f0edc485f2fb5c6",
        ),
        (
            "meta_ads",
            "pause",
            True,
            "5ac883edd3f1f5a4a4b3d488990d8c28e64fb6d05aa115468a8b149cbd417845",
        ),
        (
            "tiktok_ads",
            "budget",
            False,
            "68dfe0d25f1000e76f517a962027e4f9ad6ab79aced73086ce2281e8bd84dfb4",
        ),
        (
            "tiktok_ads",
            "budget",
            True,
            "e2fd170650e6160efaffd02ce3039a8e0b0f16b2f8fff27cea2fab358596945c",
        ),
        (
            "tiktok_ads",
            "pause",
            False,
            "24d549da2f2014a216781a3b9ea0618fe79545157498c2ad99ce5cd184d8552a",
        ),
        (
            "tiktok_ads",
            "pause",
            True,
            "91852409e272995c3f61177012c9a9a4f78f1ed278b514460786b88c6974a84e",
        ),
    ],
)
def test_google_extension_preserves_frozen_social_documents(
    provider: str,
    action: str,
    campaign: bool,
    digest: str,
) -> None:
    assert setup(provider, action, campaign)[2].digest() == digest


def state() -> GoogleCurrentState:
    social = setup("meta_ads")[2].before
    values = social.model_dump(include=set(CurrentStateBase.model_fields))
    scope = ExecutionAccount.model_validate(
        {
            **social.scope.model_dump(),
            "account": {**social.scope.account.model_dump(), "platform": "google_ads"},
            "external_advertiser_id": "1234567890",
            "connection_version": "google:1:1",
        }
    )
    target = OptimizationTarget(kind="campaign", external_id="5", campaign_id="5")
    budget = "customers/1234567890/campaignBudgets/9"
    return GoogleCurrentState.model_validate(
        {
            **values,
            "scope": scope,
            "target": target,
            "budget_owner": GoogleBudgetOwnerRef(
                owner=target,
                affected_targets=[target],
                native_budget_resource=budget,
                topology_digest="a" * 64,
            ),
            "native_budget_resource": budget,
            "budget_amount_micros": 50_000_000,
            "budget_total_amount_micros": None,
            "budget_explicitly_shared": False,
            "budget_reference_count": 1,
            "owning_campaign_ids": ["5"],
            "budget_period": "DAILY",
            "budget_delivery_method": "STANDARD",
            "budget_status": "ENABLED",
            "budget_type": "STANDARD",
            "advertising_channel_type": "SEARCH",
            "advertising_channel_sub_type": "UNSPECIFIED",
            "bidding_strategy_type": "MANUAL_CPC",
            "manual_cpc_digest": "b" * 64,
            "network_settings_digest": "c" * 64,
            "campaign_start_date": "2026-10-01",
            "campaign_end_date": "2026-10-31",
            "configured_status": "ENABLED",
            "parent_configured_status": "ENABLED",
        }
    )


def test_native_budget_identity_is_the_shared_exposure_key() -> None:
    value = state()
    assert value.budget_owner.key(value.scope) == value.native_budget_resource


@pytest.mark.parametrize(
    "change",
    [
        {"budget_explicitly_shared": True},
        {"budget_reference_count": 2},
        {"owning_campaign_ids": ["5", "6"]},
        {"native_budget_resource": "customers/9999999999/campaignBudgets/9"},
    ],
)
def test_shared_or_foreign_native_owner_cannot_enter_bounded_google_profile(
    change: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        GoogleCurrentState.model_validate({**state().model_dump(), **change})
