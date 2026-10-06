"""Actual paused total-budget compilation; no financial or live qualification."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from app.executors.google_publication import GooglePublicationHTTP
from app.publication.customer_schemas import CreationIntent, GoogleTotalConfigurationIntent
from app.publication.google_compiler import compile_google, materialize_google
from app.publication.provider_contracts import (
    ProviderPublicationReview,
    ProviderPublishPlan,
)
from pydantic import ValidationError

from tests.test_google_publication_http import context
from tests.test_provider_publication_contracts import NOW, review


def total_review(
    days: int = 10, zone: str = "UTC", start: datetime | None = None
) -> ProviderPublicationReview:
    raw = review().model_dump()
    local = start or datetime(2026, 10, 6, tzinfo=ZoneInfo(zone))
    raw["source"]["definition"]["starts_at"] = local.astimezone(UTC)
    raw["source"]["definition"]["ends_at"] = (local + timedelta(days=days, seconds=-1)).astimezone(
        UTC
    )
    from app.campaign_review.contracts import ReviewArtifact

    raw["source_digest"] = ReviewArtifact.model_validate(raw["source"]).fingerprint()
    f = raw["configuration"]
    f.pop("daily_budget_micros")
    f.update(
        kind="google_search_total_v25_v1",
        total_budget_micros=200_000_000,
        budget_semantics="native_total_budget_not_portfolio_proof",
        account_timezone=zone,
    )
    return ProviderPublicationReview.model_validate(raw)


def test_legacy_daily_digest_unchanged() -> None:
    old = review()
    assert old.digest() == "33a8d693f769d17b62d038213b74b6a994454b54a3b679759d33720b887d48ce"
    assert (
        compile_google(old).digest()
        == "2532e599c75b353661d4c8298f72c90d083e091720d5f33acbf40ee08c25cb95"
    )


@pytest.mark.parametrize("days", [1, 2, 3, 90, 91])
def test_duration_boundary_is_unqualified_not_claimed_provider_error(days: int) -> None:
    with pytest.raises(ValidationError, match="inlet_total_budget_duration_boundary_unqualified"):
        total_review(days)


@pytest.mark.parametrize("month,day", [(3, 6), (10, 30)])
@pytest.mark.parametrize("days", [4, 89])
def test_interior_dst_exact_local_schedule(month: int, day: int, days: int) -> None:
    zone = ZoneInfo("America/New_York")
    source = total_review(days, str(zone), datetime(2026, month, day, tzinfo=zone))
    plan = compile_google(source)
    campaign = plan.steps[1].operation.model_dump()
    assert campaign["starts_local"] == f"2026-{month:02d}-{day:02d} 00:00:00"
    assert campaign["ends_local"].endswith("23:59:59")
    assert plan.compiler_id == "google_search_total_v25_v1"
    assert plan.publication_eligible is False


@pytest.mark.parametrize("failure", ["mixed", "excess", "compiler", "daily_op", "time", "shared"])
def test_exact_total_contract_rejects_mismatch(failure: str) -> None:
    raw = total_review().model_dump()
    if failure in {"compiler", "daily_op", "shared"}:
        plan = compile_google(total_review()).model_dump()
        if failure == "compiler":
            plan["compiler_id"] = "google_search_v25_v1"
        elif failure == "daily_op":
            plan["steps"][0]["operation"] = compile_google(review()).steps[0].operation.model_dump()
        else:
            plan["steps"][0]["operation"]["explicitly_shared"] = True
        with pytest.raises(ValidationError):
            ProviderPublishPlan.model_validate(plan)
        return
    if failure == "mixed":
        raw["configuration"]["daily_budget_micros"] = 1
    elif failure == "excess":
        raw["configuration"]["total_budget_micros"] += 1
    else:
        raw["source"]["definition"]["starts_at"] += timedelta(hours=1)
    with pytest.raises(ValidationError):
        ProviderPublicationReview.model_validate(raw)


@pytest.mark.parametrize("failure", [None, "daily", "amount", "period", "shared", "missing"])
def test_actual_total_budget_http_readback(failure: str | None) -> None:
    plan = compile_google(total_review())
    request = materialize_google(plan, "c" * 32, "budget", {}, {}, uuid4().hex, NOW)
    resource = "customers/1234567890/campaignBudgets/1"
    calls: list[str] = []

    def send(raw: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(raw.content)
        calls.append(raw.url.path)
        if raw.url.path.endswith("googleAds:search"):
            assert "campaign_budget.total_amount_micros" in body["query"]
            assert "campaign_budget.amount_micros" in body["query"]
            actual: dict[str, Any] = {
                "resourceName": resource,
                "totalAmountMicros": "200000000",
                "period": "CUSTOM_PERIOD",
                "deliveryMethod": "STANDARD",
                "explicitlyShared": False,
            }
            if failure == "daily":
                actual["amountMicros"] = "1"
            elif failure == "amount":
                actual["totalAmountMicros"] = "1"
            elif failure == "period":
                actual["period"] = "DAILY"
            elif failure == "shared":
                actual["explicitlyShared"] = True
            elif failure == "missing":
                actual.pop("totalAmountMicros")
            return httpx.Response(200, json={"results": [{"campaignBudget": actual}]})
        op = body["operations"][0]["create"]
        assert op == {
            "totalAmountMicros": "200000000",
            "period": "CUSTOM_PERIOD",
            "deliveryMethod": "STANDARD",
            "explicitlyShared": False,
        }
        assert body["partialFailure"] is False
        return httpx.Response(
            200, json={} if body["validateOnly"] else {"results": [{"resourceName": resource}]}
        )

    transport = GooglePublicationHTTP(transport=httpx.MockTransport(send))
    assert transport.validate_only(request, context(request), NOW).valid
    response = transport.apply_once(request, context(request), NOW)
    assert response.outcome == "acknowledged"
    receipt = transport.read_back(request, response, context(request), NOW)
    assert receipt.outcome == ("verified_effect" if failure is None else "conflict")
    assert len(calls) == 3


def test_customer_total_intent_is_explicit_and_exclusive() -> None:
    values = dict(draft_id="a" * 32, draft_revision=1, mandate_id="b" * 32, mandate_revision=1)
    f = dict(
        budget_kind="campaign_total_v1",
        total_budget_micros=1,
        max_cpc_micros=1,
        catalog_option_id="c" * 64,
    )
    assert isinstance(
        CreationIntent.model_validate({**values, "google": f}).google,
        GoogleTotalConfigurationIntent,
    )
    with pytest.raises(ValidationError):
        CreationIntent.model_validate({**values, "google": {**f, "daily_budget_micros": 1}})
    with pytest.raises(ValidationError):
        CreationIntent.model_validate(
            {**values, "google": {k: v for k, v in f.items() if k != "budget_kind"}}
        )
