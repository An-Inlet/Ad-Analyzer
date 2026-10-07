import json
from datetime import timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.executors.google_publication import (
    GooglePublicationHTTP,
    GooglePublicationUnavailable,
    serialize,
)
from app.publication.google_compiler import compile_google, materialize_google
from app.publication.provider_contracts import (
    BoundProviderRequest,
    ProviderContext,
    ProviderReceipt,
    ProviderResponse,
)
from pydantic import SecretStr

from tests.test_provider_publication_contracts import NOW, review


def context(request: BoundProviderRequest) -> ProviderContext:
    return ProviderContext(
        scope=request.scope,
        login_customer_id=request.login_customer_id,
        access_token=SecretStr("mock-only"),
        expires_at=NOW + timedelta(hours=1),
    )


def first() -> BoundProviderRequest:
    return materialize_google(
        compile_google(review()), "c" * 32, "budget", {}, {}, uuid4().hex, NOW
    )


@pytest.mark.parametrize("total_budget", [False, True])
def test_actual_http_mocked_full_google_dag_validate_mutate_readback(total_budget: bool) -> None:
    from tests.test_google_total_publication import total_review

    plan = compile_google(total_review() if total_budget else review())
    requests: dict[str, BoundProviderRequest] = {}
    receipts: dict[str, ProviderReceipt] = {}
    calls: list[httpx.Request] = []
    expected_read: dict[str, Any] = {}
    current_resource = ""
    current_table = ""

    def send(raw: httpx.Request) -> httpx.Response:
        calls.append(raw)
        assert raw.url.host == "googleads.googleapis.com"
        assert raw.url.path.startswith("/v25/customers/1234567890/")
        assert raw.headers["Authorization"] == "Bearer mock-only"
        assert "developer-token" not in raw.headers
        body = json.loads(raw.content)
        if raw.url.path.endswith("googleAds:search"):
            assert f"{current_table}.resource_name = '{current_resource}'" in body["query"]
            key = current_table.split("_")[0] + "".join(
                part.title() for part in current_table.split("_")[1:]
            )
            return httpx.Response(200, json={"results": [{key: expected_read}]})
        if raw.url.path.endswith("conversionGoalCampaignConfigs:mutate"):
            assert set(body) == {"operations", "validateOnly"}
        else:
            assert set(body) == {"operations", "validateOnly", "partialFailure"}
            assert body["partialFailure"] is False
        if body["validateOnly"]:
            return httpx.Response(200, json={})
        assert len(body["operations"]) == 1
        return httpx.Response(200, json={"results": [{"resourceName": current_resource}]})

    adapter = GooglePublicationHTTP(transport=httpx.MockTransport(send))
    for index, step in enumerate(plan.steps):
        request = materialize_google(
            plan, "c" * 32, step.step_id, receipts, requests, uuid4().hex, NOW
        )
        collection, current_table, operation = serialize(request)
        suffix = f"{index + 1}"
        if collection in {"campaignCriteria", "adGroupCriteria", "adGroupAds"}:
            suffix = f"2~{index + 1}"
        current_resource = f"customers/1234567890/{collection}/{suffix}"
        expected_read = dict(operation.get("create", operation.get("update", {})))
        if "resourceName" in expected_read:
            current_resource = expected_read["resourceName"]
        expected_read["resourceName"] = current_resource
        if "manualCpc" in expected_read:
            del expected_read["manualCpc"]
            expected_read["biddingStrategyType"] = "MANUAL_CPC"
        validation = adapter.validate_only(request, context(request), NOW)
        assert validation.valid and not validation.publication_authorized
        response = adapter.apply_once(request, context(request), NOW)
        assert response.outcome == "acknowledged"
        receipt = adapter.read_back(request, response, context(request), NOW)
        assert receipt.outcome == "verified_effect"
        requests[step.step_id], receipts[step.step_id] = request, receipt
    assert len(calls) == 3 * len(plan.steps)
    campaign_body = json.loads(calls[4].content)["operations"][0]["create"]
    assert campaign_body["status"] == "PAUSED"
    assert campaign_body["campaignBudget"] == "customers/1234567890/campaignBudgets/1"
    assert campaign_body["manualCpc"] == {}
    assert campaign_body["startDateTime"] == "2026-10-06 00:00:00"
    assert campaign_body["finalUrlSuffix"] == "utm_source=google"


@pytest.mark.parametrize("after_effect", [False, True])
def test_timeout_before_or_after_effect_stays_unknown_without_replay(after_effect: bool) -> None:
    calls = 0
    effects: list[bytes] = []

    def timeout(raw: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if after_effect:
            effects.append(raw.content)
        raise httpx.ReadTimeout("private raw error must not escape", request=raw)

    request = first()
    adapter = GooglePublicationHTTP(transport=httpx.MockTransport(timeout))
    response = adapter.apply_once(request, context(request), NOW)
    assert response.outcome == "unknown"
    assert adapter.reconcile(request, [response], context(request), NOW).outcome == "unknown"
    assert calls == 1
    assert len(effects) == int(after_effect)


@pytest.mark.parametrize(
    "response_body",
    [
        {"results": []},
        {"results": [{"resourceName": "customers/9999999999/campaignBudgets/1"}]},
        {"partialFailureError": {"message": "private"}},
        {"results": [{}, {}]},
    ],
)
def test_invalid_mutation_ack_is_unknown(response_body: dict[str, Any]) -> None:
    request = first()
    adapter = GooglePublicationHTTP(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response_body))
    )
    assert adapter.apply_once(request, context(request), NOW).outcome == "unknown"


def test_absent_readback_never_authoritative_no_effect_and_foreign_history_rejected() -> None:
    request = first()
    response = ProviderResponse(
        request_digest=request.digest(),
        outcome="acknowledged",
        resource_name="customers/1234567890/campaignBudgets/1",
    )
    calls: list[httpx.Request] = []

    def empty(raw: httpx.Request) -> httpx.Response:
        calls.append(raw)
        return httpx.Response(200, json={"results": []})

    adapter = GooglePublicationHTTP(transport=httpx.MockTransport(empty))
    assert adapter.reconcile(request, [response], context(request), NOW).outcome == "unknown"
    assert len(calls) == 1 and calls[0].url.path.endswith("googleAds:search")
    altered = response.model_copy(update={"request_digest": "d" * 64})
    with pytest.raises(GooglePublicationUnavailable):
        adapter.reconcile(request, [altered], context(request), NOW)
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["foreign", "generation", "expired", "login"])
def test_context_fails_before_io(change: str) -> None:
    request = first()
    ctx = context(request)
    if change in {"foreign", "generation"}:
        field, value = (
            ("workspace_id", 99) if change == "foreign" else ("connection_version", "reconnected")
        )
        ctx = ctx.model_copy(update={"scope": ctx.scope.model_copy(update={field: value})})
    elif change == "expired":
        ctx = ctx.model_copy(update={"expires_at": NOW})
    else:
        ctx = ctx.model_copy(update={"login_customer_id": "9999999999"})

    def no_io(_: httpx.Request) -> httpx.Response:
        pytest.fail("ineligible context must not call provider")

    adapter = GooglePublicationHTTP(transport=httpx.MockTransport(no_io))
    with pytest.raises(GooglePublicationUnavailable):
        adapter.apply_once(request, ctx, NOW)


def test_redirect_rate_limit_and_oversized_responses_not_retried() -> None:
    request = first()
    for response in [
        httpx.Response(302, headers={"location": "https://example.invalid"}),
        httpx.Response(429),
        httpx.Response(200, content=b"a" * 1_000_001),
    ]:
        calls: list[httpx.Request] = []

        def send(
            raw: httpx.Request,
            calls: list[httpx.Request] = calls,
            response: httpx.Response = response,
        ) -> httpx.Response:
            calls.append(raw)
            return response

        adapter = GooglePublicationHTTP(transport=httpx.MockTransport(send))
        assert adapter.apply_once(request, context(request), NOW).outcome == "unknown"
        assert len(calls) == 1


def test_readback_semantic_drift_conflicts_and_known_ack_reconciles_without_mutation() -> None:
    request = first()
    expected = {
        "resourceName": "customers/1234567890/campaignBudgets/1",
        "amountMicros": "100000000",
        "period": "DAILY",
        "deliveryMethod": "STANDARD",
    }
    response = ProviderResponse(
        request_digest=request.digest(),
        outcome="acknowledged",
        resource_name=expected["resourceName"],
    )
    calls: list[httpx.Request] = []

    def send(raw: httpx.Request) -> httpx.Response:
        calls.append(raw)
        return httpx.Response(200, json={"results": [{"campaignBudget": expected}]})

    adapter = GooglePublicationHTTP(transport=httpx.MockTransport(send))
    # Protobuf JSON omits default false; requested explicitlyShared=false remains verifiable.
    assert (
        adapter.reconcile(request, [response], context(request), NOW).outcome == "verified_effect"
    )
    expected["amountMicros"] = "200000000"
    assert adapter.reconcile(request, [response], context(request), NOW).outcome == "conflict"
    assert all(call.url.path.endswith("googleAds:search") for call in calls)


def test_acknowledged_different_resources_conflict_without_guessing() -> None:
    request = first()
    responses = [
        ProviderResponse(
            request_digest=request.digest(),
            outcome="acknowledged",
            resource_name=f"customers/1234567890/campaignBudgets/{value}",
        )
        for value in [1, 2]
    ]

    def no_io(_: httpx.Request) -> httpx.Response:
        pytest.fail("contradictory receipts cannot choose an arbitrary resource")

    adapter = GooglePublicationHTTP(transport=httpx.MockTransport(no_io))
    assert adapter.reconcile(request, responses, context(request), NOW).outcome == "conflict"


def test_new_provider_path_does_not_weaken_fixture_execution_guard() -> None:
    from app.publication.fixture import require_fixture

    with pytest.raises(ValueError):
        require_fixture(GooglePublicationHTTP())
