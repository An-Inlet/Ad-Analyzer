"""TikTok fixed one-resource ENABLE updates; no retry or delivery-time claim."""

import json
from datetime import datetime
from typing import Any, Literal

import httpx

from app.executors.meta_activation import MetaActivationHTTP
from app.executors.social_http import SocialPublicationUnavailable
from app.executors.tiktok_publication import TikTokPublicationTransport
from app.publication.activation_contracts import (
    ActivationContext,
    ActivationObservation,
    ActivationRequest,
    ActivationResponse,
)
from app.publication.social_contracts import (
    OUTPUT_KINDS,
    ProviderMediaReader,
    TikTokCreateDisabledVideoAd,
    social_resource,
)


class TikTokActivationHTTP(MetaActivationHTTP):
    provider = "tiktok_ads"

    def __init__(
        self, media: ProviderMediaReader, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.http = TikTokPublicationTransport(media, transport=transport)

    def read_exact(
        self,
        request: ActivationRequest,
        context: ActivationContext,
        expected: Literal["paused", "active"],
        now: datetime,
    ) -> ActivationObservation:
        original, converted = self.check(request, context, now)
        external = social_resource(
            original.scope, request.target.resource_name, OUTPUT_KINDS[original.step.operation.kind]
        )
        _, wanted = self.http.prepare(original)
        kind = {
            "tiktok_create_disabled_campaign": "campaign",
            "tiktok_create_disabled_adgroup": "adgroup",
            "tiktok_create_disabled_video_ad": "ad",
        }[original.step.operation.kind]
        if isinstance(original.step.operation, TikTokCreateDisabledVideoAd):
            wanted = {
                "advertiser_id": wanted["advertiser_id"],
                "adgroup_id": wanted["adgroup_id"],
                **wanted["creatives"][0],
            }
        wanted[kind + "_id"] = external
        wanted["operation_status"] = (
            request.target.before_status if expected == "paused" else request.target.target_status
        )
        actual = None
        try:
            raw = self.http.send(
                "GET",
                f"/{'open_api'}/{original.api_version}/{kind}/get/",
                {"Access-Token": converted.access_token.get_secret_value()},
                params={
                    "advertiser_id": original.scope.external_advertiser_id,
                    "filtering": json.dumps(
                        {kind + "_ids": [external], "primary_status": "STATUS_ALL"}
                    ),
                    "fields": json.dumps(sorted(wanted)),
                    "page": "1",
                    "page_size": "100",
                },
            )
            data = TikTokPublicationTransport.data(raw)
            rows = data.get("list") if isinstance(data, dict) else None
            if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict):
                actual = rows[0]
        except SocialPublicationUnavailable:
            pass
        return self.observation(request, expected, wanted, actual, "operation_status", now)

    def apply_once(
        self, request: ActivationRequest, context: ActivationContext, now: datetime
    ) -> ActivationResponse:
        original, converted = self.check(request, context, now)
        observed = self.read_exact(request, context, "paused", now)
        if (
            observed.state != "paused"
            or observed.readback_digest != request.target.before_readback_digest
        ):
            raise SocialPublicationUnavailable("social_activation_preflight_changed")
        external = social_resource(
            original.scope, request.target.resource_name, OUTPUT_KINDS[original.step.operation.kind]
        )
        kind = {
            "tiktok_create_disabled_campaign": "campaign",
            "tiktok_create_disabled_adgroup": "adgroup",
            "tiktok_create_disabled_video_ad": "ad",
        }[original.step.operation.kind]
        body: dict[str, Any] = {
            "advertiser_id": original.scope.external_advertiser_id,
            kind + "_ids": [external],
            "operation_status": request.target.target_status,
        }
        if kind == "adgroup":
            body["allow_partial_success"] = False
        try:
            result = self.http.send(
                "POST",
                f"/open_api/{original.api_version}/{kind}/status/update/",
                {"Access-Token": converted.access_token.get_secret_value()},
                body=body,
            )
            TikTokPublicationTransport.data(result)
            outcome = "acknowledged"
        except SocialPublicationUnavailable:
            outcome = "unknown"
        return ActivationResponse.model_validate(
            {"request_digest": request.digest(), "outcome": outcome}
        )
