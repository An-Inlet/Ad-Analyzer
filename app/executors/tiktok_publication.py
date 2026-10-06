"""Concrete TikTok v1.3 manual video adapter; all creates explicitly disabled."""

import hashlib
import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.executors.social_http import (
    SocialHTTP,
    SocialPublicationUnavailable,
    decimal_budget,
    resolved,
)
from app.publication.social_contracts import (
    OUTPUT_KINDS,
    SocialBoundRequest,
    SocialProviderContext,
    SocialProviderReceipt,
    SocialProviderResponse,
    TikTokCreateDisabledAdGroup,
    TikTokCreateDisabledCampaign,
    TikTokCreateDisabledVideoAd,
    TikTokUploadCover,
    TikTokUploadVideo,
    social_resource,
)


class TikTokPublicationTransport(SocialHTTP):
    provider = "tiktok_ads"
    origin = "https://business-api.tiktok.com"

    def prepare(self, request: SocialBoundRequest) -> tuple[str, dict[str, Any]]:
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
        if isinstance(op, TikTokCreateDisabledCampaign):
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
        if isinstance(op, TikTokCreateDisabledAdGroup):
            f = op.configuration
            return "adgroup/create/", {
                **owner,
                "campaign_id": resolved(request, op.campaign),
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
        if isinstance(op, TikTokCreateDisabledVideoAd):
            f, c = op.configuration, op.content
            if int(f.tracking_pixel_id) > 2**63 - 1:
                raise SocialPublicationUnavailable("tiktok_pixel_id_not_representable")
            return "ad/create/", {
                **owner,
                "adgroup_id": resolved(request, op.adgroup),
                "creatives": [
                    {
                        "ad_name": op.name,
                        "identity_type": f.identity_type,
                        "identity_id": f.identity_id,
                        "ad_format": f.ad_format,
                        "video_id": resolved(request, op.video),
                        "image_ids": [resolved(request, op.cover)],
                        "ad_text": c.text,
                        "call_to_action": c.call_to_action,
                        "landing_page_url": c.landing_page,
                        "tracking_pixel_id": int(f.tracking_pixel_id),
                        "operation_status": op.operation_status,
                    }
                ],
            }
        raise SocialPublicationUnavailable("tiktok_publication_operation_unsupported")

    @staticmethod
    def data(value: dict[str, Any]) -> Any:
        if type(value.get("code")) is not int or value["code"] != 0 or "data" not in value:
            raise SocialPublicationUnavailable("social_response_invalid")
        return value["data"]

    def apply_once(
        self, request: SocialBoundRequest, context: SocialProviderContext, now: datetime
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
                    "tiktok_create_disabled_campaign": "campaign_id",
                    "tiktok_create_disabled_adgroup": "adgroup_id",
                    "tiktok_create_disabled_video_ad": "ad_ids",
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
        request: SocialBoundRequest,
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
                request.scope, response.resource_name, OUTPUT_KINDS[request.step.operation.kind]
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
                "tiktok_create_disabled_campaign": "campaign",
                "tiktok_create_disabled_adgroup": "adgroup",
                "tiktok_create_disabled_video_ad": "ad",
            }[op.kind]
            endpoint = kind + "/get/"
            params["filtering"] = json.dumps({kind + "_ids": [external]})
            params.update(page="1", page_size="100")
            if isinstance(op, TikTokCreateDisabledVideoAd):
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
