"""Status-only activation with original creation request/receipt identities."""

import json
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from app.executors.meta_activation import MetaActivationHTTP
from app.executors.social_http import SocialPublicationUnavailable
from app.executors.tiktok_activation import TikTokActivationHTTP
from app.publication.activation_contracts import (
    ActivationContext,
    ActivationRequest,
    ActivationTarget,
    get_activation_transport,
)
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from pydantic import SecretStr

from tests.test_execution_contracts import binding, policy
from tests.test_provider_publication_contracts import NOW
from tests.test_social_publication_http import Media, MetaServer, TikTokServer, graph, tiktok_graph

# Retained post-launch provider engines, never deployment write authority.
pytestmark = [pytest.mark.retained_execution, pytest.mark.usefixtures("retained_execution_engine")]


class MetaActivationServer(MetaServer):
    def __init__(self) -> None:
        super().__init__()
        self.activations: list[dict[str, Any]] = []
        self.activation_timeout = False
        self.delay = False
        self.absent = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        external = request.url.path.rsplit("/", 1)[1]
        if request.method == "POST" and external.isdigit():
            body = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            assert len(body.pop("appsecret_proof")) == 64
            assert body == {"status": "ACTIVE"}
            self.activations.append(body)
            if not self.delay:
                self.rows[external].update(body)
            if self.activation_timeout:
                raise httpx.ReadTimeout("lost activation response")
            return httpx.Response(200, json={"success": True})
        if self.absent and request.method == "GET":
            return httpx.Response(200, json={})
        return super().__call__(request)


class TikTokActivationServer(TikTokServer):
    def __init__(self) -> None:
        super().__init__()
        self.activations: list[dict[str, Any]] = []
        self.activation_timeout = False
        self.delay = False
        self.absent = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/status/update/"):
            body = json.loads(request.content)
            kind = request.url.path.split("/")[-4]
            assert body["advertiser_id"] == "1234567890" and body["operation_status"] == "ENABLE"
            assert set(body) == {"advertiser_id", kind + "_ids", "operation_status"} | (
                {"allow_partial_success"} if kind == "adgroup" else set()
            )
            assert len(body[kind + "_ids"]) == 1
            self.activations.append(body)
            if not self.delay:
                self.rows[body[kind + "_ids"][0]]["operation_status"] = "ENABLE"
            if self.activation_timeout:
                raise httpx.ReadTimeout("lost activation response")
            return httpx.Response(200, json={"code": 0, "data": {}})
        if self.absent and request.method == "GET":
            return httpx.Response(200, json={"code": 0, "data": {"list": []}})
        return super().__call__(request)


def target(provider: str, step: str) -> tuple[Any, Any, ActivationRequest, ActivationContext]:
    server: Any = MetaActivationServer() if provider == "meta_ads" else TikTokActivationServer()
    _, requests, receipts = graph(server) if provider == "meta_ads" else tiktok_graph(server)
    original, receipt = requests[step], receipts[step]
    assert receipt.resource_name is not None and receipt.readback_digest is not None
    request = ActivationRequest(
        run_id="d" * 32,
        plan_digest="a" * 64,
        review_digest="b" * 64,
        mandate=binding(policy()),
        target=ActivationTarget(
            source_attempt_id="1" * 32,
            source_receipt_id="2" * 32,
            source_receipt_digest=fingerprint("receipt", receipt.model_dump(mode="json")),
            original_request=original,
            resource_name=receipt.resource_name,
            before_readback_digest=receipt.readback_digest,
            before_status="PAUSED" if provider == "meta_ads" else "DISABLE",
            target_status="ACTIVE" if provider == "meta_ads" else "ENABLE",
        ),
        fence="e" * 32,
        dispatched_at=NOW,
    )
    context = ActivationContext(
        account=ExecutionAccount.from_publication(original.scope),
        access_token=SecretStr("offline-token"),
        app_secret=SecretStr("offline-app-secret"),
        expires_at=NOW + timedelta(hours=1),
    )
    adapter = (MetaActivationHTTP if provider == "meta_ads" else TikTokActivationHTTP)(
        Media(), transport=httpx.MockTransport(server)
    )
    return adapter, server, request, context


@pytest.mark.parametrize(
    "provider,step",
    [
        ("meta_ads", "campaign"),
        ("meta_ads", "adset"),
        ("meta_ads", "ad"),
        ("tiktok_ads", "campaign"),
        ("tiktok_ads", "adgroup"),
        ("tiktok_ads", "ad"),
    ],
)
def test_original_receipt_full_readback_and_status_only_update(provider: str, step: str) -> None:
    adapter, server, request, context = target(provider, step)
    observed = adapter.read_exact(request, context, "paused", NOW)
    assert observed.readback_digest == request.target.before_readback_digest
    assert (
        observed.resource_name == request.target.resource_name
        and observed.provider_compare_and_swap == "unavailable"
    )
    assert get_activation_transport() is None
    response = adapter.apply_once(request, context, NOW)
    assert response.outcome == "acknowledged"
    receipt = adapter.read_back(request, response, context, NOW)
    assert (
        receipt.outcome == "verified_target_state"
        and receipt.effective_time_evidence == "unavailable"
    )
    assert adapter.reconcile(request, [response], context, NOW).outcome == "verified_target_state"
    assert len(server.activations) == 1


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("delay", [False, True])
def test_unknown_activation_never_retries_or_claims_no_effect(provider: str, delay: bool) -> None:
    adapter, server, request, context = target(provider, "campaign")
    server.activation_timeout = True
    server.delay = delay
    response = adapter.apply_once(request, context, NOW)
    assert response.outcome == "unknown"
    receipt = adapter.reconcile(request, [response], context, NOW)
    assert receipt.outcome == ("unknown" if delay else "verified_target_state")
    assert len(server.activations) == 1
    server.absent = True
    assert adapter.reconcile(request, [response], context, NOW).outcome == "unknown"
    assert len(server.activations) == 1


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("change", ["budget", "scope", "expiry", "digest", "parent", "missing"])
def test_stale_or_foreign_activation_never_updates(provider: str, change: str) -> None:
    step = "adset" if provider == "meta_ads" else "adgroup"
    adapter, server, request, context = target(provider, step)
    external = request.target.resource_name.rsplit("/", 1)[1]
    if change == "budget":
        server.rows[external]["lifetime_budget" if provider == "meta_ads" else "budget"] = 999
    elif change == "parent":
        server.rows[external]["campaign_id"] = "999"
    elif change == "missing":
        del server.rows[external]["name" if provider == "meta_ads" else "adgroup_name"]
    elif change == "scope":
        context = context.model_copy(
            update={"account": context.account.model_copy(update={"workspace_id": 999})}
        )
    elif change == "expiry":
        context = context.model_copy(update={"expires_at": NOW})
    else:
        request = request.model_copy(
            update={
                "target": request.target.model_copy(update={"before_readback_digest": "f" * 64})
            }
        )
    with pytest.raises(SocialPublicationUnavailable):
        adapter.apply_once(request, context, NOW)
    assert not server.activations
