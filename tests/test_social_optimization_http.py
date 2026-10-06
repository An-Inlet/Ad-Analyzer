"""Actual HTTP serialization against offline responses, not authority fixtures."""

import json
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from app.executors.meta_optimization import MetaOptimizationTransport
from app.executors.optimization_http import OptimizationUnavailable
from app.executors.tiktok_optimization import TikTokOptimizationTransport
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


class Server:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.posts: list[dict[str, Any]] = []
        self.ignore = False
        self.timeout = False
        self.foreign = False
        self.currency = "USD"
        self.extra_child = False
        self.meta_campaign: dict[str, Any] = dict(
            id="5",
            account_id="123",
            configured_status="ACTIVE",
            effective_status="ACTIVE",
            daily_budget="0",
            lifetime_budget="0",
            is_budget_schedule_enabled=False,
            is_adset_budget_sharing_enabled=False,
            budget_rebalance_flag=False,
            objective="OUTCOME_SALES",
            buying_type="AUCTION",
        )
        self.meta_child: dict[str, Any] = dict(
            id="6",
            account_id="123",
            campaign_id="5",
            configured_status="ACTIVE",
            effective_status="ACTIVE",
            daily_budget="5000",
            lifetime_budget="0",
            is_budget_schedule_enabled=False,
            start_time=NOW.isoformat(),
            end_time=(NOW + timedelta(days=1)).isoformat(),
            targeting={"geo_locations": {"countries": ["US"]}},
            promoted_object={"pixel_id": "101", "custom_event_type": "PURCHASE"},
            bid_strategy="LOWEST_COST_WITHOUT_CAP",
            optimization_goal="OFFSITE_CONVERSIONS",
        )
        self.tk_campaign: dict[str, Any] = dict(
            advertiser_id="123",
            campaign_id="5",
            operation_status="ENABLE",
            secondary_status="CAMPAIGN_STATUS_ENABLE",
            budget=0,
            budget_mode="BUDGET_MODE_INFINITE",
            campaign_type="REGULAR_CAMPAIGN",
            objective_type="WEB_CONVERSIONS",
            budget_optimize_on=False,
            is_smart_performance_campaign=False,
        )
        self.tk_child: dict[str, Any] = dict(
            advertiser_id="123",
            campaign_id="5",
            adgroup_id="6",
            operation_status="ENABLE",
            secondary_status="ADGROUP_STATUS_DELIVERY_OK",
            budget=50,
            budget_mode="BUDGET_MODE_DAY",
            promotion_type="WEBSITE",
            schedule_type="SCHEDULE_START_END",
            schedule_start_time=NOW.strftime("%Y-%m-%d %H:%M:%S"),
            schedule_end_time=(NOW + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            dayparting="1" * 336,
        )

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            response: dict[str, Any]
            if self.provider == "meta_ads":
                body = {k: v[0] for k, v in parse_qs(req.content.decode()).items()}
                row = self.meta_campaign if req.url.path.endswith("/5") else self.meta_child
                updates = {
                    ("configured_status" if k == "status" else k): v for k, v in body.items()
                }
                response = {"success": True}
            else:
                body = json.loads(req.content)
                row = self.tk_campaign if "/campaign/" in req.url.path else self.tk_child
                updates = {k: v for k, v in body.items() if k in {"budget", "operation_status"}}
                response = {"code": 0, "data": {}}
            self.posts.append(body)
            if not self.ignore:
                row.update(updates)
            if self.timeout:
                raise httpx.ReadTimeout("offline ambiguous acknowledgement")
            return httpx.Response(200, json=response)
        path = req.url.path
        if self.provider == "meta_ads":
            if path.endswith("/act_123"):
                data = {
                    "account_id": "123",
                    "currency": self.currency,
                    "timezone_name": "UTC",
                    "account_status": 1,
                }
            elif path.endswith("/adsets"):
                rows = [{"id": "6", "account_id": "123", "campaign_id": "5"}]
                if self.extra_child:
                    rows.append({"id": "7", "account_id": "123", "campaign_id": "5"})
                data = {"data": rows}
            else:
                data = dict(self.meta_campaign if path.endswith("/5") else self.meta_child)
                if self.foreign:
                    data["account_id"] = "999"
            return httpx.Response(200, json=data)
        if "/advertiser/info/" in path:
            data = {
                "list": [
                    {
                        "advertiser_id": "123",
                        "currency": self.currency,
                        "timezone": "UTC",
                        "status": "STATUS_ENABLE",
                    }
                ]
            }
        else:
            filters = json.loads(req.url.params["filtering"])
            assert filters["primary_status"] == "STATUS_ALL"
            row = dict(self.tk_campaign if "/campaign/" in path else self.tk_child)
            if self.foreign:
                row["advertiser_id"] = "999"
            data = {"list": [row], "page_info": {"page": 1, "total_page": 1}}
        return httpx.Response(200, json={"code": 0, "data": data})


def setup(
    provider: str, action_kind: str = "budget", campaign: bool = False
) -> tuple[Any, Server, OptimizationRequest, OptimizationContext]:
    p = policy()
    scope = ExecutionAccount.model_validate(
        {
            **p.accounts[0].model_dump(),
            "account": {**p.accounts[0].account.model_dump(), "platform": provider},
        }
    )
    p = p.model_copy(update={"accounts": [scope]})
    server = Server(provider)
    if campaign:
        server.meta_campaign["daily_budget"] = "5000"
        server.tk_campaign.update(budget=50, budget_mode="BUDGET_MODE_DAY")
    adapter = (
        MetaOptimizationTransport if provider == "meta_ads" else TikTokOptimizationTransport
    )(transport=httpx.MockTransport(server))
    ctx = OptimizationContext(
        scope=scope, access_token=SecretStr("offline-token"), expires_at=NOW + timedelta(hours=1)
    )
    target = OptimizationTarget(
        kind="campaign" if campaign else ("adset" if provider == "meta_ads" else "adgroup"),
        external_id="5" if campaign else "6",
        campaign_id="5",
    )
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=p.starts_at,
        period_end=p.ends_at,
    )
    state = adapter.read_current(scope, target, money, "e" * 32, 1, ctx, NOW)
    action: dict[str, Any]
    if action_kind == "budget":
        action = (
            {
                "kind": "meta_budget_set_v1",
                "budget_field": "daily_budget",
                "amount_micros": 45_000_000,
            }
            if provider == "meta_ads"
            else {
                "kind": "tiktok_budget_set_v1",
                "budget_mode": "BUDGET_MODE_DAY",
                "amount_micros": 45_000_000,
            }
        )
    else:
        action = (
            {"kind": "meta_status_set_v1", "status": "PAUSED"}
            if provider == "meta_ads"
            else {"kind": "tiktok_status_set_v1", "operation_status": "DISABLE"}
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


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("kind", ["budget", "pause"])
def test_real_sparse_http_update_and_owned_readback(provider: str, kind: str) -> None:
    adapter, server, request, ctx = setup(provider, kind)
    assert adapter.validate_only(request, ctx, NOW).kind == "local_schema"
    response = adapter.apply_once(request, ctx, NOW)
    assert response.outcome == "acknowledged"
    receipt = adapter.read_back(request, response, ctx, NOW)
    assert receipt.outcome == "verified_target_state"
    assert receipt.fence == request.fence and receipt.attempt_id == request.attempt_id
    assert receipt.after.provider_cas == "unavailable"
    if provider == "meta_ads":
        assert server.posts == [
            {"daily_budget": "4500"} if kind == "budget" else {"status": "PAUSED"}
        ]
    elif kind == "budget":
        assert server.posts == [{"advertiser_id": "123", "adgroup_id": "6", "budget": 45.0}]
    else:
        assert server.posts == [
            {
                "advertiser_id": "123",
                "adgroup_ids": ["6"],
                "operation_status": "DISABLE",
                "allow_partial_success": False,
            }
        ]
    assert get_optimization_transport() is None


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("ignore", [False, True])
def test_timeout_preserves_unknown_and_reconcile_never_emits(provider: str, ignore: bool) -> None:
    adapter, server, request, ctx = setup(provider)
    server.timeout = True
    server.ignore = ignore
    response = adapter.apply_once(request, ctx, NOW)
    assert response.outcome == "unknown"
    receipt = adapter.reconcile(request, [response], ctx, NOW)
    assert receipt.outcome == ("unknown" if ignore else "verified_target_state")
    assert len(server.posts) == 1


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("drift", ["foreign", "currency", "budget"])
def test_fresh_preflight_drift_prevents_mutation(provider: str, drift: str) -> None:
    adapter, server, request, ctx = setup(provider)
    if drift == "foreign":
        server.foreign = True
    elif drift == "currency":
        server.currency = "EUR"
    elif provider == "meta_ads":
        server.meta_child["daily_budget"] = "5100"
    else:
        server.tk_child["budget"] = 51
    with pytest.raises(OptimizationUnavailable):
        adapter.apply_once(request, ctx, NOW)
    assert not server.posts


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_unsupported_exposure_never_authorizes_http(provider: str) -> None:
    adapter, server, request, ctx = setup(provider)
    data = request.model_dump()
    data["exposure"].update(
        completeness="incomplete", unreported_upper_micros=None, portfolio_upper_micros=None
    )
    request = OptimizationRequest.model_validate(data)
    assert not adapter.validate_only(request, ctx, NOW).valid
    with pytest.raises(OptimizationUnavailable):
        adapter.apply_once(request, ctx, NOW)
    assert not server.posts


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_foreign_readback_is_unknown_not_success(provider: str) -> None:
    adapter, server, request, ctx = setup(provider)
    response = adapter.apply_once(request, ctx, NOW)
    server.foreign = True
    assert adapter.read_back(request, response, ctx, NOW).outcome == "unknown"
    assert len(server.posts) == 1


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("kind", ["budget", "pause"])
def test_campaign_owner_covers_full_children(provider: str, kind: str) -> None:
    adapter, server, request, ctx = setup(provider, kind, campaign=True)
    assert len(request.intent.budget_owner.affected_targets) == 2
    assert request.intent.budget_owner.mode == "campaign_pool"
    response = adapter.apply_once(request, ctx, NOW)
    assert adapter.read_back(request, response, ctx, NOW).outcome == "verified_target_state"
    assert len(server.posts) == 1


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_missing_native_flags_blocks_without_mutating(provider: str) -> None:
    adapter, server, request, ctx = setup(provider)
    if provider == "meta_ads":
        del server.meta_campaign["is_adset_budget_sharing_enabled"]
    else:
        del server.tk_campaign["is_smart_performance_campaign"]
    with pytest.raises(OptimizationUnavailable):
        adapter.apply_once(request, ctx, NOW)
    assert not server.posts


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_cycling_or_changed_pagination_blocks(provider: str) -> None:
    adapter, server, request, ctx = setup(provider)

    def handler(req: httpx.Request) -> httpx.Response:
        response = server(req)
        if provider == "meta_ads" and req.url.path.endswith("/adsets"):
            data = response.json()
            data["paging"] = {
                "next": "https://untrusted.invalid/never-follow",
                "cursors": {"after": "cycle"},
            }
            return httpx.Response(200, json=data)
        if provider == "tiktok_ads" and "/adgroup/get/" in req.url.path:
            data = response.json()
            page = int(req.url.params["page"])
            data["data"]["page_info"] = {"page": page, "total_page": 2 if page == 1 else 3}
            return httpx.Response(200, json=data)
        return response

    adapter.transport = httpx.MockTransport(handler)
    with pytest.raises(OptimizationUnavailable):
        adapter.apply_once(request, ctx, NOW)
    assert not server.posts


def test_campaign_new_child_changes_approved_effect_scope() -> None:
    adapter, server, request, ctx = setup("meta_ads", campaign=True)
    server.extra_child = True
    with pytest.raises(OptimizationUnavailable, match="preflight_changed"):
        adapter.apply_once(request, ctx, NOW)
    assert not server.posts


def test_missing_readback_fields_are_unknown() -> None:
    adapter, server, request, ctx = setup("meta_ads")
    response = adapter.apply_once(request, ctx, NOW)
    del server.meta_child["configured_status"]
    assert adapter.read_back(request, response, ctx, NOW).outcome == "unknown"
