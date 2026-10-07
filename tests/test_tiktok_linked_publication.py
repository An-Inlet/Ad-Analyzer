"""Actual linked wire calls through MockTransport; no configured runtime admission."""

from datetime import timedelta
from typing import Any, cast

import httpx
import pytest
from app.executors.social_http import SocialPublicationUnavailable
from app.executors.tiktok_linked_publication import LinkedPushTikTokTransport
from app.publication.social_contracts import (
    SocialProviderContext,
    SocialProviderReceipt,
    SocialProviderResponse,
)
from app.publication.tiktok_linked_plan import (
    LinkedPushBoundRequestV1,
    compile_linked_push,
    materialize_linked_push,
)
from pydantic import SecretStr

from tests.test_commerce_measurement import NOW
from tests.test_social_publication_http import Media, TikTokServer
from tests.test_tiktok_linked_plan import linked_review


def graph(
    server: TikTokServer,
) -> tuple[
    LinkedPushTikTokTransport,
    dict[str, LinkedPushBoundRequestV1],
    dict[str, SocialProviderReceipt],
    SocialProviderContext,
]:
    review = linked_review()
    plan = compile_linked_push(review)
    context = SocialProviderContext(
        scope=review.scope,
        access_token=SecretStr("offline-token"),
        expires_at=NOW + timedelta(hours=1),
    )
    adapter = LinkedPushTikTokTransport(Media(), transport=httpx.MockTransport(server))
    requests: dict[str, LinkedPushBoundRequestV1] = {}
    receipts: dict[str, SocialProviderReceipt] = {}
    for step in plan.steps:
        request = materialize_linked_push(
            plan, "a" * 32, step.step_id, receipts, requests, "b" * 32, NOW
        )
        requests[step.step_id] = request
        before = len(server.posts)
        assert adapter.validate_only(request, context, NOW).kind == "local_schema"
        assert len(server.posts) == before
        response = adapter.apply_once(request, context, NOW)
        receipt = adapter.read_back(request, response, context, NOW)
        assert receipt.outcome == "verified_effect", step.step_id
        receipts[step.step_id] = receipt
    return adapter, requests, receipts, context


def test_exact_linked_disabled_graph_does_not_require_post_id_before_review() -> None:
    server = TikTokServer()
    _, requests, receipts, _ = graph(server)
    assert len(server.posts) == len(receipts) == server.gets == 5
    ad = server.posts[-1][1]
    assert set(ad) == {"advertiser_id", "adgroup_id", "creatives"}
    creative = ad["creatives"][0]
    assert creative["identity_type"] == "TT_USER" and creative["identity_id"] == "linked"
    assert creative["video_id"] == "video_fixture" and creative["image_ids"] == ["image_fixture"]
    assert creative["dark_post_status"] == "ON" and creative["operation_status"] == "DISABLE"
    assert creative["creative_authorized"] is False
    assert {"tiktok_item_id", "rights_review_digest", "creative_type"}.isdisjoint(creative)
    assert requests["ad"].review_digest == compile_linked_push(linked_review()).review_digest


@pytest.mark.parametrize(
    "change",
    [
        {"identity_id": "other"},
        {"identity_authorized_bc_id": "foreign-bc"},
        {"video_id": "other"},
        {"dark_post_status": "OFF"},
        {"creative_authorized": 0},
        {"operation_status": "ENABLE"},
    ],
)
def test_exact_readback_conflicts(change: dict[str, Any]) -> None:
    server = TikTokServer()
    adapter, requests, receipts, context = graph(server)
    server.change = change
    request = requests["ad"]
    response = SocialProviderResponse(
        request_digest=request.digest(),
        outcome="acknowledged",
        resource_name=receipts["ad"].resource_name,
    )
    assert adapter.read_back(request, response, context, NOW).outcome == "conflict"


def test_unknown_response_reconciliation_never_replays_and_expired_context_has_no_io() -> None:
    server = TikTokServer()
    adapter, requests, _, context = graph(server)
    request = requests["ad"]
    server.timeout = True
    response = adapter.apply_once(request, context, NOW)
    assert response.outcome == "unknown"
    before = len(server.posts), server.gets
    assert adapter.reconcile(request, [response], context, NOW).outcome == "unknown"
    assert (len(server.posts), server.gets) == before
    with pytest.raises(SocialPublicationUnavailable, match="linked_context_unavailable"):
        adapter.apply_once(request, context, context.expires_at)
    assert (len(server.posts), server.gets) == before


@pytest.mark.parametrize(
    "raw",
    [
        b'{"code":0,"code":1,"data":{"video_id":"x"}}',
        b'{"code":0,"data":{"video_id":"x","other":NaN}}',
        b'{"code":0,"data":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
    ],
    ids=["duplicate", "nonfinite", "deep"],
)
def test_malformed_wire_response_is_sanitized_unknown_without_retry(raw: bytes) -> None:
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(200, content=raw)

    review = linked_review()
    plan = compile_linked_push(review)
    request = materialize_linked_push(plan, "a" * 32, "video", {}, {}, "b" * 32, NOW)
    context = SocialProviderContext(
        scope=review.scope,
        access_token=SecretStr("offline-token"),
        expires_at=NOW + timedelta(hours=1),
    )
    adapter = LinkedPushTikTokTransport(Media(), transport=httpx.MockTransport(respond))
    result = adapter.apply_once(request, context, NOW)
    assert result.outcome == "unknown" and result.resource_name is None
    assert calls == ["POST"]
    assert adapter.reconcile(request, [result], context, NOW).outcome == "unknown"
    assert calls == ["POST"]


def test_real_transport_is_rejected_before_http() -> None:
    class Forbidden(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            pytest.fail("real transport must never be called")

    with pytest.raises(SocialPublicationUnavailable, match="linked_real_transport_unavailable"):
        LinkedPushTikTokTransport(Media(), transport=cast(httpx.MockTransport, Forbidden()))
