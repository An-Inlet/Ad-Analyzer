"""Bounded actual TikTok HTTP diagnostics; no real provider traffic."""

import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.collectors.tiktok_native_inventory import (
    TikTokInventoryRequest,
    TikTokNativeInventory,
    TikTokNativeInventoryContext,
    TikTokNativeInventoryHTTP,
    TikTokNativeInventoryRequest,
    TikTokNativeInventoryUnavailable,
)
from pydantic import SecretStr, ValidationError

from tests.test_meta_native_inventory import NOW, PRIVATE
from tests.test_meta_native_inventory import request as meta_request


def request() -> TikTokNativeInventoryRequest:
    raw = meta_request().model_dump()
    raw["account"]["account"]["platform"] = "tiktok_ads"
    raw["account"]["connection_version"] = "tiktok:abc:1"
    return TikTokNativeInventoryRequest.model_validate(raw)


def context(req: TikTokInventoryRequest, now: Any) -> TikTokNativeInventoryContext:
    return TikTokNativeInventoryContext(
        scope=req.account,
        request_digest=req.digest(),
        access_token=SecretStr(PRIVATE),
        expires_at=NOW + timedelta(hours=1),
    )


class Server:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.mode: str | None = None
        self.budget: Any = 12.34

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        assert req.method == "GET" and req.url.host == "business-api.tiktok.com"
        assert req.headers["Access-Token"] == PRIVATE
        assert req.extensions["timeout"] == dict(connect=5, read=12, write=12, pool=12)
        assert PRIVATE not in str(req.url)
        if self.mode == "timeout":
            raise httpx.ReadTimeout(PRIVATE)
        if self.mode == "redirect":
            return httpx.Response(302, headers={"location": "https://example.invalid/" + PRIVATE})
        if self.mode == "oversize":
            return httpx.Response(200, content=b"x" * 1_000_001)
        if self.mode == "error":
            return httpx.Response(200, json={"code": 40000, "message": PRIVATE})
        if req.url.path.endswith("advertiser/info/"):
            assert json.loads(req.url.params["advertiser_ids"]) == ["123"]
            data: dict[str, Any] = {
                "list": [
                    dict(
                        advertiser_id="123", currency="USD", timezone="UTC", status="STATUS_ENABLE"
                    )
                ]
            }
            if self.mode == "foreign_account":
                data["list"][0]["advertiser_id"] = "999"
        else:
            assert req.url.params["advertiser_id"] == "123"
            assert json.loads(req.url.params["filtering"]) == {"primary_status": "STATUS_ALL"}
            child = req.url.path.endswith("adgroup/get/")
            assert child or req.url.path.endswith("campaign/get/")
            page = int(req.url.params["page"])
            row: dict[str, Any] = dict(
                advertiser_id="123",
                campaign_id="5",
                operation_status="ENABLE",
                budget=self.budget,
                budget_mode="BUDGET_MODE_DAY",
            )
            if child:
                row.update(
                    adgroup_id="6",
                    schedule_type="SCHEDULE_START_END",
                    schedule_start_time="2026-10-01 00:00:00",
                )
            if self.mode == "foreign_child" and child:
                row["advertiser_id"] = "999"
            if self.mode == "missing_parent" and child:
                row["campaign_id"] = "999"
            pages = (
                2
                if self.mode in {"page", "duplicate", "changed_pages", "hidden_foreign"}
                and not child
                else 1
            )
            if page == 2:
                if self.mode != "duplicate":
                    row["campaign_id"] = "7"
                if self.mode == "changed_pages":
                    pages = 3
                if self.mode == "hidden_foreign":
                    row["advertiser_id"] = "999"
            data = {
                "list": [row],
                "page_info": dict(page=page, total_page=pages, total_number=pages),
            }
            if self.mode == "wrong_count":
                data["page_info"]["total_number"] = 2
            if self.mode == "invalid_page":
                data["page_info"]["page"] = True
            if self.mode == "too_many_pages":
                data["page_info"]["total_page"] = 11
            if self.mode == "empty":
                data = {"list": [], "page_info": dict(page=1, total_page=0, total_number=0)}
            if self.mode == "empty_unknown":
                data = {"list": [], "page_info": dict(page=1, total_page=0)}
            if self.mode == "absent_budget":
                del row["budget"]
        return httpx.Response(200, json={"code": 0, "data": data})


def read(server: Server, resolver: Any = context) -> TikTokNativeInventory:
    return TikTokNativeInventoryHTTP(
        resolver, clock=lambda: NOW, transport=httpx.MockTransport(server)
    )(request(), NOW)


def test_whole_regular_inventory_preserves_decimal_and_missing_authority() -> None:
    server = Server()
    server.mode = "page"
    result = read(server)
    assert [c.id for c in result.campaigns] == ["5", "7"]
    assert result.adgroups[0].budget_native == "12.34"
    assert result.adgroups[0].budget_optimize_on is None
    assert result.regular_inventory_read_complete and not result.all_campaign_families_complete
    assert (
        result.account_cap
        is result.original_request_terminality
        is result.reporting_watermark
        is None
    )
    assert (
        result.unreported_upper_micros
        is result.unchanged_future_upper_micros
        is result.proposed_owner_upper_micros
        is None
    )
    assert result.unit_semantics == "native_decimal_unqualified" and len(result.digest()) == 64
    assert PRIVATE not in result.model_dump_json()


@pytest.mark.parametrize(
    "mode",
    [
        "timeout",
        "redirect",
        "oversize",
        "error",
        "foreign_account",
        "foreign_child",
        "missing_parent",
        "duplicate",
        "changed_pages",
        "hidden_foreign",
        "wrong_count",
        "invalid_page",
        "too_many_pages",
        "empty_unknown",
    ],
)
def test_private_invalid_or_incomplete_reads_fail(
    mode: str, caplog: pytest.LogCaptureFixture
) -> None:
    server = Server()
    server.mode = mode
    with pytest.raises(TikTokNativeInventoryUnavailable) as error:
        read(server)
    assert PRIVATE not in str(error.value) + caplog.text and len(server.calls) <= 4


@pytest.mark.parametrize("value", [True, -1, "NaN", "1e9", "-0.5", "1.1234567", 10**16, {}, []])
def test_budget_rejects_lossy_or_unbounded_values(value: Any) -> None:
    server = Server()
    server.budget = value
    with pytest.raises(TikTokNativeInventoryUnavailable):
        read(server)


def test_explicit_empty_and_absent_budget_remain_unqualified() -> None:
    server = Server()
    server.mode = "empty"
    assert read(server).campaigns == []
    server.mode = "absent_budget"
    result = read(server)
    assert result.campaigns[0].budget_native is None
    server.mode = None
    server.budget = 0
    assert read(server).campaigns[0].budget_native == "0"


@pytest.mark.parametrize("change", ["generation", "request", "expired", "revoked"])
def test_scope_is_rechecked_after_http(change: str) -> None:
    server = Server()

    def current(req: TikTokInventoryRequest, now: Any) -> TikTokNativeInventoryContext:
        value = context(req, now)
        if server.calls:
            if change == "generation":
                return value.model_copy(
                    update={
                        "scope": req.account.model_copy(
                            update={"connection_version": "tiktok:abc:2"}
                        )
                    }
                )
            if change == "request":
                return value.model_copy(update={"request_digest": "f" * 64})
            if change == "expired":
                return value.model_copy(update={"expires_at": NOW})
            raise RuntimeError(PRIVATE)
        return value

    with pytest.raises(TikTokNativeInventoryUnavailable) as error:
        read(server, current)
    assert len(server.calls) == 1 and PRIVATE not in str(error.value)


@pytest.mark.parametrize(
    "field",
    [
        "account_cap",
        "cap_counter_epoch",
        "original_request_terminality",
        "reporting_watermark",
        "unreported_upper_micros",
        "unchanged_future_upper_micros",
        "proposed_owner_upper_micros",
    ],
)
def test_results_cannot_claim_unimplemented_proofs(field: str) -> None:
    raw = read(Server()).model_dump()
    raw[field] = 0
    with pytest.raises(ValidationError):
        TikTokNativeInventory.model_validate(raw)
