"""Real Google REST serialization with deterministic offline provider responses."""

import copy
import json
import logging
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.optimization_http import OptimizationUnavailable
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import (
    MoneyContext,
    OptimizationContext,
    OptimizationIntent,
    OptimizationRequest,
    OptimizationTarget,
    get_optimization_transport,
)
from pydantic import SecretStr

from tests.test_execution_contracts import binding, exposure, policy
from tests.test_provider_publication_contracts import NOW

CUSTOMER = "1234567890"
BUDGET = f"customers/{CUSTOMER}/campaignBudgets/9"
CAMPAIGN = f"customers/{CUSTOMER}/campaigns/5"


class Server:
    def __init__(self) -> None:
        self.account: dict[str, Any] = {
            "id": CUSTOMER,
            "resourceName": f"customers/{CUSTOMER}",
            "status": "ENABLED",
            "currencyCode": "USD",
            "timeZone": "UTC",
        }
        self.campaign: dict[str, Any] = {
            "id": "5",
            "resourceName": CAMPAIGN,
            "campaignBudget": BUDGET,
            "status": "ENABLED",
            "primaryStatus": "ELIGIBLE",
            "advertisingChannelType": "SEARCH",
            "biddingStrategyType": "MANUAL_CPC",
            "networkSettings": {"targetGoogleSearch": True},
            "startDateTime": "2026-10-01 00:00:00",
            "endDateTime": "2026-10-31 23:59:59",
        }
        self.budget: dict[str, Any] = {
            "resourceName": BUDGET,
            "amountMicros": "50000000",
            "referenceCount": "1",
            "period": "DAILY",
            "deliveryMethod": "STANDARD",
            "status": "ENABLED",
            "type": "STANDARD",
        }
        self.subscriptions: list[dict[str, Any]] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.writes: list[dict[str, Any]] = []
        self.pages = False
        self.cycle = False
        self.hidden_owner = False
        self.duplicate_owner = False
        self.timeout = False
        self.ignore = False
        self.partial_failure = False
        self.bad_ack = False
        self.error: httpx.Response | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        assert req.url.host == "googleads.googleapis.com"
        assert req.url.path.startswith(f"/v25/customers/{CUSTOMER}/")
        assert req.method == "POST" and not req.url.query
        assert req.headers["authorization"] == "Bearer offline-token"
        assert req.headers["accept-encoding"] == "identity"
        assert req.extensions["timeout"] == {"connect": 5, "read": 12, "write": 12, "pool": 12}
        body = json.loads(req.content)
        self.calls.append((req.url.path, body))
        if self.error is not None:
            return self.error
        if req.url.path.endswith(":mutate"):
            assert body["partialFailure"] is False
            assert len(body["operations"]) == 1
            if body["validateOnly"]:
                return httpx.Response(200, json={})
            self.writes.append(body)
            op = body["operations"][0]
            if not self.ignore:
                if req.url.path.endswith("campaignBudgets:mutate"):
                    assert op["updateMask"] == "amountMicros"
                    assert set(op["update"]) == {"resourceName", "amountMicros"}
                    self.budget.update(op["update"])
                else:
                    assert op == {
                        "update": {"resourceName": CAMPAIGN, "status": "PAUSED"},
                        "updateMask": "status",
                    }
                    self.campaign.update(op["update"])
                    self.campaign["primaryStatus"] = "PAUSED"
            if self.timeout:
                raise httpx.ReadTimeout("private provider payload must not escape")
            result: dict[str, Any] = {"results": [{"resourceName": op["update"]["resourceName"]}]}
            if self.partial_failure:
                result["partialFailureError"] = {"message": "private provider error"}
            if self.bad_ack:
                result["results"] = [{"resourceName": "customers/9999999999/campaigns/1"}]
            return httpx.Response(200, json=result)
        query = body["query"]
        assert "pageSize" not in body
        if "FROM customer" in query:
            rows = [{"customer": self.account}]
        elif "FROM campaign_budget" in query:
            rows = [{"campaignBudget": self.budget}]
        elif "FROM recommendation_subscription" in query:
            rows = self.subscriptions
        elif "WHERE campaign.id" in query:
            assert "start_date_time" in query and "end_date_time" in query
            rows = [{"campaign": self.campaign}]
        else:
            assert "campaign.campaign_budget = '" + BUDGET + "'" in query
            if self.pages and "pageToken" not in body:
                return httpx.Response(200, json={"nextPageToken": "opaque"})
            if self.cycle:
                return httpx.Response(200, json={"nextPageToken": "opaque"})
            owner = {
                k: self.campaign[k] for k in ("id", "resourceName", "campaignBudget", "status")
            }
            rows = [{"campaign": owner}]
            if self.hidden_owner:
                rows.append(
                    {
                        "campaign": {
                            **owner,
                            "id": "6",
                            "resourceName": f"customers/{CUSTOMER}/campaigns/6",
                        }
                    }
                )
            if self.duplicate_owner:
                rows *= 2
        return httpx.Response(200, json={"results": copy.deepcopy(rows)})


def setup(
    kind: str = "budget",
) -> tuple[GoogleOptimizationTransport, Server, OptimizationRequest, OptimizationContext]:
    p = policy()
    scope = ExecutionAccount.model_validate(
        {
            **p.accounts[0].model_dump(),
            "account": {**p.accounts[0].account.model_dump(), "platform": "google_ads"},
            "external_advertiser_id": CUSTOMER,
            "connection_version": "google:1:1",
        }
    )
    p = p.model_copy(update={"accounts": [scope]})
    server = Server()
    adapter = GoogleOptimizationTransport(transport=httpx.MockTransport(server))
    ctx = OptimizationContext(
        scope=scope, access_token=SecretStr("offline-token"), expires_at=NOW + timedelta(hours=1)
    )
    target = OptimizationTarget(kind="campaign", external_id="5", campaign_id="5")
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=p.starts_at,
        period_end=p.ends_at,
    )
    state = adapter.read_current(scope, target, money, "e" * 32, 1, ctx, NOW)
    action = (
        {"kind": "google_budget_set_v1", "amount_micros": 45_000_000}
        if kind == "budget"
        else {"kind": "google_status_set_v1", "status": "PAUSED"}
    )
    intent = OptimizationIntent(
        scope=scope,
        mandate=binding(p),
        target=target,
        budget_owner=state.budget_owner,
        action=action,
        expected_state_digest=state.digest(),
        approved_target_set_digest=state.budget_owner.target_set_digest(),
        qualification_id="e" * 32,
        qualification_revision=1,
        rationale_reference="f" * 64,
    )
    ev = exposure(p).model_copy(
        update={
            "account": scope,
            "state_digest": state.digest(),
            "budget_owner_key": state.budget_owner.key(scope),
            "target_set_digest": state.budget_owner.target_set_digest(),
        }
    )
    request = OptimizationRequest(
        intent=intent,
        intent_digest=intent.digest(),
        before=state,
        exposure=ev,
        action_id="1" * 32,
        attempt_id="2" * 32,
        fence="3" * 32,
        dispatched_at=NOW,
    )
    return adapter, server, request, ctx


@pytest.mark.parametrize("kind", ["budget", "pause"])
def test_exact_masked_update_and_native_owner_readback(kind: str) -> None:
    adapter, server, request, ctx = setup(kind)
    evidence = adapter.validate_only(request, ctx, NOW)
    assert evidence.valid and evidence.kind == "provider_validate_only"
    assert not server.writes
    response = adapter.apply_once(request, ctx, NOW)
    assert response.outcome == "acknowledged"
    receipt = adapter.read_back(request, response, ctx, NOW)
    assert receipt.outcome == "verified_target_state"
    assert receipt.budget_owner_key == BUDGET
    assert receipt.after is not None and receipt.after.provider_cas == "unavailable"
    assert len(server.writes) == 1
    assert get_optimization_transport() is None


@pytest.mark.parametrize("mode", ["timeout", "partial_failure", "bad_ack"])
def test_ambiguous_response_reconciles_read_only_original_attempt(mode: str) -> None:
    adapter, server, request, ctx = setup()
    setattr(server, mode, True)
    response = adapter.apply_once(request, ctx, NOW)
    assert response.outcome == "unknown"
    for _ in range(2):
        receipt = adapter.reconcile(request, [response], ctx, NOW)
        assert (
            receipt.outcome == "verified_target_state" and receipt.attempt_id == request.attempt_id
        )
    assert len(server.writes) == 1


def test_old_state_is_not_no_effect_and_changed_unaffected_settings_conflict() -> None:
    adapter, server, request, ctx = setup()
    server.ignore = True
    response = adapter.apply_once(request, ctx, NOW)
    assert adapter.read_back(request, response, ctx, NOW).outcome == "unknown"
    server.campaign["networkSettings"]["targetSearchNetwork"] = True
    assert adapter.reconcile(request, [response], ctx, NOW).outcome == "conflict"
    assert len(server.writes) == 1


@pytest.mark.parametrize(
    "change",
    [
        "foreign_customer",
        "currency",
        "foreign_budget",
        "shared",
        "count",
        "hidden_owner",
        "duplicate_owner",
        "cycle",
        "amount",
        "strategy",
        "ai",
        "autoapply",
        "intraday",
        "bad_boolean",
    ],
)
def test_current_state_or_preflight_blocks_changes_without_mutation(change: str) -> None:
    adapter, server, request, ctx = setup()
    if change == "foreign_customer":
        server.account["id"] = "9999999999"
    elif change == "currency":
        server.account["currencyCode"] = "EUR"
    elif change == "foreign_budget":
        server.campaign["campaignBudget"] = "customers/9999999999/campaignBudgets/9"
    elif change == "shared":
        server.budget["explicitlyShared"] = True
    elif change == "count":
        server.budget["referenceCount"] = "2"
    elif change in {"hidden_owner", "duplicate_owner", "cycle"}:
        server.pages = True
        setattr(server, change, True)
    elif change == "amount":
        server.budget["amountMicros"] = "60000000"
    elif change == "strategy":
        server.campaign["biddingStrategyType"] = "MAXIMIZE_CONVERSIONS"
    elif change == "ai":
        server.campaign["aiMaxSetting"] = {"enableAiMax": True}
    elif change == "autoapply":
        server.subscriptions = [
            {
                "recommendationSubscription": {
                    "resourceName": (
                        f"customers/{CUSTOMER}/recommendationSubscriptions/CAMPAIGN_BUDGET"
                    ),
                    "type": "CAMPAIGN_BUDGET",
                    "status": "ENABLED",
                }
            }
        ]
    elif change == "intraday":
        server.campaign["startDateTime"] = "2026-10-01 05:00:00"
    else:
        server.budget["explicitlyShared"] = "false"
    with pytest.raises(OptimizationUnavailable):
        adapter.apply_once(request, ctx, NOW)
    assert not server.writes


def test_complete_paginated_ownership_and_native_indefinite_end() -> None:
    adapter, server, request, ctx = setup()
    server.pages = True
    server.campaign.pop("endDateTime")
    state = adapter.read_current(
        request.intent.scope, request.intent.target, request.before.money, "e" * 32, 1, ctx, NOW
    )
    assert state.ends_at is None and state.campaign_end_date is None
    queries = [body for _, body in server.calls if "pageToken" in body]
    assert queries and all(body["pageToken"] == "opaque" for body in queries)


@pytest.mark.parametrize("failure", ["redirect", "compressed", "large", "array", "provider_error"])
def test_bounded_sanitized_http_and_no_private_logging(
    failure: str, caplog: pytest.LogCaptureFixture
) -> None:
    adapter, server, request, ctx = setup()
    responses = {
        "redirect": httpx.Response(302, headers={"Location": "https://evil.invalid/private"}),
        "compressed": httpx.Response(
            200, headers={"Content-Encoding": "gzip"}, stream=httpx.ByteStream(b"bad")
        ),
        "large": httpx.Response(200, content=b"x" * 2_000_001),
        "array": httpx.Response(200, json=[]),
        "provider_error": httpx.Response(403, json={"error": "private-secret"}),
    }
    server.error = responses[failure]
    with (
        caplog.at_level(logging.INFO, logger="httpx"),
        pytest.raises(OptimizationUnavailable) as caught,
    ):
        adapter.apply_once(request, ctx, NOW)
    assert "private" not in str(caught.value)
    assert "googleads.googleapis.com" not in caplog.text
    assert not server.writes


def test_late_effect_after_timeout_never_resubmits() -> None:
    adapter, server, request, ctx = setup()
    server.timeout = server.ignore = True
    response = adapter.apply_once(request, ctx, NOW)
    assert response.outcome == "unknown"
    assert adapter.reconcile(request, [response], ctx, NOW).outcome == "unknown"
    server.budget["amountMicros"] = "45000000"
    assert adapter.reconcile(request, [response], ctx, NOW).outcome == "verified_target_state"
    assert len(server.writes) == 1


@pytest.mark.parametrize("change", ["expired", "foreign", "live", "stale", "budget_precision"])
def test_invalid_context_or_bound_evidence_emits_no_http(change: str) -> None:
    from pydantic import ValidationError

    adapter, server, request, ctx = setup()
    server.calls.clear()
    if change == "expired":
        ctx = ctx.model_copy(update={"expires_at": NOW})
    elif change == "foreign":
        ctx = ctx.model_copy(
            update={"scope": ctx.scope.model_copy(update={"external_advertiser_id": "9999999999"})}
        )
    elif change == "live":
        request = request.model_copy(
            update={"exposure": request.exposure.model_copy(update={"environment": "live"})}
        )
    elif change == "budget_precision":
        intent = request.intent.model_copy(
            update={"action": request.intent.action.model_copy(update={"amount_micros": 12345})}
        )
        request = request.model_copy(update={"intent": intent, "intent_digest": intent.digest()})
    with pytest.raises((OptimizationUnavailable, ValidationError)):
        adapter.apply_once(request, ctx, NOW + timedelta(minutes=6) if change == "stale" else NOW)
    assert not server.calls and not server.writes


def test_initial_unsupported_state_cannot_validate_or_apply() -> None:
    adapter, server, request, ctx = setup()
    server.campaign["biddingStrategyType"] = "MAXIMIZE_CONVERSIONS"
    before = adapter.read_current(
        request.intent.scope, request.intent.target, request.before.money, "e" * 32, 1, ctx, NOW
    )
    assert "google_search_manual_cpc_required" in before.unsupported_features
    intent = request.intent.model_copy(update={"expected_state_digest": before.digest()})
    request = OptimizationRequest.model_validate(
        {
            **request.model_dump(),
            "before": before,
            "intent": intent,
            "intent_digest": intent.digest(),
            "exposure": request.exposure.model_copy(update={"state_digest": before.digest()}),
        }
    )
    server.calls.clear()
    assert not adapter.validate_only(request, ctx, NOW).valid
    with pytest.raises(OptimizationUnavailable):
        adapter.apply_once(request, ctx, NOW)
    assert not server.calls


def test_optional_legacy_headers_and_secret_exclusion() -> None:
    adapter, server, request, ctx = setup()
    checked: list[httpx.Headers] = []

    def handler(req: httpx.Request) -> httpx.Response:
        checked.append(req.headers)
        return server(req)

    adapter.transport = httpx.MockTransport(handler)
    ctx = ctx.model_copy(
        update={"developer_token": SecretStr("offline-legacy"), "login_customer_id": "2345678901"}
    )
    assert adapter.validate_only(request, ctx, NOW).valid
    assert checked[0]["developer-token"] == "offline-legacy"
    assert checked[0]["login-customer-id"] == "2345678901"
    assert "offline" not in ctx.model_dump_json()
