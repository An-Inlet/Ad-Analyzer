"""Bounded raw selected-action parser, not an activated Google import or ownership proof."""

import hashlib
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from app.campaign_performance.presence_contracts import Digest, Frozen, Id, NativeId, Positive
from app.campaign_performance.raw_cells import count_cell, exact_json, money_cell
from app.campaign_performance.selected_contracts import (
    SelectedCampaignDayV1,
    SelectedCaptureRequestV1,
    capture_request_digest,
)

PRODUCER = "google.v24.campaign-day.selected-action.v1"


def query_profile_digest(metric_family: Literal["conversions", "all_conversions"]) -> str:
    if metric_family not in {"conversions", "all_conversions"}:
        raise ValueError("unsupported Google metric family")
    # This is a parser profile, not a provider-signed query capability assertion.
    return hashlib.sha256(
        (
            PRODUCER
            + "\x00campaign.id/resourceName;segments.date/conversionAction;metrics."
            + metric_family
            + "/value;no-implicit-zero"
        ).encode("ascii")
    ).hexdigest()


class GoogleSelectedPageV1(Frozen):
    capture_id: Id
    request_digest: Digest
    facts: tuple[SelectedCampaignDayV1, ...] = Field(max_length=10_000)
    following_cursor: Annotated[str, Field(strict=True, max_length=3000)]

    @model_validator(mode="after")
    def exact_request(self) -> "GoogleSelectedPageV1":
        if any(
            (fact.capture_id, fact.request_digest) != (self.capture_id, self.request_digest)
            for fact in self.facts
        ):
            raise ValueError("page fact request mismatch")
        return self


def parse_selected_page(
    raw: bytes,
    request: SelectedCaptureRequestV1,
    campaign_mapping: dict[str, int],
    *,
    requested_cursor: str = "",
) -> GoogleSelectedPageV1:
    """Decode original response bytes, retain only allowlisted exact facts.

    Caller must prove campaign_mapping from owned inventory, current native account
    metadata and action ownership. No raw response, credential or provider error is
    included in raised messages. Empty pagination is not a zero observation.
    """
    try:
        req = SelectedCaptureRequestV1.model_validate(request)
        selection = req.selection
        if (
            selection.scope.platform != "google_ads"
            or selection.api_version != "v24"
            or req.producer_contract != PRODUCER
            or selection.metric_family not in {"conversions", "all_conversions"}
            or selection.native_event_owner_id != selection.scope.native_account_id
        ):
            raise ValueError("unsupported selected profile")
        family: Literal["conversions", "all_conversions"] = (
            "conversions" if selection.metric_family == "conversions" else "all_conversions"
        )
        if req.query_profile_digest != query_profile_digest(family):
            raise ValueError("profile digest mismatch")
        if type(requested_cursor) is not str or len(requested_cursor) > 3000:
            raise ValueError("invalid requested cursor")
        if len(campaign_mapping) > 50_000:
            raise ValueError("campaign mapping bound")
        for native, local in campaign_mapping.items():
            TypeAdapter(NativeId).validate_python(native)
            TypeAdapter(Positive).validate_python(local)
        if len(set(campaign_mapping.values())) != len(campaign_mapping):
            raise ValueError("ambiguous campaign mapping")
        body = exact_json(raw, limit=8_000_000)
        if "error" in body:
            raise ValueError("provider read failed")
        rows = body.get("results", [])
        cursor = body.get("nextPageToken", "")
        if (
            type(rows) is not list
            or len(rows) > 10_000
            or type(cursor) is not str
            or len(cursor) > 3000
            or (cursor and cursor == requested_cursor)
        ):
            raise ValueError("invalid page")
        facts = []
        keys = set()
        digest = capture_request_digest(req)
        count_key = "conversions" if family == "conversions" else "allConversions"
        value_key = "conversionsValue" if family == "conversions" else "allConversionsValue"
        for row in rows:
            if type(row) is not dict:
                raise ValueError("invalid row")
            campaign, segments = row["campaign"], row["segments"]
            native = campaign["id"]
            if (
                campaign["resourceName"]
                != (f"customers/{selection.scope.native_account_id}/campaigns/{native}")
                or segments["conversionAction"] != selection.native_event_id
            ):
                raise ValueError("native binding mismatch")
            metrics = row.get("metrics", {})
            if type(metrics) is not dict:
                raise ValueError("invalid metrics")
            fact = SelectedCampaignDayV1(
                capture_id=req.capture_id,
                request_digest=digest,
                campaign_id=campaign_mapping[native],
                native_campaign_id=native,
                metric_date=segments["date"],
                selected_conversions=count_cell(metrics, count_key),
                selected_value_micros=money_cell(metrics, value_key),
            )
            if not req.requested_starts_on <= fact.metric_date <= req.requested_ends_on:
                raise ValueError("date outside request")
            key = (fact.campaign_id, fact.metric_date)
            if key in keys:
                raise ValueError("duplicate campaign day")
            keys.add(key)
            facts.append(fact)
        return GoogleSelectedPageV1(
            capture_id=req.capture_id,
            request_digest=digest,
            facts=tuple(facts),
            following_cursor=cursor,
        )
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        raise ValueError("google_selected_observation_unavailable") from None
