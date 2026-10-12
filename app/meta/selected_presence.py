"""Strict Meta standard website-purchase counts; absent data never becomes zero."""

import re
from typing import Annotated

from pydantic import Field, TypeAdapter, model_validator

from app.campaign_performance.presence_contracts import Digest, Frozen, Id, MoneyCellV1, Positive
from app.campaign_performance.raw_cells import count_cell, exact_json
from app.campaign_performance.selected_contracts import (
    SelectedCampaignDayV1,
    SelectedCaptureRequestV1,
    capture_request_digest,
)
from app.meta.selected_profile import EVENT, PROFILE


class MetaSelectedPageV1(Frozen):
    capture_id: Id
    request_digest: Digest
    facts: tuple[SelectedCampaignDayV1, ...] = Field(max_length=100)
    following_cursor: Annotated[str, Field(strict=True, max_length=4096)]

    @model_validator(mode="after")
    def bound(self) -> "MetaSelectedPageV1":
        if any(
            (f.capture_id, f.request_digest) != (self.capture_id, self.request_digest)
            for f in self.facts
        ):
            raise ValueError("page request mismatch")
        return self


def validate_inputs(
    request: SelectedCaptureRequestV1,
    mapping: dict[str, int],
    cursor: str = "",
) -> SelectedCaptureRequestV1:
    req = SelectedCaptureRequestV1.model_validate(request)
    if (
        req.settings is None
        or req.settings.profile != PROFILE
        or type(cursor) is not str
        or len(cursor) > 4096
        or (cursor and re.fullmatch(r"[A-Za-z0-9_=+/-]+", cursor) is None)
        or not re.fullmatch(r"[0-9]{1,32}", req.aggregate.scope.native_account_id)
        or type(mapping) is not dict
        or not 1 <= len(mapping) <= 50_000
    ):
        raise ValueError("unsupported Meta count request")
    for native, local in mapping.items():
        if type(native) is not str or not re.fullmatch(r"[0-9]{1,32}", native):
            raise ValueError("invalid campaign identity")
        TypeAdapter(Positive).validate_python(local)
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("ambiguous campaign mapping")
    return req


def parse_selected_page(
    raw: bytes,
    request: SelectedCaptureRequestV1,
    campaign_mapping: dict[str, int],
    *,
    requested_cursor: str = "",
) -> MetaSelectedPageV1:
    try:
        req = validate_inputs(request, campaign_mapping, requested_cursor)
        body = exact_json(raw, limit=2_000_000)
        if "error" in body or set(body) - {"data", "paging"}:
            raise ValueError("invalid report")
        rows, paging = body["data"], body.get("paging", {})
        if type(rows) is not list or len(rows) > 100 or type(paging) is not dict:
            raise ValueError("invalid page")
        following = paging.get("next")
        if following is not None and (type(following) is not str or len(following) > 16384):
            raise ValueError("invalid pagination")
        cursor = ""
        if following:
            cursors = paging["cursors"]
            if type(cursors) is not dict:
                raise ValueError("invalid cursor")
            cursor = cursors["after"]
            validate_inputs(req, campaign_mapping, cursor)
            if not cursor or cursor == requested_cursor:
                raise ValueError("cursor did not advance")
        facts, keys = [], set()
        digest, scope = capture_request_digest(req), req.aggregate.scope
        for row in rows:
            if type(row) is not dict or set(row) - {
                "account_id",
                "campaign_id",
                "date_start",
                "date_stop",
                "account_currency",
                "actions",
            }:
                raise ValueError("unexpected report grain")
            native = row["campaign_id"]
            if (
                row["account_id"] != scope.native_account_id
                or row["account_currency"] != scope.currency
                or row["date_start"] != row["date_stop"]
            ):
                raise ValueError("report scope mismatch")
            actions = row.get("actions", [])
            if type(actions) is not list or len(actions) > 1000:
                raise ValueError("invalid actions")
            selected, seen = {}, set()
            for item in actions:
                if type(item) is not dict or set(item) - {"action_type", "value"}:
                    raise ValueError("unexpected action context")
                event = item["action_type"]
                if type(event) is not str or not 1 <= len(event) <= 128 or event in seen:
                    raise ValueError("ambiguous action")
                seen.add(event)
                # Validate present numeric cells even when their event is not selected.
                count_cell(item, "value")
                if event == EVENT:
                    selected = item
            fact = SelectedCampaignDayV1(
                capture_id=req.capture_id,
                request_digest=digest,
                campaign_id=campaign_mapping[native],
                native_campaign_id=native,
                metric_date=row["date_start"],
                selected_conversions=count_cell(selected, "value"),
                selected_value_micros=MoneyCellV1(presence="unsupported", value=None),
            )
            key = (fact.campaign_id, fact.metric_date)
            if (
                key in keys
                or not req.requested_starts_on <= fact.metric_date <= req.requested_ends_on
            ):
                raise ValueError("duplicate or out-of-range row")
            keys.add(key)
            facts.append(fact)
        return MetaSelectedPageV1(
            capture_id=req.capture_id,
            request_digest=digest,
            facts=tuple(facts),
            following_cursor=cursor,
        )
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        raise ValueError("meta_selected_observation_unavailable") from None
