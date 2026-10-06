from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from app.campaign_review.contracts import ReviewArtifact, RevisionInput
from app.publication.contracts import PublicationScope
from app.publication.google_compiler import compile_google, materialize_google
from app.publication.provider_contracts import (
    BoundProviderRequest,
    ProviderPublicationReview,
    ProviderPublishPlan,
    ProviderReceipt,
    get_provider_publication_transport,
)
from pydantic import ValidationError

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def review() -> ProviderPublicationReview:
    scope = PublicationScope(
        workspace_id=1,
        account={"account_id": 2, "connection_id": 3, "platform": "google_ads"},
        external_advertiser_id="1234567890",
        connection_version="generation-a",
        mandate_id="a" * 32,
        mandate_revision=1,
    )
    source = ReviewArtifact(
        draft_id="b" * 32,
        revision=1,
        workspace_id=1,
        connection_version="generation-a",
        definition=RevisionInput(
            account=scope.account,
            mandate_id=scope.mandate_id,
            mandate_revision=1,
            currency="USD",
            budget_micros=200_000_000,
            starts_at=NOW,
            ends_at=NOW + timedelta(days=1, seconds=-1),
            content={
                "kind": "google_search_v1",
                "objective": "website_sales",
                "name": "Review name",
                "landing_page": "https://example.invalid/product",
                "audience": {"countries": ["US"], "languages": ["en"]},
                "headlines": ["One", "Two", "Three"],
                "descriptions": ["First description", "Second description"],
                "exact_keywords": ["reviewed keyword"],
            },
        ),
        media=[],
        offline_reviewable=True,
        blockers=[],
    )
    return ProviderPublicationReview(
        source=source,
        source_digest=source.fingerprint(),
        scope=scope,
        configuration={
            "kind": "google_search_v25",
            "account_timezone": "UTC",
            "login_customer_id": None,
            "daily_budget_micros": 100_000_000,
            "budget_semantics": "average_daily_not_hard_cap",
            "reservation_micros": 200_000_000,
            "bidding": "MANUAL_CPC",
            "max_cpc_micros": 1_000_000,
            "custom_conversion_goal": "customers/1234567890/customConversionGoals/42",
            "conversion_actions": ["customers/1234567890/conversionActions/43"],
            "country_targets": {"US": "geoTargetConstants/2840"},
            "language_targets": {"en": "languageConstants/1000"},
            "google_search": True,
            "search_partners": False,
            "content_network": False,
            "positive_geo_target": "PRESENCE",
            "negative_geo_target": "PRESENCE",
            "political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
            "tracking_url_template": "",
            "final_url_suffix": "utm_source=google",
            "activation_policy": "separate_exact_approval",
            "omission_policy": "no_optional_assets_or_automation_requested",
        },
        qualification_blockers=["production_mandate_unavailable", "provider_unqualified"],
    )


def test_separate_versioned_exact_compiler_and_disabled_runtime() -> None:
    r = review()
    plan = compile_google(r)
    assert plan.review_digest == r.digest()
    assert len(plan.steps) == 8
    assert all(getattr(step.operation, "status", "PAUSED") == "PAUSED" for step in plan.steps)
    assert not plan.publication_eligible
    assert get_provider_publication_transport() is None
    assert compile_google(r).digest() == plan.digest()
    changed = r.model_dump()
    changed["configuration"]["search_partners"] = True
    assert (
        compile_google(ProviderPublicationReview.model_validate(changed)).digest() != plan.digest()
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("daily_budget_micros", 100_000_001),
        ("bidding", "guessed_default"),
        ("conversion_actions", ["customers/9999999999/conversionActions/1"]),
        ("country_targets", {"GB": "geoTargetConstants/2826"}),
        ("content_network", True),
    ],
)
def test_unreviewed_or_foreign_fields_rejected(field: str, value: Any) -> None:
    body = review().model_dump()
    body["configuration"][field] = value
    with pytest.raises(ValueError):
        ProviderPublicationReview.model_validate(body)


def test_missing_explicit_policy_rejected() -> None:
    body = review().model_dump()
    del body["configuration"]["omission_policy"]
    with pytest.raises(ValidationError):
        ProviderPublicationReview.model_validate(body)


def dependencies() -> tuple[ProviderPublishPlan, BoundProviderRequest, ProviderReceipt]:
    plan = compile_google(review())
    request = materialize_google(plan, "c" * 32, "budget", {}, {}, uuid4().hex, NOW)
    receipt = ProviderReceipt(
        scope=request.scope,
        plan_id=request.plan_id,
        plan_digest=request.plan_digest,
        step_id="budget",
        fence=request.fence,
        request_digest=request.digest(),
        outcome="verified_effect",
        resource_name="customers/1234567890/campaignBudgets/10",
        readback_digest="d" * 64,
        evidence="exact_readback",
        observed_at=NOW,
    )
    return plan, request, receipt


def test_dependency_binds_original_request_scope_and_fence() -> None:
    plan, request, receipt = dependencies()
    result = materialize_google(
        plan,
        request.plan_id,
        "campaign",
        {"budget": receipt},
        {"budget": request},
        uuid4().hex,
        NOW,
    )
    assert result.resources == {"budget": receipt.resource_name}
    for field, value in [
        ("fence", "e" * 32),
        ("plan_id", "f" * 32),
        ("observed_at", NOW - timedelta(seconds=1)),
    ]:
        altered = receipt.model_copy(update={field: value})
        with pytest.raises(ValueError):
            materialize_google(
                plan,
                request.plan_id,
                "campaign",
                {"budget": altered},
                {"budget": request},
                uuid4().hex,
                NOW,
            )


def test_operation_tampering_cannot_materialize_even_with_recomputed_plan_digest() -> None:
    plan, request, receipt = dependencies()
    data = plan.model_dump()
    data["steps"][1]["operation"]["name"] = "Unreviewed name"
    altered = ProviderPublishPlan.model_validate(data)
    with pytest.raises(ValueError, match="noncanonical"):
        materialize_google(
            altered,
            request.plan_id,
            "campaign",
            {"budget": receipt},
            {"budget": request},
            uuid4().hex,
            NOW,
        )


def test_no_effect_requires_authoritative_evidence() -> None:
    _, _, receipt = dependencies()
    data = receipt.model_dump()
    data.update(
        outcome="verified_no_effect",
        evidence="unresolved",
        resource_name=None,
        readback_digest=None,
    )
    with pytest.raises(ValueError):
        ProviderReceipt.model_validate(data)


def test_blocked_source_not_promoted_to_provider_plan() -> None:
    data = review().model_dump()
    source = ReviewArtifact.model_validate(data["source"]).model_copy(
        update={"blockers": ["connection_reauthorization_required"]}
    )
    data.update(source=source.model_dump(), source_digest=source.fingerprint())
    with pytest.raises(ValueError):
        ProviderPublicationReview.model_validate(data)
