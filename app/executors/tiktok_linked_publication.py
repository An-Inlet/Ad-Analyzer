"""Linked Push wire adapter; mock-only admission until configured qualification exists."""

import hashlib
import json
from datetime import datetime
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.executors.social_http import (
    SocialPublicationUnavailable,
    _private_http,
    decimal_budget,
    matches,
    missing,
)
from app.publication.contracts import fingerprint
from app.publication.social_contracts import (
    ProviderMediaBinding,
    ProviderMediaReader,
    SocialProviderContext,
    SocialProviderReceipt,
    SocialProviderResponse,
    SocialResourceRef,
    SocialValidationEvidence,
    TikTokUploadCover,
    TikTokUploadVideo,
    social_resource,
)
from app.publication.tiktok_linked_plan import (
    LINKED_OUTPUTS,
    LinkedPushAdGroupV1,
    LinkedPushAdV1,
    LinkedPushBoundRequestV1,
    LinkedPushCampaignV1,
    creative_for,
)
from app.publication.tiktok_linked_wire import creative_body, matches_linked_ad


class LinkedPushTikTokTransport:
    provider = "tiktok_ads"
    origin = "https://business-api.tiktok.com"

    def __init__(self, media: ProviderMediaReader, *, transport: httpx.MockTransport) -> None:
        if not isinstance(transport, httpx.MockTransport):
            raise SocialPublicationUnavailable("linked_real_transport_unavailable")
        self.media = media
        self.transport = transport

    def send(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        form: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> dict[str, Any]:
        # No live transport admission exists for this unqualified linked profile.
        if not isinstance(self.transport, httpx.MockTransport):
            raise SocialPublicationUnavailable("linked_real_transport_unavailable")
        if not path.startswith("/open_api/v1.3/") or any(c in path for c in ("..", ":", "?")):
            raise SocialPublicationUnavailable("linked_path_invalid")

        def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate response key")
                result[key] = value
            return result

        def nonfinite(value: str) -> Any:
            raise ValueError("nonfinite response")

        token = _private_http.set(True)
        deadline = monotonic() + 30
        try:
            with (
                httpx.Client(
                    transport=self.transport, timeout=12, follow_redirects=False
                ) as client,
                client.stream(
                    method,
                    self.origin + path,
                    headers={**headers, "Accept-Encoding": "identity"},
                    params=params,
                    json=body,
                    data=form,
                    files=files,
                ) as response,
            ):
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise ValueError("encoded response")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000 or monotonic() > deadline:
                        raise ValueError("response bound")
                if response.status_code != 200:
                    raise ValueError("response status")
                value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
        except (httpx.HTTPError, ValueError, OSError, RecursionError):
            raise SocialPublicationUnavailable("linked_provider_unavailable") from None
        finally:
            _private_http.reset(token)
        if not isinstance(value, dict) or value.get("error"):
            raise SocialPublicationUnavailable("linked_response_invalid")
        return value

    @staticmethod
    def check(
        request: LinkedPushBoundRequestV1, context: SocialProviderContext, now: datetime
    ) -> LinkedPushBoundRequestV1:
        request = LinkedPushBoundRequestV1.model_validate_json(request.model_dump_json())
        if (
            request.scope != context.scope
            or request.scope.account.platform != "tiktok_ads"
            or now.tzinfo is None
            or not request.dispatched_at <= now < context.expires_at
            or not context.access_token.get_secret_value()
        ):
            raise SocialPublicationUnavailable("linked_context_unavailable")
        return request

    def media_bytes(
        self, request: LinkedPushBoundRequestV1, binding: ProviderMediaBinding
    ) -> bytes:
        try:
            raw = self.media.read_verified(request.scope.workspace_id, binding)
        except Exception:
            raise SocialPublicationUnavailable("linked_media_unavailable") from None
        if (
            not isinstance(raw, bytes)
            or len(raw) != binding.byte_size
            or hashlib.sha256(raw).hexdigest() != binding.sha256
        ):
            raise SocialPublicationUnavailable("linked_media_integrity_failed")
        return raw

    @staticmethod
    def resolved(request: LinkedPushBoundRequestV1, ref: SocialResourceRef) -> str:
        return social_resource(request.scope, request.resources[ref.step_id], ref.kind)

    @staticmethod
    def resource(request: LinkedPushBoundRequestV1, external_id: Any) -> str:
        if not isinstance(external_id, str):
            raise SocialPublicationUnavailable("linked_response_invalid")
        kind = LINKED_OUTPUTS[request.step.operation.kind]
        name = f"tiktok/{request.scope.external_advertiser_id}/{kind}/{external_id}"
        try:
            social_resource(request.scope, name, kind)
        except ValueError:
            raise SocialPublicationUnavailable("linked_response_invalid") from None
        return name

    @staticmethod
    def receipt(
        request: LinkedPushBoundRequestV1,
        now: datetime,
        outcome: str = "unknown",
        resource: str | None = None,
        expected: dict[str, Any] | None = None,
    ) -> SocialProviderReceipt:
        return SocialProviderReceipt.model_validate(
            dict(
                scope=request.scope,
                plan_id=request.plan_id,
                plan_digest=request.plan_digest,
                step_id=request.step.step_id,
                fence=request.fence,
                request_digest=request.digest(),
                outcome=outcome,
                resource_kind=LINKED_OUTPUTS[request.step.operation.kind],
                resource_name=resource,
                readback_digest=fingerprint("inlet.linked-tiktok-readback.v1", expected)
                if expected
                else None,
                evidence={
                    "unknown": "unresolved",
                    "conflict": "mismatch",
                    "verified_effect": "exact_readback",
                }[outcome],
                observed_at=now,
            )
        )

    def verified(
        self,
        request: LinkedPushBoundRequestV1,
        now: datetime,
        resource: str,
        expected: dict[str, Any],
        actual: Any,
    ) -> SocialProviderReceipt:
        if missing(expected, actual):
            return self.receipt(request, now)
        if not matches(expected, actual):
            return self.receipt(request, now, "conflict")
        if isinstance(request.step.operation, LinkedPushAdV1):
            op = request.step.operation
            creative = creative_for(
                request.review, self.resolved(request, op.video), self.resolved(request, op.cover)
            )
            if not matches_linked_ad(creative, actual):
                return self.receipt(request, now, "conflict")
        return self.receipt(request, now, "verified_effect", resource, expected)

    def validate_only(
        self, request: LinkedPushBoundRequestV1, context: SocialProviderContext, now: datetime
    ) -> SocialValidationEvidence:
        request = self.check(request, context, now)
        self.prepare(request)
        return SocialValidationEvidence(
            request_digest=request.digest(), kind="local_schema", valid=True
        )

    def reconcile(
        self,
        request: LinkedPushBoundRequestV1,
        history: list[SocialProviderResponse],
        context: SocialProviderContext,
        now: datetime,
    ) -> SocialProviderReceipt:
        request = self.check(request, context, now)
        if len(history) > 32 or any(value.request_digest != request.digest() for value in history):
            raise SocialPublicationUnavailable("linked_attempt_mismatch")
        names = {value.resource_name for value in history if value.outcome == "acknowledged"}
        if len(names) > 1:
            return self.receipt(request, now, "conflict")
        if len(names) == 1 and None not in names:
            return self.read_back(
                request,
                SocialProviderResponse(
                    request_digest=request.digest(),
                    resource_name=next(iter(names)),
                    outcome="acknowledged",
                ),
                context,
                now,
            )
        return self.receipt(request, now)

    def prepare(self, request: LinkedPushBoundRequestV1) -> tuple[str, dict[str, Any]]:
        op = request.step.operation
        owner = {"advertiser_id": request.scope.external_advertiser_id}
        if isinstance(op, TikTokUploadVideo | TikTokUploadCover):
            binding = op.video if isinstance(op, TikTokUploadVideo) else op.cover
            raw = self.media_bytes(request, binding)
            kind = "video" if isinstance(op, TikTokUploadVideo) else "image"
            body: dict[str, Any] = {
                **owner,
                "upload_type": "UPLOAD_BY_FILE",
                "file_name": binding.sha256,
                kind + "_signature": hashlib.md5(raw, usedforsecurity=False).hexdigest(),
            }
            if kind == "video":
                body.update(auto_fix_enabled=False, auto_bind_enabled=False)
            return f"file/{kind}/ad/upload/", body
        if isinstance(op, LinkedPushCampaignV1):
            f = op.configuration
            return "campaign/create/", {
                **owner,
                "campaign_name": op.name,
                "objective_type": f.objective_type,
                "campaign_type": f.campaign_type,
                "budget_optimize_on": f.budget_optimize_on,
                "budget_mode": f.campaign_budget_mode,
                "budget": decimal_budget(f.lifetime_budget_micros),
                "operation_status": op.operation_status,
            }
        if isinstance(op, LinkedPushAdGroupV1):
            f = op.configuration
            return "adgroup/create/", {
                **owner,
                "campaign_id": self.resolved(request, op.campaign),
                "adgroup_name": op.name,
                "operation_status": op.operation_status,
                "promotion_type": f.promotion_type,
                "budget_mode": f.adgroup_budget_mode,
                "budget": decimal_budget(f.lifetime_budget_micros),
                "placement_type": f.placement_type,
                "placements": f.placements,
                "pixel_id": f.pixel_id,
                "optimization_event": f.optimization_event,
                "optimization_goal": f.optimization_goal,
                "billing_event": f.billing_event,
                "bid_type": f.bid_type,
                "pacing": f.pacing,
                "schedule_type": f.schedule_type,
                "schedule_start_time": op.starts_at.astimezone(
                    ZoneInfo(f.schedule_wire_timezone)
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "schedule_end_time": op.ends_at.astimezone(
                    ZoneInfo(f.schedule_wire_timezone)
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "click_attribution_window": f.click_attribution_window,
                "view_attribution_window": f.view_attribution_window,
                "engaged_view_attribution_window": f.engaged_view_attribution_window,
                "attribution_event_count": f.attribution_event_count,
                "location_ids": sorted(
                    {v for values in f.location_ids_by_country.values() for v in values}
                ),
                "languages": sorted(set(f.language_codes.values())),
                "age_groups": f.age_groups,
                "gender": f.gender,
                "smart_audience_enabled": f.smart_audience_enabled,
                "smart_interest_behavior_enabled": f.smart_interest_behavior_enabled,
                "search_result_enabled": f.search_result_enabled,
                "comment_disabled": f.comment_disabled,
                "share_disabled": f.share_disabled,
                "video_download_disabled": f.video_download_disabled,
                "creative_material_mode": f.creative_material_mode,
            }
        if isinstance(op, LinkedPushAdV1):
            creative = creative_for(
                request.review, self.resolved(request, op.video), self.resolved(request, op.cover)
            )
            return "ad/create/", {
                **owner,
                "adgroup_id": self.resolved(request, op.adgroup),
                "creatives": [creative_body(creative)],
            }
        raise SocialPublicationUnavailable("tiktok_publication_operation_unsupported")

    @staticmethod
    def data(value: dict[str, Any]) -> Any:
        if type(value.get("code")) is not int or value["code"] != 0 or "data" not in value:
            raise SocialPublicationUnavailable("social_response_invalid")
        return value["data"]

    def apply_once(
        self, request: LinkedPushBoundRequestV1, context: SocialProviderContext, now: datetime
    ) -> SocialProviderResponse:
        request = self.check(request, context, now)
        endpoint, body = self.prepare(request)
        path = f"/open_api/{request.api_version}/{endpoint}"
        headers = {"Access-Token": context.access_token.get_secret_value()}
        op = request.step.operation
        try:
            if isinstance(op, TikTokUploadVideo | TikTokUploadCover):
                binding = op.video if isinstance(op, TikTokUploadVideo) else op.cover
                kind = "video" if isinstance(op, TikTokUploadVideo) else "image"
                raw = self.media_bytes(request, binding)
                form = {k: json.dumps(v) if not isinstance(v, str) else v for k, v in body.items()}
                result = self.send(
                    "POST",
                    path,
                    headers,
                    form=form,
                    files={kind + "_file": (binding.sha256, raw, binding.mime)},
                )
                data = self.data(result)
                # Upload variants may wrap a single result, never accept ambiguous batches.
                if isinstance(data, list) and len(data) == 1:
                    data = data[0]
                external = data.get(kind + "_id") if isinstance(data, dict) else None
            else:
                data = self.data(self.send("POST", path, headers, body=body))
                if not isinstance(data, dict):
                    raise SocialPublicationUnavailable("social_response_invalid")
                key = {
                    "tiktok_linked_push_campaign": "campaign_id",
                    "tiktok_linked_push_adgroup": "adgroup_id",
                    "tiktok_linked_push_ad": "ad_ids",
                }[op.kind]
                external = data.get(key)
                if key == "ad_ids":
                    external = (
                        external[0] if isinstance(external, list) and len(external) == 1 else None
                    )
            name = self.resource(request, external)
            return SocialProviderResponse(
                request_digest=request.digest(), resource_name=name, outcome="acknowledged"
            )
        except SocialPublicationUnavailable:
            return SocialProviderResponse(request_digest=request.digest(), outcome="unknown")

    def read_back(
        self,
        request: LinkedPushBoundRequestV1,
        response: SocialProviderResponse,
        context: SocialProviderContext,
        now: datetime,
    ) -> SocialProviderReceipt:
        request = self.check(request, context, now)
        if response.request_digest != request.digest():
            raise SocialPublicationUnavailable("social_attempt_mismatch")
        if response.outcome != "acknowledged" or not response.resource_name:
            return self.receipt(request, now)
        try:
            external = social_resource(
                request.scope, response.resource_name, LINKED_OUTPUTS[request.step.operation.kind]
            )
        except ValueError:
            return self.receipt(request, now, "conflict")
        op = request.step.operation
        _, expected = self.prepare(request)
        params = {"advertiser_id": request.scope.external_advertiser_id}
        if isinstance(op, TikTokUploadVideo | TikTokUploadCover):
            video = isinstance(op, TikTokUploadVideo)
            binding = op.video if isinstance(op, TikTokUploadVideo) else op.cover
            kind = "video" if video else "image"
            endpoint = f"file/{kind}/ad/info/"
            params[kind + "_ids"] = json.dumps([external])
            expected = {kind + "_id": external, "width": binding.width, "height": binding.height}
            if video:
                expected.update(
                    signature=hashlib.md5(
                        self.media_bytes(request, binding), usedforsecurity=False
                    ).hexdigest(),
                    size=binding.byte_size,
                    duration=(binding.duration_ms or 0) / 1000,
                )
        else:
            kind = {
                "tiktok_linked_push_campaign": "campaign",
                "tiktok_linked_push_adgroup": "adgroup",
                "tiktok_linked_push_ad": "ad",
            }[op.kind]
            endpoint = kind + "/get/"
            params["filtering"] = json.dumps({kind + "_ids": [external]})
            params.update(page="1", page_size="100")
            if isinstance(op, LinkedPushAdV1):
                expected = {
                    "advertiser_id": expected["advertiser_id"],
                    "adgroup_id": expected["adgroup_id"],
                    **expected["creatives"][0],
                }
            expected[kind + "_id"] = external
            params["fields"] = json.dumps(sorted(expected))
        try:
            data = self.data(
                self.send(
                    "GET",
                    f"/open_api/{request.api_version}/{endpoint}",
                    {"Access-Token": context.access_token.get_secret_value()},
                    params=params,
                )
            )
            rows = data.get("list") if isinstance(data, dict) else None
            if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
                return self.receipt(request, now)
            actual = rows[0]
            if isinstance(op, TikTokUploadVideo | TikTokUploadCover):
                if (
                    actual.get("advertiser_id", request.scope.external_advertiser_id)
                    != request.scope.external_advertiser_id
                ):
                    return self.receipt(request, now, "conflict")
                if isinstance(op, TikTokUploadVideo) and (
                    not isinstance(actual.get("allowed_placements"), list)
                    or actual.get("displayable") is False
                    or "PLACEMENT_TIKTOK" not in actual.get("allowed_placements", [])
                ):
                    return self.receipt(request, now, "conflict")
            return self.verified(request, now, response.resource_name, expected, actual)
        except SocialPublicationUnavailable:
            return self.receipt(request, now)
