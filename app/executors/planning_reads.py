"""Narrow semantic reads at retained executor HTTP boundaries; no write override."""

import re
from collections.abc import Mapping
from typing import Any

from app import advertising_capabilities


def google_read(endpoint: str, body: Mapping[str, Any]) -> None:
    if (
        endpoint not in {"googleAds:search", "googleAds:searchStream"}
        or not set(body)
        <= {"query", "pageToken", "pageSize", "returnTotalResults", "summaryRowSetting"}
        or not isinstance(body.get("query"), str)
    ):
        advertising_capabilities.require_advertising_write()


def social_read(
    provider: str,
    method: str,
    path: str,
    *,
    headers: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
    body: object = None,
    form: object = None,
    files: object = None,
) -> None:
    # Reject method-override headers and unknown query keys, even on a GET path.
    override = any("method" in key.lower().replace("-", "_") for key in (headers or {}))
    allowed_params = (
        {"fields", "limit", "after", "before", "hashes", "appsecret_proof", "effective_status"}
        if provider == "meta_ads"
        else {
            "advertiser_id",
            "advertiser_ids",
            "fields",
            "filtering",
            "page",
            "page_size",
            "video_ids",
            "image_ids",
        }
    )
    allowed_path = (
        re.fullmatch(r"/v26\.0/(?:[0-9]+(?:/adsets)?|act_[0-9]+(?:/adimages)?)", path)
        if provider == "meta_ads"
        else re.fullmatch(
            r"/open_api/v1\.3/(?:(?:campaign|adgroup|ad)/get/|advertiser/info/|file/(?:image|video)/ad/info/)",
            path,
        )
        if provider == "tiktok_ads"
        else None
    )
    if (
        method != "GET"
        or allowed_path is None
        or override
        or not set(params or {}) <= allowed_params
        or body is not None
        or form is not None
        or files is not None
    ):
        advertising_capabilities.require_advertising_write()
