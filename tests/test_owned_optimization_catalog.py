"""Actual inventory/name/admission/state HTTP composition; no runtime or DB mocks."""

import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.production_runtime.optimization_catalog import (
    OwnedOptimizationCatalogHTTP,
    OwnedOptimizationCatalogUnavailable,
)
from app.production_runtime.optimization_contracts import OwnedOptimizationInventoryRequestV1
from app.publication.customer_optimization_contracts import TargetRequest
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import MoneyContext, OptimizationContext
from app.publication.optimization_execution_contracts import OptimizationQualification
from pydantic import SecretStr

from tests.test_google_optimization_http import Server as GoogleServer
from tests.test_provider_publication_contracts import NOW
from tests.test_social_optimization_http import Server as MetaServer


class Wire:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.google, self.meta = GoogleServer(), MetaServer("meta_ads")
        self.meta.meta_campaign.update(daily_budget="5000", name="Summer Essentials")
        self.meta.meta_child.update(daily_budget="0")
        self.google.campaign["name"] = "Summer Essentials"
        self.calls: list[httpx.Request] = []
        self.mode = "normal"

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        if self.provider == "google_ads":
            query = json.loads(req.content)["query"]
            if "metrics.cost_micros" in query:
                return httpx.Response(200, json={"results": []})
            if "FROM account_budget" in query or "FROM billing_setup" in query:
                return httpx.Response(200, json={"results": []})
            if "SELECT campaign.id, campaign.name" in query:
                return httpx.Response(200, json={"results": [{"campaign": self.google.campaign}]})
            if "WHERE campaign.status IN" in query:
                rows = [{"campaign": self.google.campaign}]
                if self.mode == "overflow":
                    rows = [
                        {
                            "campaign": {
                                **self.google.campaign,
                                "resourceName": f"customers/1234567890/campaigns/{i}",
                            }
                        }
                        for i in range(51)
                    ]
                result: dict[str, Any] = {"results": rows}
                if self.mode == "cycle":
                    result["nextPageToken"] = "same"
                if self.mode == "page" and "pageToken" not in json.loads(req.content):
                    result = {"results": [], "nextPageToken": "next"}
                return httpx.Response(200, json=result)
            return self.google(req)
        path = req.url.path
        if path == "/v26.0/act_123/campaigns":
            result = {"data": [self.meta.meta_campaign]}
            if self.mode == "cycle":
                result["paging"] = {"next": "opaque", "cursors": {"after": "same"}}
            if self.mode == "page" and "after" not in req.url.params:
                result = {"data": [], "paging": {"next": "opaque", "cursors": {"after": "next"}}}
            return httpx.Response(200, json=result)
        if path == "/v26.0/act_123/adsets":
            return httpx.Response(200, json={"data": [self.meta.meta_child]})
        return self.meta(req)


def setup(provider: str, mode: str = "normal") -> tuple[Any, ...]:
    wire = Wire(provider)
    wire.mode = mode
    scope = ExecutionAccount(
        workspace_id=1,
        account={"platform": provider, "account_id": 2, "connection_id": 3},
        external_advertiser_id="1234567890" if provider == "google_ads" else "123",
        connection_version="owned-generation-1",
    )
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=NOW,
        period_end=NOW + timedelta(days=1),
    )
    request = OwnedOptimizationInventoryRequestV1(
        request=TargetRequest(goal_id="a" * 32, goal_revision=1, goal_digest="b" * 64, scope=scope),
        money=money,
        period_basis="confirmed_goal",
        original_mandate=None,
    )
    calls: list[Any] = []
    current: dict[str, Any] = {"valid": True, "now": NOW}

    def context(account: ExecutionAccount) -> OptimizationContext:
        if not current["valid"]:
            raise ValueError("private reconnect details")
        return OptimizationContext(
            scope=account,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(minutes=3),
        )

    def admission(req: Any, candidate: Any, now: Any) -> OptimizationQualification | None:
        calls.append(candidate)
        assert candidate.request_digest == req.digest()
        if mode == "unqualified":
            return None
        if mode == "revoked":
            current["valid"] = False
        if mode == "topology":
            if provider == "google_ads":
                wire.google.hidden_owner = True
            else:
                wire.meta.extra_child = True
        if mode == "elapsed":
            current["now"] = NOW + timedelta(minutes=4)
        return OptimizationQualification(
            environment="live" if mode == "foreign" else "contract_test",
            scope=req.request.scope,
            target=candidate.target,
            money=req.money.model_copy(
                update={"period_end": req.money.period_end + timedelta(days=1)}
            )
            if mode == "money"
            else req.money,
            qualification_id="c" * 32,
            qualification_revision=1,
            profile="explicit_fixture",
            allowed_operations=[
                "google_budget_set_v1" if provider == "google_ads" else "meta_budget_set_v1"
            ],
            observed_at=now,
            expires_at=NOW + timedelta(minutes=2),
            evidence_digest="d" * 64,
            unresolved=["missing_fact"] if mode == "unresolved" else [],
        )

    reader = OwnedOptimizationCatalogHTTP(
        context,
        admission,
        environment="contract_test",
        transport=httpx.MockTransport(wire),
        clock=lambda: current["now"],
    )
    return reader, request, wire, calls


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
def test_actual_inventory_admission_state_and_opaque_named_provenance(provider: str) -> None:
    reader, request, wire, admissions = setup(provider)
    result = reader.read(request, NOW)
    assert len(result.catalog.options) == len(result.admitted) == len(admissions) == 1
    option = result.catalog.options[0]
    assert option.label == "Summer Essentials"
    assert result.admitted[0].option_id == option.identifier(request.request)
    assert result.admitted[0].state_digest == option.state.digest()
    assert option.state.money == request.money
    assert not wire.google.writes and not wire.meta.posts


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
@pytest.mark.parametrize(
    "mode", ["foreign", "revoked", "topology", "elapsed", "cycle", "money", "unresolved"]
)
def test_scope_time_admission_topology_or_incomplete_never_returns_partial(
    provider: str, mode: str
) -> None:
    reader, request, wire, admissions = setup(provider, mode)
    with pytest.raises(
        OwnedOptimizationCatalogUnavailable, match="^optimization_catalog_unavailable$"
    ):
        reader.read(request, NOW)
    assert len(admissions) == (0 if mode == "cycle" else 1)
    assert not wire.google.writes and not wire.meta.posts


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
def test_unqualified_inventory_does_not_read_authorized_state(provider: str) -> None:
    reader, request, wire, calls = setup(provider, "unqualified")
    result = reader.read(request, NOW)
    assert calls and not result.catalog.options and not result.admitted
    assert result.exclusions == (("unqualified", 1),)
    assert not any("recommendation_subscription" in req.content.decode() for req in wire.calls)


def test_overflow_fails_without_admitting_first_fifty() -> None:
    reader, request, _, calls = setup("google_ads", "overflow")
    with pytest.raises(OwnedOptimizationCatalogUnavailable):
        reader.read(request, NOW)
    assert calls == []


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
def test_terminal_pagination_uses_real_inventory(provider: str) -> None:
    reader, request, wire, calls = setup(provider, "page")
    result = reader.read(request, NOW)
    assert len(result.catalog.options) == len(calls) == 1
    assert any(
        "pageToken" in req.content.decode() or "after" in req.url.params for req in wire.calls
    )


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
def test_missing_native_label_excluded_without_invented_identity(provider: str) -> None:
    reader, request, wire, calls = setup(provider)
    (wire.google.campaign if provider == "google_ads" else wire.meta.meta_campaign).pop("name")
    result = reader.read(request, NOW)
    assert not calls and not result.catalog.options
    assert result.exclusions == (("label_unavailable", 1),)


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
def test_unsupported_owner_is_excluded_before_admission(provider: str) -> None:
    reader, request, wire, calls = setup(provider)
    if provider == "google_ads":
        wire.google.campaign["advertisingChannelType"] = "SHOPPING"
    else:
        wire.meta.meta_campaign["is_adset_budget_sharing_enabled"] = True
    result = reader.read(request, NOW)
    assert not calls and not result.catalog.options
    assert result.exclusions == (("unsupported_owner", 1),)
