"""Fixed bounded metadata reads; no legacy inventory schema or digest changes."""

import hashlib
import hmac
import json
import re
from collections.abc import Callable
from datetime import datetime
from time import monotonic
from typing import Any

import httpx

from app.collectors.google_native_inventory import (
    GoogleNativeInventory,
    GoogleNativeInventoryContext,
)
from app.collectors.meta_native_inventory import (
    ADSET_STATUSES,
    CAMPAIGN_STATUSES,
    MetaNativeInventory,
)
from app.collectors.native_diagnostics import Inventory, InventoryRequest
from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.social_http import _private_http
from app.planning_catalog.metadata_contracts import MetadataEntityV1, PlanningMetadataV1
from app.publication.contracts import fingerprint


class PlanningMetadataUnavailable(RuntimeError):
    pass


Values = Callable[[InventoryRequest, datetime], dict[str, Any]]


def read_metadata(
    inventory: Inventory,
    transport: httpx.BaseTransport,
    values: Values,
    clock: Callable[[], datetime],
) -> PlanningMetadataV1:
    private = _private_http.set(True)
    try:
        return _read(inventory, transport, values, clock)
    except Exception:
        raise PlanningMetadataUnavailable("planning_metadata_unavailable") from None
    finally:
        _private_http.reset(private)


def _read(
    inventory: Inventory,
    transport: httpx.BaseTransport,
    values: Values,
    clock: Callable[[], datetime],
) -> PlanningMetadataV1:
    req = inventory.request
    source = req.account
    platform = source.account.platform
    advertiser = source.external_advertiser_id
    started, expires, deadline = clock(), inventory.expires_at, monotonic() + 60
    calls, total_bytes = 0, 0

    def current() -> dict[str, Any]:
        nonlocal expires
        now = clock()
        if not started <= now < expires or monotonic() >= deadline:
            raise ValueError("expired")
        context = values(req, now)
        expires = min(expires, context["expires_at"])
        if (
            context["scope"] != source
            or context["request_digest"] != req.digest()
            or not started <= clock() < expires
            or monotonic() >= deadline
        ):
            raise ValueError("changed")
        return context

    def native_id(value: Any) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,32}", value):
            raise ValueError("invalid identifier")
        return value

    def google_id(value: Any, kind: str) -> str:
        if not isinstance(value, str) or not re.fullmatch(
            r"customers/" + advertiser + "/" + kind + r"/[0-9]{1,32}", value
        ):
            raise ValueError("foreign resource")
        return value.rsplit("/", 1)[1]

    entities: list[MetadataEntityV1] = []

    def entity(
        kind: str,
        ident: str,
        parent: str | None,
        name: Any,
        status: Any = None,
        entity_type: Any = None,
    ) -> None:
        if name is not None and not isinstance(name, str):
            raise ValueError("invalid name")
        name_status = "missing" if not name else "over_bound" if len(name) > 160 else "observed"
        entities.append(
            MetadataEntityV1.model_validate(
                dict(
                    kind=kind,
                    reference=dict(
                        platform=platform,
                        advertiser_id=advertiser,
                        entity_id=native_id(ident),
                        parent_campaign_id=parent,
                    ),
                    name=name if name_status == "observed" else None,
                    name_status=name_status,
                    status=status,
                    entity_type=entity_type,
                )
            )
        )
        if len(entities) > 400:
            raise ValueError("capacity")

    def google_rows(query: str) -> list[dict[str, Any]]:
        nonlocal calls
        wire = GoogleOptimizationTransport(transport=transport)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        body: dict[str, Any] = {"query": query}
        for _ in range(10):
            context = GoogleNativeInventoryContext(**current())
            calls += 1
            if calls > 20:
                raise ValueError("capacity")
            data = wire.post(context, "googleAds:search", body)
            current()
            batch = data.get("results", [])
            if not isinstance(batch, list) or any(not isinstance(r, dict) for r in batch):
                raise ValueError("shape")
            rows.extend(batch)
            if len(rows) > 200:
                raise ValueError("capacity")
            token = data.get("nextPageToken")
            if token is None or token == "":
                return rows
            if not isinstance(token, str) or not 1 <= len(token) <= 4096 or token in seen:
                raise ValueError("pagination")
            seen.add(token)
            body["pageToken"] = token
        raise ValueError("pagination")

    with httpx.Client(
        transport=transport,
        timeout=httpx.Timeout(12, connect=5),
        follow_redirects=False,
        trust_env=False,
    ) as client:

        def social_get(edge: str, params: dict[str, str]) -> dict[str, Any]:
            nonlocal calls, total_bytes
            context = current()
            calls += 1
            if calls > 20:
                raise ValueError("capacity")
            token = context["access_token"].get_secret_value()
            if platform == "meta_ads":
                url = "https://graph.facebook.com/v26.0/act_" + advertiser + "/" + edge
                headers = {"Authorization": "Bearer " + token, "Accept-Encoding": "identity"}
                secret = context.get("app_secret")
                if secret is not None:
                    params = dict(
                        params,
                        appsecret_proof=hmac.new(
                            secret.get_secret_value().encode(), token.encode(), hashlib.sha256
                        ).hexdigest(),
                    )
            else:
                url = "https://business-api.tiktok.com/open_api/v1.3/" + edge + "/"
                headers = {"Access-Token": token, "Accept-Encoding": "identity"}
            with client.stream("GET", url, params=params, headers=headers) as response:
                if (
                    response.status_code != 200
                    or response.headers.get("Content-Encoding", "identity") != "identity"
                ):
                    raise ValueError("provider")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    total_bytes += len(chunk)
                    if len(raw) > 1_000_000 or total_bytes > 4_000_000 or monotonic() >= deadline:
                        raise ValueError("capacity")
            current()
            data = json.loads(raw)
            if not isinstance(data, dict) or "error" in data:
                raise ValueError("shape")
            if platform == "tiktok_ads":
                if (
                    type(data.get("code")) is not int
                    or data["code"] != 0
                    or not isinstance(data.get("data"), dict)
                ):
                    raise ValueError("shape")
                return dict(data["data"])
            return data

        if isinstance(inventory, GoogleNativeInventory):
            for row in google_rows(
                "SELECT campaign.resource_name, campaign.name, campaign.status FROM campaign"
            ):
                campaign = row["campaign"]
                entity(
                    "campaign",
                    google_id(campaign["resourceName"], "campaigns"),
                    None,
                    campaign.get("name"),
                    campaign.get("status"),
                )
            for row in google_rows(
                "SELECT ad_group.resource_name, ad_group.name, ad_group.status, "
                "ad_group.type, ad_group.campaign FROM ad_group"
            ):
                google_child = row["adGroup"]
                entity(
                    "adgroup",
                    google_id(google_child["resourceName"], "adGroups"),
                    google_id(google_child["campaign"], "campaigns"),
                    google_child.get("name"),
                    google_child.get("status"),
                    google_child.get("type"),
                )
        else:
            for child in (False, True):
                kind = (
                    "adset"
                    if child and platform == "meta_ads"
                    else "adgroup"
                    if child
                    else "campaign"
                )
                rows: list[dict[str, Any]] = []
                if platform == "meta_ads":
                    params = dict(
                        fields="id,account_id,name" + (",campaign_id" if child else ""),
                        limit="100",
                        effective_status=json.dumps(ADSET_STATUSES if child else CAMPAIGN_STATUSES),
                    )
                    seen_cursors: set[str] = set()
                    for _ in range(10):
                        data = social_get("adsets" if child else "campaigns", params)
                        batch = data.get("data")
                        if not isinstance(batch, list) or any(
                            not isinstance(r, dict) for r in batch
                        ):
                            raise ValueError("shape")
                        rows.extend(batch)
                        if len(rows) > 200:
                            raise ValueError("capacity")
                        paging = data.get("paging", {})
                        if not isinstance(paging, dict):
                            raise ValueError("pagination")
                        if not paging.get("next"):
                            break
                        cursor = paging.get("cursors", {}).get("after")
                        if (
                            not isinstance(cursor, str)
                            or not 1 <= len(cursor) <= 1024
                            or cursor in seen_cursors
                        ):
                            raise ValueError("pagination")
                        seen_cursors.add(cursor)
                        params["after"] = cursor
                    else:
                        raise ValueError("pagination")
                    for row in rows:
                        if row.get("account_id") != advertiser:
                            raise ValueError("foreign")
                        entity(
                            kind,
                            row["id"],
                            native_id(row.get("campaign_id")) if child else None,
                            row.get("name"),
                        )
                else:
                    expected: tuple[int, int] | None = None
                    for page in range(1, 11):
                        fields = ["advertiser_id", "campaign_id", "campaign_name"] + (
                            ["adgroup_id", "adgroup_name"] if child else []
                        )
                        data = social_get(
                            "adgroup/get" if child else "campaign/get",
                            dict(
                                advertiser_id=advertiser,
                                fields=json.dumps(fields),
                                filtering=json.dumps({"primary_status": "STATUS_ALL"}),
                                page=str(page),
                                page_size="100",
                            ),
                        )
                        batch, info = data.get("list"), data.get("page_info")
                        if (
                            not isinstance(batch, list)
                            or len(batch) > 100
                            or any(not isinstance(r, dict) for r in batch)
                            or not isinstance(info, dict)
                            or type(info.get("page")) is not int
                            or info["page"] != page
                            or type(info.get("total_page")) is not int
                            or not 0 <= info["total_page"] <= 10
                            or type(info.get("total_number")) is not int
                            or not 0 <= info["total_number"] <= 200
                        ):
                            raise ValueError("pagination")
                        state = (info["total_page"], info["total_number"])
                        if expected is not None and expected != state:
                            raise ValueError("pagination changed")
                        expected = state
                        rows.extend(batch)
                        if len(rows) > 200:
                            raise ValueError("capacity")
                        if page >= state[0]:
                            if len(rows) != state[1] or (state[0] == 0 and rows):
                                raise ValueError("count")
                            break
                    else:
                        raise ValueError("pagination")
                    for row in rows:
                        if row.get("advertiser_id") != advertiser:
                            raise ValueError("foreign")
                        entity(
                            kind,
                            row["adgroup_id" if child else "campaign_id"],
                            native_id(row.get("campaign_id")) if child else None,
                            row.get("adgroup_name" if child else "campaign_name"),
                        )
    actual: set[tuple[str, str]]
    # Metadata and native settings describe the same exact observed hierarchy.
    if isinstance(inventory, GoogleNativeInventory):
        native_keys = {
            ("campaign", google_id(c.resource_name, "campaigns")) for c in inventory.campaigns
        }
        actual = {(e.kind, e.reference.entity_id) for e in entities if e.kind == "campaign"}
    elif isinstance(inventory, MetaNativeInventory):
        native_keys = {("campaign", c.id) for c in inventory.campaigns} | {
            ("adset", c.id) for c in inventory.adsets
        }
        actual = {(e.kind, e.reference.entity_id) for e in entities}
    else:
        native_keys = {("campaign", c.id) for c in inventory.campaigns} | {
            ("adgroup", c.id) for c in inventory.adgroups
        }
        actual = {(e.kind, e.reference.entity_id) for e in entities}
    if not isinstance(inventory, GoogleNativeInventory):
        native_parents = {
            c.id: c.campaign_id
            for c in (
                inventory.adsets
                if isinstance(inventory, MetaNativeInventory)
                else inventory.adgroups
            )
        }
        if any(
            e.reference.parent_campaign_id != native_parents[e.reference.entity_id]
            for e in entities
            if e.kind != "campaign"
        ):
            raise ValueError("parent changed")
    if native_keys != actual:
        raise ValueError("topology changed")
    current()
    kinds = ["campaign", "adset" if platform == "meta_ads" else "adgroup"]
    return PlanningMetadataV1.model_validate(
        dict(
            workspace_id=source.workspace_id,
            account_id=source.account.account_id,
            connection_id=source.account.connection_id,
            platform=platform,
            connection_version=source.connection_version,
            source_binding_digest=fingerprint(
                "inlet.planning-source.v1", source.model_dump(mode="json")
            ),
            native_inventory_digest=inventory.digest(),
            request_digest=req.digest(),
            reporting_starts_at=req.period_start,
            reporting_ends_at=req.period_end,
            observation_started_at=started,
            observed_at=clock(),
            expires_at=expires,
            entities=entities,
            coverage=[
                dict(
                    kind=k,
                    status="complete" if platform == "google_ads" else "partial",
                    count=sum(e.kind == k for e in entities),
                    scope=("provider_campaigns" if k == "campaign" else "provider_adgroups")
                    if platform == "google_ads"
                    else "sdk_known_effective_statuses"
                    if platform == "meta_ads"
                    else "regular_campaign_families",
                    reasons=[] if platform == "google_ads" else ["native_scope_limited"],
                )
                for k in kinds
            ],
        )
    )
