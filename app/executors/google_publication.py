"""Actual Google v25 REST serialization, injected IO, no automatic mutation retry.

Not installed in any runtime factory. A transport is not production authority.
All tests use MockTransport; construction opens no connection.
"""

import json
import re
from datetime import datetime
from typing import Any

import httpx

from app.publication.contracts import fingerprint
from app.publication.provider_contracts import (
    BoundProviderRequest,
    GoogleCreateBudget,
    GoogleCreateCampaignCriterion,
    GoogleCreateExactKeyword,
    GoogleCreatePausedAdGroup,
    GoogleCreatePausedCampaign,
    GoogleCreatePausedResponsiveSearchAd,
    GoogleCreateTotalBudget,
    GoogleSetConversionGoal,
    ProviderContext,
    ProviderReceipt,
    ProviderResponse,
    ValidationEvidence,
)


class GooglePublicationUnavailable(RuntimeError):
    """Sanitized error: no token, advertiser, ad copy or raw response escapes."""


def _resource(request: BoundProviderRequest, key: str, collection: str) -> str:
    value = request.resources[key]
    prefix = f"customers/{request.scope.external_advertiser_id}/{collection}/"
    if not value.startswith(prefix) or not re.fullmatch(r"[0-9]+", value[len(prefix) :]):
        raise GooglePublicationUnavailable("google_publication_reference_invalid")
    return value


def serialize(request: BoundProviderRequest) -> tuple[str, str, dict[str, Any]]:
    """Return fixed collection, GAQL resource and one typed create/update operation."""
    request = BoundProviderRequest.model_validate(request.model_dump())
    op = request.step.operation
    if isinstance(op, GoogleCreateTotalBudget):
        return (
            "campaignBudgets",
            "campaign_budget",
            {
                "create": {
                    "totalAmountMicros": str(op.total_amount_micros),
                    "deliveryMethod": op.delivery_method,
                    "period": op.period,
                    "explicitlyShared": op.explicitly_shared,
                }
            },
        )
    if isinstance(op, GoogleCreateBudget):
        return (
            "campaignBudgets",
            "campaign_budget",
            {
                "create": {
                    "amountMicros": str(op.amount_micros),
                    "deliveryMethod": op.delivery_method,
                    "period": op.period,
                    "explicitlyShared": op.explicitly_shared,
                }
            },
        )
    if isinstance(op, GoogleCreatePausedCampaign):
        f = op.configuration
        return (
            "campaigns",
            "campaign",
            {
                "create": {
                    "name": op.name,
                    "status": "PAUSED",
                    "advertisingChannelType": "SEARCH",
                    "campaignBudget": _resource(request, op.budget.step_id, "campaignBudgets"),
                    "manualCpc": {},
                    "startDateTime": op.starts_local,
                    "endDateTime": op.ends_local,
                    "networkSettings": {
                        "targetGoogleSearch": f.google_search,
                        "targetSearchNetwork": f.search_partners,
                        "targetContentNetwork": f.content_network,
                        "targetPartnerSearchNetwork": False,
                    },
                    "geoTargetTypeSetting": {
                        "positiveGeoTargetType": f.positive_geo_target,
                        "negativeGeoTargetType": f.negative_geo_target,
                    },
                    "containsEuPoliticalAdvertising": f.political_advertising,
                    "trackingUrlTemplate": f.tracking_url_template,
                    "finalUrlSuffix": f.final_url_suffix,
                }
            },
        )
    if isinstance(op, GoogleSetConversionGoal):
        campaign = _resource(request, op.campaign.step_id, "campaigns")
        resource = campaign.replace("/campaigns/", "/conversionGoalCampaignConfigs/")
        return (
            "conversionGoalCampaignConfigs",
            "conversion_goal_campaign_config",
            {
                "update": {
                    "resourceName": resource,
                    "goalConfigLevel": "CAMPAIGN",
                    "customConversionGoal": op.custom_conversion_goal,
                },
                "updateMask": "goal_config_level,custom_conversion_goal",
            },
        )
    if isinstance(op, GoogleCreateCampaignCriterion):
        field, resource_field = (
            ("location", "geoTargetConstant")
            if op.target.startswith("geoTargetConstants/")
            else ("language", "languageConstant")
        )
        return (
            "campaignCriteria",
            "campaign_criterion",
            {
                "create": {
                    "campaign": _resource(request, op.campaign.step_id, "campaigns"),
                    "negative": False,
                    field: {resource_field: op.target},
                }
            },
        )
    if isinstance(op, GoogleCreatePausedAdGroup):
        return (
            "adGroups",
            "ad_group",
            {
                "create": {
                    "campaign": _resource(request, op.campaign.step_id, "campaigns"),
                    "name": op.name,
                    "status": "PAUSED",
                    "type": "SEARCH_STANDARD",
                    "cpcBidMicros": str(op.cpc_bid_micros),
                }
            },
        )
    if isinstance(op, GoogleCreateExactKeyword):
        return (
            "adGroupCriteria",
            "ad_group_criterion",
            {
                "create": {
                    "adGroup": _resource(request, op.group.step_id, "adGroups"),
                    "status": "PAUSED",
                    "negative": False,
                    "keyword": {"text": op.text, "matchType": "EXACT"},
                }
            },
        )
    if isinstance(op, GoogleCreatePausedResponsiveSearchAd):
        return (
            "adGroupAds",
            "ad_group_ad",
            {
                "create": {
                    "adGroup": _resource(request, op.group.step_id, "adGroups"),
                    "status": "PAUSED",
                    "ad": {
                        "finalUrls": [op.content.landing_page],
                        "responsiveSearchAd": {
                            "headlines": [{"text": value} for value in op.content.headlines],
                            "descriptions": [{"text": value} for value in op.content.descriptions],
                        },
                    },
                }
            },
        )
    raise GooglePublicationUnavailable("google_publication_operation_unregistered")


def _snake(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _fields(value: dict[str, Any], prefix: str) -> list[str]:
    fields: list[str] = []
    for key, item in value.items():
        path = f"{prefix}.{_snake(key)}"
        if isinstance(item, dict) and item:
            fields.extend(_fields(item, path))
        elif key == "manualCpc":
            # A strategy oneof is queried through its output enum, not message presence.
            fields.append(f"{prefix}.bidding_strategy_type")
        else:
            fields.append(path)
    return fields


def _matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            (key in actual and _matches(value, actual[key]))
            or (key not in actual and (value is False or value == ""))
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(_matches(left, right) for left, right in zip(expected, actual, strict=True))
        )
    return type(actual) is type(expected) and actual == expected


class GooglePublicationHTTP:
    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def _check(
        self, request: BoundProviderRequest, context: ProviderContext, now: datetime
    ) -> None:
        BoundProviderRequest.model_validate(request.model_dump())
        if (
            context.scope != request.scope
            or context.login_customer_id != request.login_customer_id
            or not request.dispatched_at <= now < context.expires_at
            or request.scope.account.platform != "google_ads"
            or not re.fullmatch(r"[0-9]{10}", request.scope.external_advertiser_id)
            or not context.access_token.get_secret_value()
        ):
            raise GooglePublicationUnavailable("google_publication_context_unavailable")

    def _post(
        self,
        request: BoundProviderRequest,
        context: ProviderContext,
        suffix: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        url = (
            f"https://googleads.googleapis.com/v25/customers/"
            f"{request.scope.external_advertiser_id}/{suffix}"
        )
        headers = {"Authorization": f"Bearer {context.access_token.get_secret_value()}"}
        if context.login_customer_id:
            headers["login-customer-id"] = context.login_customer_id
        if context.developer_token:
            headers["developer-token"] = context.developer_token.get_secret_value()
        try:
            with (
                httpx.Client(
                    transport=self.transport,
                    timeout=httpx.Timeout(30, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream("POST", url, headers=headers, json=body) as response,
            ):
                if response.status_code != 200:
                    raise GooglePublicationUnavailable("google_publication_unavailable")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 1_000_000:
                        raise GooglePublicationUnavailable("google_publication_response_bounds")
                result = json.loads(raw)
                if not isinstance(result, dict) or "partialFailureError" in result:
                    raise GooglePublicationUnavailable("google_publication_response_invalid")
                return result
        except (httpx.HTTPError, ValueError, TypeError):
            raise GooglePublicationUnavailable("google_publication_unavailable") from None

    def validate_only(
        self, request: BoundProviderRequest, context: ProviderContext, now: datetime
    ) -> ValidationEvidence:
        self._check(request, context, now)
        collection, _, operation = serialize(request)
        valid = True
        try:
            self._post(
                request,
                context,
                f"{collection}:mutate",
                {
                    "operations": [operation],
                    "validateOnly": True,
                    "partialFailure": False,
                },
            )
        except GooglePublicationUnavailable:
            valid = False
        return ValidationEvidence(request_digest=request.digest(), valid=valid)

    def apply_once(
        self, request: BoundProviderRequest, context: ProviderContext, now: datetime
    ) -> ProviderResponse:
        self._check(request, context, now)
        collection, _, operation = serialize(request)
        try:
            data = self._post(
                request,
                context,
                f"{collection}:mutate",
                {
                    "operations": [operation],
                    "validateOnly": False,
                    "partialFailure": False,
                },
            )
            results = data.get("results")
            if not isinstance(results, list) or len(results) != 1:
                raise GooglePublicationUnavailable("google_publication_receipt_invalid")
            resource = results[0].get("resourceName") if isinstance(results[0], dict) else None
            self._resource_name(request, collection, resource)
            return ProviderResponse(
                request_digest=request.digest(), resource_name=resource, outcome="acknowledged"
            )
        except GooglePublicationUnavailable:
            return ProviderResponse(request_digest=request.digest(), outcome="unknown")

    @staticmethod
    def _resource_name(request: BoundProviderRequest, collection: str, value: Any) -> str:
        prefix = f"customers/{request.scope.external_advertiser_id}/{collection}/"
        suffix = (
            r"[0-9]+~[0-9]+"
            if collection in {"campaignCriteria", "adGroupCriteria", "adGroupAds"}
            else r"[0-9]+"
        )
        if not isinstance(value, str) or not re.fullmatch(re.escape(prefix) + suffix, value):
            raise GooglePublicationUnavailable("google_publication_receipt_invalid")
        return value

    @staticmethod
    def _receipt(
        request: BoundProviderRequest,
        now: datetime,
        outcome: str = "unknown",
        resource: str | None = None,
        readback: dict[str, Any] | None = None,
    ) -> ProviderReceipt:
        return ProviderReceipt.model_validate(
            {
                "scope": request.scope,
                "plan_id": request.plan_id,
                "plan_digest": request.plan_digest,
                "step_id": request.step.step_id,
                "fence": request.fence,
                "request_digest": request.digest(),
                "outcome": outcome,
                "resource_name": resource,
                "readback_digest": fingerprint("google.readback.v25", readback)
                if readback
                else None,
                "evidence": {
                    "verified_effect": "exact_readback",
                    "unknown": "unresolved",
                    "conflict": "mismatch",
                }[outcome],
                "observed_at": now,
            }
        )

    def read_back(
        self,
        request: BoundProviderRequest,
        response: ProviderResponse,
        context: ProviderContext,
        now: datetime,
    ) -> ProviderReceipt:
        self._check(request, context, now)
        collection, table, operation = serialize(request)
        if response.request_digest != request.digest():
            raise GooglePublicationUnavailable("google_publication_attempt_mismatch")
        if response.outcome != "acknowledged" or not response.resource_name:
            return self._receipt(request, now)
        resource = self._resource_name(request, collection, response.resource_name)
        expected = dict(operation.get("create", operation.get("update", {})))
        if "resourceName" in expected and expected["resourceName"] != resource:
            return self._receipt(request, now, "conflict")
        expected["resourceName"] = resource
        if "manualCpc" in expected:
            del expected["manualCpc"]
            expected["biddingStrategyType"] = "MANUAL_CPC"
        fields = _fields(expected, table)
        total = isinstance(request.step.operation, GoogleCreateTotalBudget)
        if total:
            fields.append("campaign_budget.amount_micros")
        query = (
            f"SELECT {', '.join(fields)} FROM {table} "
            f"WHERE {table}.resource_name = '{resource}' LIMIT 2"
        )
        try:
            data = self._post(request, context, "googleAds:search", {"query": query})
            rows = data.get("results", [])
            if data.get("nextPageToken") or not isinstance(rows, list) or len(rows) != 1:
                return self._receipt(request, now)
            key = table.split("_")[0] + "".join(part.title() for part in table.split("_")[1:])
            actual = rows[0].get(key) if isinstance(rows[0], dict) else None
            if total and (
                not isinstance(actual, dict) or actual.get("amountMicros") not in (None, "0", 0)
            ):
                return self._receipt(request, now, "conflict")
            if not _matches(expected, actual):
                return self._receipt(request, now, "conflict")
            return self._receipt(request, now, "verified_effect", resource, expected)
        except GooglePublicationUnavailable:
            return self._receipt(request, now)

    def reconcile(
        self,
        request: BoundProviderRequest,
        history: list[ProviderResponse],
        context: ProviderContext,
        now: datetime,
    ) -> ProviderReceipt:
        self._check(request, context, now)
        if len(history) > 32 or any(item.request_digest != request.digest() for item in history):
            raise GooglePublicationUnavailable("google_publication_attempt_mismatch")
        names = {item.resource_name for item in history if item.outcome == "acknowledged"}
        if len(names) > 1:
            return self._receipt(request, now, "conflict")
        if len(names) == 1 and None not in names:
            return self.read_back(
                request,
                ProviderResponse(
                    request_digest=request.digest(),
                    resource_name=next(iter(names)),
                    outcome="acknowledged",
                ),
                context,
                now,
            )
        # No provider idempotency key / authoritative absent-effect proof is qualified.
        # A timeout without an acknowledged ID must remain unknown; never resend/name-search.
        return self._receipt(request, now)
