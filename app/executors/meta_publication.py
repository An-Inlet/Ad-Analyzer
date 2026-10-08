"""Concrete Meta v26 image publication HTTP adapter, unregistered by default."""

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from app import advertising_capabilities
from app.executors.social_http import SocialHTTP, SocialPublicationUnavailable, resolved
from app.publication.social_contracts import (
    OUTPUT_KINDS,
    MetaCreateImageCreative,
    MetaCreatePausedAd,
    MetaCreatePausedAdSet,
    MetaCreatePausedCampaign,
    MetaUploadImage,
    SocialBoundRequest,
    SocialProviderContext,
    SocialProviderReceipt,
    SocialProviderResponse,
    social_resource,
)


class MetaPublicationTransport(SocialHTTP):
    provider = "meta_ads"
    origin = "https://graph.facebook.com"

    def prepare(self, request: SocialBoundRequest) -> tuple[str, dict[str, Any]]:
        op = request.step.operation
        if isinstance(op, MetaUploadImage):
            return "adimages", {
                "bytes": base64.b64encode(self.media_bytes(request, op.image)).decode()
            }
        if isinstance(op, MetaCreatePausedCampaign):
            f = op.configuration
            return "campaigns", {
                "name": op.name,
                "status": op.status,
                "objective": f.objective,
                "buying_type": f.buying_type,
                "special_ad_categories": f.special_ad_categories,
                "is_adset_budget_sharing_enabled": f.is_adset_budget_sharing_enabled,
            }
        if isinstance(op, MetaCreatePausedAdSet):
            f = op.configuration
            body: dict[str, Any] = {
                "name": op.name,
                "campaign_id": resolved(request, op.campaign),
                "status": op.status,
                "lifetime_budget": f.adset_lifetime_budget_micros
                // (10 ** (6 - f.currency_minor_unit_exponent)),
                "start_time": op.starts_at.isoformat(),
                "end_time": op.ends_at.isoformat(),
                "bid_strategy": f.bid_strategy,
                "optimization_goal": f.optimization_goal,
                "billing_event": f.billing_event,
                "destination_type": f.destination_type,
                "promoted_object": {
                    "pixel_id": f.pixel_id,
                    "custom_event_type": f.conversion_event,
                },
                "attribution_spec": [v.model_dump() for v in f.attribution],
                "attribution_count_type": f.attribution_count_type,
                "is_dynamic_creative": f.dynamic_creative,
                "targeting": {
                    "geo_locations": {"countries": sorted(f.countries)},
                    "locales": sorted(f.language_locale_ids.values()),
                    "age_min": f.age_min,
                    "age_max": f.age_max,
                    "publisher_platforms": f.publisher_platforms,
                    "facebook_positions": f.facebook_positions,
                    "targeting_automation": {"advantage_audience": f.advantage_audience},
                },
            }
            if f.dsa_beneficiary is not None:
                body["dsa_beneficiary"] = f.dsa_beneficiary
            if f.dsa_payor is not None:
                body["dsa_payor"] = f.dsa_payor
            return "adsets", body
        if isinstance(op, MetaCreateImageCreative):
            f, c = op.configuration, op.content
            return "adcreatives", {
                "name": op.name,
                "url_tags": f.url_tags,
                "object_story_spec": {
                    "page_id": f.page_id,
                    "link_data": {
                        "link": c.landing_page,
                        "message": c.text,
                        "name": c.headline,
                        "image_hash": resolved(request, op.image),
                        "call_to_action": {
                            "type": c.call_to_action,
                            "value": {"link": c.landing_page},
                        },
                    },
                },
            }
        if isinstance(op, MetaCreatePausedAd):
            return "ads", {
                "name": op.name,
                "status": op.status,
                "adset_id": resolved(request, op.adset),
                "creative": {"creative_id": resolved(request, op.creative)},
            }
        raise SocialPublicationUnavailable("meta_publication_operation_unsupported")

    @staticmethod
    def auth(context: SocialProviderContext) -> tuple[dict[str, str], dict[str, str]]:
        token = context.access_token.get_secret_value()
        params = {}
        if context.app_secret:
            params["appsecret_proof"] = hmac.new(
                context.app_secret.get_secret_value().encode(), token.encode(), hashlib.sha256
            ).hexdigest()
        return {"Authorization": "Bearer " + token}, params

    def apply_once(
        self, request: SocialBoundRequest, context: SocialProviderContext, now: datetime
    ) -> SocialProviderResponse:
        advertising_capabilities.require_advertising_write()
        request = self.check(request, context, now)
        collection, body = self.prepare(request)
        headers, proof = self.auth(context)
        # Graph expects JSON-encoded nested form fields. Never inherit SDK create defaults.
        form = {
            k: json.dumps(v, separators=(",", ":")) if not isinstance(v, str) else v
            for k, v in body.items()
        }
        form.update(proof)
        try:
            data = self.send(
                "POST",
                f"/{request.api_version}/act_{request.scope.external_advertiser_id}/{collection}",
                headers,
                form=form,
            )
            if isinstance(request.step.operation, MetaUploadImage):
                images = data.get("images")
                if not isinstance(images, dict) or len(images) != 1:
                    raise SocialPublicationUnavailable("social_response_invalid")
                item = next(iter(images.values()))
                external = item.get("hash") if isinstance(item, dict) else None
            else:
                external = data.get("id")
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
        headers, params = self.auth(context)
        if isinstance(op, MetaUploadImage):
            expected = {
                "account_id": request.scope.external_advertiser_id,
                "hash": external,
                "original_width": op.image.width,
                "original_height": op.image.height,
            }
            path = f"/{request.api_version}/act_{request.scope.external_advertiser_id}/adimages"
            params["hashes"] = json.dumps([external])
        else:
            expected.update(id=external, account_id=request.scope.external_advertiser_id)
            path = f"/{request.api_version}/{external}"
            if isinstance(op, MetaCreatePausedAd):
                expected["creative"] = {"id": resolved(request, op.creative)}
        fields = list(expected)
        if isinstance(op, MetaCreateImageCreative):
            fields.extend(["asset_feed_spec", "degrees_of_freedom_spec", "generative_asset_spec"])
        params["fields"] = ",".join(fields)
        try:
            actual = self.send("GET", path, headers, params=params)
            if isinstance(op, MetaUploadImage):
                rows = actual.get("data")
                if not isinstance(rows, list) or len(rows) != 1:
                    return self.receipt(request, now)
                actual = rows[0]
            # Graph may normalize timestamps to a different UTC offset spelling.
            if isinstance(actual, dict) and isinstance(op, MetaCreatePausedAdSet):
                actual = dict(actual)
                for key in ("start_time", "end_time"):
                    if isinstance(actual.get(key), str):
                        try:
                            observed = datetime.fromisoformat(actual[key])
                            wanted = datetime.fromisoformat(expected[key])
                            if observed.tzinfo is not None and observed == wanted:
                                actual[key] = expected[key]
                        except ValueError:
                            pass
            if isinstance(actual, dict) and isinstance(op, MetaCreateImageCreative):
                # Unexpected provider automation is never silently treated as reviewed.
                for key in ("asset_feed_spec", "degrees_of_freedom_spec", "generative_asset_spec"):
                    if actual.get(key) not in (None, {}):
                        return self.receipt(request, now, "conflict")
            return self.verified(request, now, response.resource_name, expected, actual)
        except SocialPublicationUnavailable:
            return self.receipt(request, now)
