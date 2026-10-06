"""Injected HTTP only: no provider clients, grants or sockets are used."""

import base64
import hashlib
import json
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from app.executors.meta_publication import MetaPublicationTransport
from app.executors.social_http import SocialPublicationUnavailable
from app.publication.social_compiler import compile_social, materialize_social
from app.publication.social_contracts import (
    ProviderMediaBinding,
    SocialBoundRequest,
    SocialProviderContext,
    SocialProviderReceipt,
    SocialProviderResponse,
    SocialPublicationReview,
    get_social_publication_transport,
)
from pydantic import SecretStr

from tests.test_provider_publication_contracts import NOW
from tests.test_social_publication_contracts import meta_review

RAW = b"offline image fixture: private reader validation is separately required"


class Media:
    def read_verified(self, workspace_id: int, binding: ProviderMediaBinding) -> bytes:
        return RAW


def reviewed() -> SocialPublicationReview:
    data = meta_review().model_dump()
    digest = hashlib.sha256(RAW).hexdigest()
    data["configuration"]["image"].update(sha256=digest, byte_size=len(RAW))
    data["source"]["definition"]["content"]["media"]["sha256"] = digest
    data["source"]["media"][0]["sha256"] = digest
    from app.campaign_review.contracts import ReviewArtifact

    data["source_digest"] = ReviewArtifact.model_validate(data["source"]).fingerprint()
    return SocialPublicationReview.model_validate(data)


def context(r: SocialPublicationReview) -> SocialProviderContext:
    return SocialProviderContext(
        scope=r.scope,
        access_token=SecretStr("offline-token"),
        app_secret=SecretStr("offline-app-secret"),
        expires_at=NOW + timedelta(hours=1),
    )


class MetaServer:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.rows: dict[str, dict[str, Any]] = {}
        self.change: dict[str, Any] = {}
        self.timeout = False
        self.gets = 0

    def __call__(self, req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer offline-token"
        assert req.headers["accept-encoding"] == "identity"
        assert req.url.host == "graph.facebook.com"
        if req.method == "POST":
            assert "appsecret_proof" not in req.url.params
            form = {
                k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()
            }
            assert len(form.pop("appsecret_proof")) == 64
            body: dict[str, Any] = {}
            for key, value in form.items():
                try:
                    body[key] = value if key.endswith("_id") else json.loads(value)
                except ValueError:
                    body[key] = value
            collection = req.url.path.rsplit("/", 1)[1]
            self.posts.append((collection, body))
            if self.timeout:
                raise httpx.ReadTimeout("provider details must not escape")
            if collection == "adimages":
                assert base64.b64decode(body["bytes"]) == RAW
                self.rows["hash"] = {
                    "account_id": "1234567890",
                    "hash": "hash",
                    "original_width": 100,
                    "original_height": 100,
                }
                return httpx.Response(200, json={"images": {"fixture": {"hash": "hash"}}})
            external = str(100 + len(self.posts))
            self.rows[external] = {**body, "id": external, "account_id": "1234567890"}
            if collection == "ads":
                self.rows[external]["creative"] = {"id": body["creative"]["creative_id"]}
            return httpx.Response(200, json={"id": external})
        self.gets += 1
        assert len(req.url.params["appsecret_proof"]) == 64
        if req.url.path.endswith("/adimages"):
            assert json.loads(req.url.params["hashes"]) == ["hash"]
            return httpx.Response(200, json={"data": [{**self.rows["hash"], **self.change}]})
        row = dict(self.rows[req.url.path.rsplit("/", 1)[1]])
        if "object_story_spec" in row:
            assert "degrees_of_freedom_spec" in req.url.params["fields"]
        row.update(self.change)
        return httpx.Response(200, json=row)


def graph(
    server: MetaServer,
) -> tuple[
    MetaPublicationTransport, dict[str, SocialBoundRequest], dict[str, SocialProviderReceipt]
]:
    r = reviewed()
    plan = compile_social(r)
    adapter = MetaPublicationTransport(Media(), transport=httpx.MockTransport(server))
    requests: dict[str, SocialBoundRequest] = {}
    receipts: dict[str, SocialProviderReceipt] = {}
    for step in plan.steps:
        request = materialize_social(
            plan, "a" * 32, step.step_id, receipts, requests, "b" * 32, NOW
        )
        requests[step.step_id] = request
        before = len(server.posts)
        assert adapter.validate_only(request, context(r), NOW).kind == "local_schema"
        assert len(server.posts) == before
        response = adapter.apply_once(request, context(r), NOW)
        receipt = adapter.read_back(request, response, context(r), NOW)
        assert receipt.outcome == "verified_effect", step.step_id
        receipts[step.step_id] = receipt
    return adapter, requests, receipts


def test_meta_full_graph_payloads_and_default_disabled(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="httpx")
    server = MetaServer()
    _, requests, receipts = graph(server)
    assert len(receipts) == 5 and server.gets == 5
    assert get_social_publication_transport() is None
    assert [c for c, _ in server.posts] == ["adimages", "campaigns", "adsets", "adcreatives", "ads"]
    campaign = server.posts[1][1]
    assert campaign == {
        "name": "Review name",
        "status": "PAUSED",
        "objective": "OUTCOME_SALES",
        "buying_type": "AUCTION",
        "special_ad_categories": [],
        "is_adset_budget_sharing_enabled": False,
    }
    adset = server.posts[2][1]
    assert adset["campaign_id"] == "102"
    assert adset["lifetime_budget"] == 20000
    assert adset["status"] == "PAUSED"
    assert adset["promoted_object"] == {"pixel_id": "101", "custom_event_type": "PURCHASE"}
    assert adset["attribution_spec"] == [{"event_type": "CLICK_THROUGH", "window_days": 7}]
    assert adset["targeting"] == {
        "geo_locations": {"countries": ["US"]},
        "locales": [1001],
        "age_min": 18,
        "age_max": 65,
        "publisher_platforms": ["facebook"],
        "facebook_positions": ["feed"],
        "targeting_automation": {"advantage_audience": 0},
    }
    creative = server.posts[3][1]
    assert creative["object_story_spec"] == {
        "page_id": "100",
        "link_data": {
            "link": "https://example.invalid/product",
            "message": "Reviewed text",
            "name": "Reviewed headline",
            "image_hash": "hash",
            "call_to_action": {
                "type": "SHOP_NOW",
                "value": {"link": "https://example.invalid/product"},
            },
        },
    }
    assert server.posts[4][1] == {
        "name": "Review name",
        "status": "PAUSED",
        "adset_id": "103",
        "creative": {"creative_id": "104"},
    }
    assert requests["ad"].resources == {
        "adset": "meta/1234567890/adsets/103",
        "creative": "meta/1234567890/creatives/104",
    }
    assert "offline-token" not in caplog.text and "appsecret_proof" not in caplog.text


@pytest.mark.parametrize(
    "change", [{"status": "ACTIVE"}, {"account_id": "999"}, {"campaign_id": "999"}]
)
def test_meta_wrong_state_owner_or_parent_conflicts(change: dict[str, Any]) -> None:
    server = MetaServer()
    adapter, requests, receipts = graph(server)
    server.change = change
    request = requests["adset"]
    response = SocialProviderResponse(
        request_digest=request.digest(),
        outcome="acknowledged",
        resource_name=receipts["adset"].resource_name,
    )
    assert adapter.read_back(request, response, context(reviewed()), NOW).outcome == "conflict"


def test_lost_acknowledgement_is_unknown_without_retry() -> None:
    server = MetaServer()
    adapter, requests, _ = graph(server)
    server.timeout = True
    request = requests["campaign"]
    response = adapter.apply_once(request, context(reviewed()), NOW)
    assert response.outcome == "unknown"
    count = len(server.posts)
    assert adapter.reconcile(request, [response], context(reviewed()), NOW).outcome == "unknown"
    assert len(server.posts) == count


def test_missing_readback_and_extra_automation_fail_closed() -> None:
    server = MetaServer()
    adapter, requests, receipts = graph(server)
    request = requests["creative"]
    response = SocialProviderResponse(
        request_digest=request.digest(),
        outcome="acknowledged",
        resource_name=receipts["creative"].resource_name,
    )
    server.change = {
        "degrees_of_freedom_spec": {"creative_features_spec": {"enroll_status": "OPT_IN"}}
    }
    assert adapter.read_back(request, response, context(reviewed()), NOW).outcome == "conflict"
    server.change = {}
    del server.rows["104"]["object_story_spec"]
    assert adapter.read_back(request, response, context(reviewed()), NOW).outcome == "unknown"


def test_context_expiry_and_media_tamper_prevent_http() -> None:
    r = reviewed()
    plan = compile_social(r)
    request = materialize_social(plan, "a" * 32, "image", {}, {}, "b" * 32, NOW)
    server = MetaServer()
    adapter = MetaPublicationTransport(Media(), transport=httpx.MockTransport(server))
    with pytest.raises(SocialPublicationUnavailable, match="context_unavailable"):
        adapter.apply_once(request, context(r), NOW + timedelta(hours=2))

    class BadMedia(Media):
        def read_verified(self, workspace_id: int, binding: ProviderMediaBinding) -> bytes:
            return b"tampered"

    adapter = MetaPublicationTransport(BadMedia(), transport=httpx.MockTransport(server))
    with pytest.raises(SocialPublicationUnavailable, match="integrity_failed"):
        adapter.apply_once(request, context(r), NOW)
    assert not server.posts


def tiktok_reviewed() -> SocialPublicationReview:
    from app.campaign_review.contracts import ReviewArtifact

    data = reviewed().model_dump()
    image = data["configuration"]["image"]
    video = {
        **image,
        "media_id": "d" * 32,
        "mime": "video/mp4",
        "duration_ms": 30000,
        "validation_version": "video_v1",
    }
    data["configuration"] = {
        "kind": "tiktok_video_v13",
        "account_timezone": "UTC",
        "currency": "USD",
        "reservation_micros": 200_000_000,
        "lifetime_budget_micros": 200_000_000,
        "currency_decimal_places": 2,
        "budget_semantics": "lifetime_budget_not_independent_hard_cap",
        "activation_policy": "separate_exact_approval",
        "automation_omission_policy": "no_optional_assets_or_automation_requested",
        "objective_type": "WEB_CONVERSIONS",
        "promotion_type": "WEBSITE",
        "campaign_type": "REGULAR_CAMPAIGN",
        "budget_optimize_on": False,
        "campaign_budget_mode": "BUDGET_MODE_TOTAL",
        "adgroup_budget_mode": "BUDGET_MODE_TOTAL",
        "placement_type": "PLACEMENT_TYPE_NORMAL",
        "placements": ["PLACEMENT_TIKTOK"],
        "pixel_id": "101",
        "optimization_event": "SHOPPING",
        "optimization_goal": "CONVERT",
        "billing_event": "OCPM",
        "bid_type": "BID_TYPE_NO_BID",
        "pacing": "PACING_MODE_SMOOTH",
        "schedule_type": "SCHEDULE_START_END",
        "schedule_wire_timezone": "UTC",
        "click_attribution_window": "SEVEN_DAYS",
        "view_attribution_window": "OFF",
        "engaged_view_attribution_window": "OFF",
        "attribution_event_count": "EVERY",
        "location_ids_by_country": {"US": ["6252001"]},
        "language_codes": {"en": "en"},
        "age_groups": ["AGE_18_24", "AGE_25_34"],
        "gender": "GENDER_UNLIMITED",
        "smart_audience_enabled": False,
        "smart_interest_behavior_enabled": False,
        "search_result_enabled": False,
        "comment_disabled": True,
        "share_disabled": True,
        "video_download_disabled": True,
        "identity_type": "CUSTOMIZED_USER",
        "identity_id": "reviewed_identity",
        "creative_material_mode": "CUSTOM",
        "ad_format": "SINGLE_VIDEO",
        "video": video,
        "cover": image,
        "tracking_pixel_id": "101",
        "click_tracking_url": None,
        "impression_tracking_url": None,
    }
    data["scope"]["account"]["platform"] = "tiktok_ads"
    source = data["source"]
    source["definition"]["account"]["platform"] = "tiktok_ads"
    content = source["definition"]["content"]
    content.pop("headline")
    content.update(
        kind="tiktok_website_conversion_video_v1",
        objective="website_conversion",
        media={"media_id": video["media_id"], "sha256": video["sha256"]},
    )
    source["media"] = [content["media"]]
    data["source_digest"] = ReviewArtifact.model_validate(source).fingerprint()
    return SocialPublicationReview.model_validate(data)


class TikTokServer:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.rows: dict[str, dict[str, Any]] = {}
        self.change: dict[str, Any] = {}
        self.timeout = False
        self.gets = 0

    def __call__(self, req: httpx.Request) -> httpx.Response:
        assert req.url.host == "business-api.tiktok.com"
        assert req.headers["Access-Token"] == "offline-token"
        endpoint = req.url.path.removeprefix("/open_api/v1.3/")
        if req.method == "POST":
            if endpoint.endswith("/upload/"):
                from email.parser import BytesParser
                from email.policy import default

                message = BytesParser(policy=default).parsebytes(
                    b"Content-Type: "
                    + req.headers["content-type"].encode()
                    + b"\r\n\r\n"
                    + req.content
                )
                body: dict[str, Any] = {}
                for part in message.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    assert isinstance(name, str)
                    body[name] = part.get_payload(decode=True)
                kind = "video" if "/video/" in endpoint else "image"
                assert body[kind + "_file"] == RAW
                assert (
                    body[kind + "_signature"]
                    == hashlib.md5(RAW, usedforsecurity=False).hexdigest().encode()
                )
                assert body["advertiser_id"] == b"1234567890"
                if kind == "video":
                    assert body["auto_fix_enabled"] == body["auto_bind_enabled"] == b"false"
                external = kind + "_fixture"
                self.rows[external] = {kind + "_id": external, "width": 100, "height": 100}
                if kind == "video":
                    self.rows[external].update(
                        size=len(RAW),
                        duration=30,
                        signature=hashlib.md5(RAW, usedforsecurity=False).hexdigest(),
                        allowed_placements=["PLACEMENT_TIKTOK"],
                        displayable=True,
                    )
                result: dict[str, Any] = {kind + "_id": external}
            else:
                body = json.loads(req.content)
                kind = endpoint.split("/")[0]
                external = str(100 + len(self.posts))
                if kind == "ad":
                    self.rows[external] = {
                        "advertiser_id": body["advertiser_id"],
                        "adgroup_id": body["adgroup_id"],
                        **body["creatives"][0],
                        "ad_id": external,
                    }
                    result = {"ad_ids": [external]}
                else:
                    self.rows[external] = {**body, kind + "_id": external}
                    result = {kind + "_id": external}
            self.posts.append((endpoint, body))
            if self.timeout:
                raise httpx.ReadTimeout("acknowledgement lost")
            return httpx.Response(200, json={"code": 0, "data": result})
        self.gets += 1
        assert req.url.params["advertiser_id"] == "1234567890"
        if endpoint.startswith("file/"):
            kind = endpoint.split("/")[1]
            ids = json.loads(req.url.params[kind + "_ids"])
        else:
            filters = json.loads(req.url.params["filtering"])
            ids = next(iter(filters.values()))
            assert req.url.params["page"] == "1"
        assert len(ids) == 1
        return httpx.Response(
            200, json={"code": 0, "data": {"list": [{**self.rows[ids[0]], **self.change}]}}
        )


def tiktok_graph(
    server: TikTokServer,
) -> tuple[Any, dict[str, SocialBoundRequest], dict[str, SocialProviderReceipt]]:
    from app.executors.tiktok_publication import TikTokPublicationTransport

    r = tiktok_reviewed()
    plan = compile_social(r)
    adapter = TikTokPublicationTransport(Media(), transport=httpx.MockTransport(server))
    requests: dict[str, SocialBoundRequest] = {}
    receipts: dict[str, SocialProviderReceipt] = {}
    for step in plan.steps:
        request = materialize_social(
            plan, "a" * 32, step.step_id, receipts, requests, "b" * 32, NOW
        )
        requests[step.step_id] = request
        response = adapter.apply_once(request, context(r), NOW)
        receipt = adapter.read_back(request, response, context(r), NOW)
        assert receipt.outcome == "verified_effect", step.step_id
        receipts[step.step_id] = receipt
    return adapter, requests, receipts


def test_tiktok_multipart_full_disabled_graph_exact_cover_and_budget() -> None:
    server = TikTokServer()
    _, requests, receipts = tiktok_graph(server)
    assert len(receipts) == 5 and server.gets == 5
    assert [e for e, _ in server.posts] == [
        "file/video/ad/upload/",
        "file/image/ad/upload/",
        "campaign/create/",
        "adgroup/create/",
        "ad/create/",
    ]
    assert server.posts[2][1] == {
        "advertiser_id": "1234567890",
        "campaign_name": "Review name",
        "objective_type": "WEB_CONVERSIONS",
        "campaign_type": "REGULAR_CAMPAIGN",
        "budget_optimize_on": False,
        "budget_mode": "BUDGET_MODE_TOTAL",
        "budget": 200.0,
        "operation_status": "DISABLE",
    }
    group = server.posts[3][1]
    assert group["campaign_id"] == "102" and group["budget"] == 200
    assert group["operation_status"] == "DISABLE" and group["optimization_event"] == "SHOPPING"
    assert group["schedule_start_time"] == NOW.strftime("%Y-%m-%d %H:%M:%S")
    assert group["placement_type"] == "PLACEMENT_TYPE_NORMAL"
    assert group["placements"] == ["PLACEMENT_TIKTOK"] and not group["search_result_enabled"]
    assert group["location_ids"] == ["6252001"] and group["languages"] == ["en"]
    assert server.posts[4][1] == {
        "advertiser_id": "1234567890",
        "adgroup_id": "103",
        "creatives": [
            {
                "ad_name": "Review name",
                "identity_type": "CUSTOMIZED_USER",
                "identity_id": "reviewed_identity",
                "ad_format": "SINGLE_VIDEO",
                "video_id": "video_fixture",
                "image_ids": ["image_fixture"],
                "ad_text": "Reviewed text",
                "call_to_action": "SHOP_NOW",
                "landing_page_url": "https://example.invalid/product",
                "tracking_pixel_id": 101,
                "operation_status": "DISABLE",
            }
        ],
    }
    assert requests["ad"].resources["cover"] == "tiktok/1234567890/images/image_fixture"


@pytest.mark.parametrize(
    "step,change",
    [
        ("video", {"allowed_placements": None}),
        ("video", {"displayable": False}),
        ("video", {"signature": "wrong"}),
        ("cover", {"advertiser_id": "999"}),
        ("adgroup", {"operation_status": "ENABLE"}),
        ("ad", {"image_ids": ["foreign"]}),
        ("ad", {"identity_id": "foreign"}),
        ("ad", {"adgroup_id": "999"}),
    ],
)
def test_tiktok_foreign_or_changed_readback_conflicts(step: str, change: dict[str, Any]) -> None:
    server = TikTokServer()
    adapter, requests, receipts = tiktok_graph(server)
    server.change = change
    request = requests[step]
    response = SocialProviderResponse(
        request_digest=request.digest(),
        outcome="acknowledged",
        resource_name=receipts[step].resource_name,
    )
    assert (
        adapter.read_back(request, response, context(tiktok_reviewed()), NOW).outcome == "conflict"
    )


def test_tiktok_timeout_after_effect_never_retries_or_guesses_absence() -> None:
    server = TikTokServer()
    adapter, requests, _ = tiktok_graph(server)
    server.timeout = True
    request = requests["campaign"]
    response = adapter.apply_once(request, context(tiktok_reviewed()), NOW)
    count = len(server.posts)
    assert response.outcome == "unknown"
    assert (
        adapter.reconcile(request, [response], context(tiktok_reviewed()), NOW).outcome == "unknown"
    )
    assert len(server.posts) == count


@pytest.mark.parametrize("mode", ["redirect", "large", "compressed", "nonobject", "error"])
def test_response_transport_fails_closed_and_does_not_follow(mode: str) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if mode == "redirect":
            return httpx.Response(302, headers={"Location": "https://other.invalid"})
        if mode == "large":
            return httpx.Response(200, content=b" " * 2_000_001)
        if mode == "compressed":
            import gzip

            return httpx.Response(
                200, content=gzip.compress(b"{}"), headers={"Content-Encoding": "gzip"}
            )
        return httpx.Response(200, json=[] if mode == "nonobject" else {"error": "private"})

    r = reviewed()
    request = materialize_social(compile_social(r), "a" * 32, "image", {}, {}, "b" * 32, NOW)
    adapter = MetaPublicationTransport(Media(), transport=httpx.MockTransport(handler))
    assert adapter.apply_once(request, context(r), NOW).outcome == "unknown"
    assert len(calls) == 1


def test_dependency_receipt_cannot_be_forged_from_foreign_attempt() -> None:
    server = MetaServer()
    _, requests, receipts = graph(server)
    plan = compile_social(reviewed())
    foreign = receipts["creative"].model_copy(update={"request_digest": "f" * 64})
    with pytest.raises(ValueError, match="stale or foreign"):
        materialize_social(
            plan, "a" * 32, "ad", {**receipts, "creative": foreign}, requests, "b" * 32, NOW
        )
    with pytest.raises(ValueError, match="verified social dependency"):
        materialize_social(plan, "a" * 32, "ad", {}, requests, "b" * 32, NOW)


def test_reconciliation_known_id_reads_only_and_conflicting_ids_block() -> None:
    server = MetaServer()
    adapter, requests, receipts = graph(server)
    request = requests["ad"]
    known = SocialProviderResponse(
        request_digest=request.digest(),
        outcome="acknowledged",
        resource_name=receipts["ad"].resource_name,
    )
    before = len(server.posts)
    assert (
        adapter.reconcile(request, [known], context(reviewed()), NOW).outcome == "verified_effect"
    )
    other = known.model_copy(update={"resource_name": "meta/1234567890/ads/999"})
    assert (
        adapter.reconcile(request, [known, other], context(reviewed()), NOW).outcome == "conflict"
    )
    assert len(server.posts) == before


def test_foreign_context_is_rejected_before_sending() -> None:
    r = reviewed()
    request = materialize_social(compile_social(r), "a" * 32, "image", {}, {}, "b" * 32, NOW)
    ctx = context(r)
    ctx = ctx.model_copy(update={"scope": ctx.scope.model_copy(update={"connection_version": 999})})
    server = MetaServer()
    adapter = MetaPublicationTransport(Media(), transport=httpx.MockTransport(server))
    with pytest.raises(SocialPublicationUnavailable, match="context_unavailable"):
        adapter.apply_once(request, ctx, NOW)
    assert not server.posts
