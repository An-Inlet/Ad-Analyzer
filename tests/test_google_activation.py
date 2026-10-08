import json
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from app.executors.google_activation import GoogleActivationHTTP
from app.executors.google_publication import (
    GooglePublicationHTTP,
    GooglePublicationUnavailable,
)
from app.publication.activation_contracts import (
    ActivationContext,
    ActivationRequest,
    ActivationTarget,
    get_activation_transport,
)
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.google_compiler import compile_google, materialize_google
from app.publication.provider_contracts import BoundProviderRequest, ProviderReceipt
from pydantic import SecretStr

from tests.test_execution_contracts import binding, policy
from tests.test_google_publication_http import context
from tests.test_provider_coordinator import GoogleServer
from tests.test_provider_publication_contracts import NOW, review

pytestmark = [pytest.mark.retained_execution, pytest.mark.usefixtures("retained_execution_engine")]


class Server(GoogleServer):
    def __init__(self) -> None:
        super().__init__()
        self.activations = 0
        self.activation_timeout = False
        self.delay = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "operations" in body and body["operations"][0].get("updateMask") == "status":
            self.activations += 1
            assert body["operations"][0]["updateMask"] == "status"
            update = body["operations"][0]["update"]
            assert set(update) == {"resourceName", "status"} and update["status"] == "ENABLED"
            if not self.delay:
                self.rows[update["resourceName"]].update(update)
            if self.activation_timeout:
                raise httpx.ReadTimeout("mock status acknowledgement lost")
            return httpx.Response(200, json={"results": [{"resourceName": update["resourceName"]}]})
        return super().__call__(request)


def target(
    server: Server, kind: str = "campaign", *, total_budget: bool = False
) -> ActivationRequest:
    from tests.test_google_total_publication import total_review

    plan = compile_google(total_review() if total_budget else review())
    requests: dict[str, BoundProviderRequest] = {}
    receipts: dict[str, ProviderReceipt] = {}
    transport = GooglePublicationHTTP(transport=httpx.MockTransport(server))
    for step in plan.steps:
        request = materialize_google(
            plan, "c" * 32, step.step_id, receipts, requests, uuid4().hex, NOW
        )
        response = transport.apply_once(request, context(request), NOW)
        receipt = transport.read_back(request, response, context(request), NOW)
        assert receipt.outcome == "verified_effect"
        requests[step.step_id], receipts[step.step_id] = request, receipt
        if step.step_id == kind:
            assert receipt.resource_name is not None and receipt.readback_digest is not None
            return ActivationRequest(
                run_id="d" * 32,
                plan_digest="a" * 64,
                review_digest="b" * 64,
                mandate=binding(policy()),
                target=ActivationTarget(
                    source_attempt_id="1" * 32,
                    source_receipt_id="2" * 32,
                    source_receipt_digest=fingerprint("receipt", receipt.model_dump(mode="json")),
                    original_request=request,
                    resource_name=receipt.resource_name,
                    before_readback_digest=receipt.readback_digest,
                    before_status="PAUSED",
                    target_status="ENABLED",
                ),
                fence="e" * 32,
                dispatched_at=NOW,
            )
    raise AssertionError("target not found")


def ctx(request: ActivationRequest) -> ActivationContext:
    return ActivationContext(
        account=ExecutionAccount.from_publication(request.target.original_request.scope),
        access_token=SecretStr("mock-only"),
        expires_at=NOW + timedelta(hours=1),
    )


@pytest.mark.parametrize("kind", ["campaign", "group", "keyword_0", "ad"])
@pytest.mark.parametrize("total_budget", [False, True])
def test_exact_status_only_update_and_full_field_readback(kind: str, total_budget: bool) -> None:
    server = Server()
    request = target(server, kind, total_budget=total_budget)
    adapter = GoogleActivationHTTP(transport=httpx.MockTransport(server))
    assert get_activation_transport() is None
    assert (
        adapter.read_exact(request, ctx(request), "paused", NOW).readback_digest
        == request.target.before_readback_digest
    )
    response = adapter.apply_once(request, ctx(request), NOW)
    from app.publication.activation_contracts import ActivationResponse
    from app.publication.google_execution_completion_contracts import (
        GoogleCapturedActivationResponse,
    )

    assert isinstance(response, GoogleCapturedActivationResponse)
    response.capture.bind(request)
    assert (
        response.model_dump_json()
        == ActivationResponse(
            request_digest=request.digest(), outcome="acknowledged"
        ).model_dump_json()
    )
    receipt = adapter.read_back(request, response, ctx(request), NOW)
    assert (
        receipt.outcome == "verified_target_state"
        and receipt.effective_time_evidence == "unavailable"
    )
    assert server.activations == 1
    assert (
        adapter.reconcile(request, [response], ctx(request), NOW).outcome == "verified_target_state"
    )
    assert server.activations == 1


@pytest.mark.parametrize("delay", [False, True])
def test_timeout_has_no_retry_or_false_no_effect(delay: bool) -> None:
    server = Server()
    request = target(server)
    server.activation_timeout, server.delay = True, delay
    adapter = GoogleActivationHTTP(transport=httpx.MockTransport(server))
    response = adapter.apply_once(request, ctx(request), NOW)
    assert response.outcome == "unknown"
    receipt = adapter.reconcile(request, [response], ctx(request), NOW)
    assert receipt.outcome == ("unknown" if delay else "verified_target_state")
    assert server.activations == 1
    server.rows[request.target.resource_name]["status"] = "ENABLED"
    assert (
        adapter.reconcile(request, [response], ctx(request), NOW).outcome == "verified_target_state"
    )
    assert server.activations == 1


@pytest.mark.parametrize("change", ["configuration", "scope", "expiry", "digest"])
def test_changed_preflight_or_context_never_updates(change: str) -> None:
    server = Server()
    request = target(server)
    context = ctx(request)
    if change == "configuration":
        server.rows[request.target.resource_name]["name"] = "changed outside Inlet"
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
    adapter = GoogleActivationHTTP(transport=httpx.MockTransport(server))
    with pytest.raises(GooglePublicationUnavailable):
        adapter.apply_once(request, context, NOW)
    assert server.activations == 0


@pytest.mark.parametrize("provider", ["meta", "tiktok"])
def test_activation_preserves_actual_social_receipt_namespaces(provider: str) -> None:
    from app.publication.activation_contracts import ACTIVATABLE, ActivationPlan

    from tests.test_social_publication_http import MetaServer, TikTokServer, graph, tiktok_graph

    _, requests, receipts = (
        graph(MetaServer()) if provider == "meta" else tiktok_graph(TikTokServer())
    )
    targets = []
    for step_id, request in reversed(list(requests.items())):
        if request.step.operation.kind not in ACTIVATABLE:
            continue
        receipt = receipts[step_id]
        assert receipt.resource_name is not None and receipt.readback_digest is not None
        targets.append(
            ActivationTarget(
                source_attempt_id="1" * 32,
                source_receipt_id="2" * 32,
                source_receipt_digest="a" * 64,
                original_request=request,
                resource_name=receipt.resource_name,
                before_readback_digest=receipt.readback_digest,
                before_status="PAUSED" if provider == "meta" else "DISABLE",
                target_status="ACTIVE" if provider == "meta" else "ENABLE",
            )
        )
    assert len(targets) == 3
    plan = ActivationPlan(
        account=ExecutionAccount.from_publication(targets[0].original_request.scope),
        parent_run_id=targets[0].original_request.plan_id,
        parent_plan_digest=targets[0].original_request.plan_digest,
        targets=targets,
    )
    assert "/campaigns/" in plan.targets[-1].resource_name
    assert all(t.resource_name == receipts[t.step_id].resource_name for t in plan.targets)
