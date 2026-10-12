"""Bounded offline TikTok count parsing; no IO, storage or runtime registration."""

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.campaign_performance.presence_contracts import CountCellV1
from app.tiktok.count_contracts import (
    MAX_BODY,
    TikTokCountPageV1,
    TikTokCountProofV1,
    TikTokCountQueryV1,
    TikTokCountRowV1,
)


def _constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_count_page(
    query: TikTokCountQueryV1,
    body: bytes,
    headers: tuple[tuple[str, str], ...],
    *,
    requested_page: int,
    acquired_at: datetime,
) -> TikTokCountPageV1:
    """Envelope binding is an input assertion, not authenticated acquisition proof."""
    try:
        q = TikTokCountQueryV1.model_validate(query)
        if type(body) is not bytes or not 1 <= len(body) <= MAX_BODY:
            raise ValueError("bounded bytes required")
        if type(requested_page) is not int or not 1 <= requested_page <= 100:
            raise ValueError("bounded page required")
        if type(headers) is not tuple or len(headers) > 100:
            raise ValueError("bounded header observations required")
        throttle = False
        size = 0
        for pair in headers:
            if type(pair) is not tuple or len(pair) != 2:
                raise ValueError("header pair required")
            name, value = pair
            if type(name) is not str or type(value) is not str:
                raise ValueError("header text required")
            size += len(name) + len(value)
            if size > 16_384 or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", name):
                raise ValueError("bounded header required")
            if name.lower() == "x-tt-ads-throttle":
                if throttle:
                    raise ValueError("duplicate throttle header")
                throttle = True  # No value vocabulary is source-qualified, including empty/zero.
        raw = json.loads(
            body, object_pairs_hook=_unique, parse_float=Decimal, parse_constant=_constant
        )
        if type(raw) is not dict or type(raw.get("code")) is not int or raw["code"] != 0:
            raise ValueError("successful envelope required")
        data = raw["data"]
        if type(data) is not dict or set(data) != {"list", "page_info"}:
            raise ValueError("exact report data required")
        info = data["page_info"]
        if type(info) is not dict or set(info) != {
            "page",
            "page_size",
            "total_number",
            "total_page",
        }:
            raise ValueError("exact pagination required")
        if info["page"] != requested_page:
            raise ValueError("wrong page")
        rows = data["list"]
        if type(rows) is not list or len(rows) > 100:
            raise ValueError("bounded list required")
        mapping = {c.native_id: c.local_id for c in q.campaigns}
        parsed = []
        for row in rows:
            if type(row) is not dict or set(row) != {"dimensions", "metrics"}:
                raise ValueError("exact row required")
            dims, metrics = row["dimensions"], row["metrics"]
            if type(dims) is not dict or set(dims) != {"campaign_id", "stat_time_day"}:
                raise ValueError("exact campaign/day dimensions required")
            native, day = dims["campaign_id"], dims["stat_time_day"]
            if type(native) is not str or native not in mapping:
                raise ValueError("foreign campaign")
            if type(day) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2} 00:00:00", day):
                raise ValueError("local midnight day required")
            metric_date = date.fromisoformat(day[:10])
            if not q.starts_on <= metric_date <= q.ends_on:
                raise ValueError("out of range date")
            if type(metrics) is not dict or not set(metrics) <= {"complete_payment"}:
                raise ValueError("exact selected metric required")
            missing = "complete_payment" not in metrics or metrics["complete_payment"] == "-"
            count = CountCellV1(
                presence="missing" if missing else "present",
                value=None if missing else metrics["complete_payment"],
            )
            parsed.append(
                TikTokCountRowV1(
                    native_campaign_id=native,
                    campaign_id=mapping[native],
                    metric_date=metric_date,
                    count=count,
                )
            )
        result = TikTokCountPageV1(
            query_digest=q.digest(),
            request_id=raw["request_id"],
            throttle="present_unqualified" if throttle else "absent",
            body_digest=hashlib.sha256(body).hexdigest(),
            acquired_at=acquired_at,
            rows=tuple(parsed),
            **info,
        )
        if not 0 <= (result.acquired_at - q.started_at).total_seconds() < 60:
            raise ValueError("expired acquisition")
        return result
    except (ValueError, TypeError, KeyError, ArithmeticError, RecursionError):
        raise ValueError("tiktok_count_page_unavailable") from None


def assemble_count_proof(
    query: TikTokCountQueryV1, pages: tuple[TikTokCountPageV1, ...]
) -> TikTokCountProofV1:
    return TikTokCountProofV1(
        query=query,
        pages=pages,
        uncapped="warning_present" if any(p.throttle != "absent" for p in pages) else "unknown",
    )
