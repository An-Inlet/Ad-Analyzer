"""Actual read-only HTTP parser and current-context checks, no provider/network access."""

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.collectors.meta_native_inventory import (
    MetaNativeInventory,
    MetaNativeInventoryContext,
    MetaNativeInventoryHTTP,
    MetaNativeInventoryRequest,
    MetaNativeInventoryUnavailable,
)
from pydantic import SecretStr, ValidationError

NOW = datetime(2026, 10, 6, tzinfo=UTC)
PRIVATE = "private-token-or-provider-payload"


def request() -> MetaNativeInventoryRequest:
    return MetaNativeInventoryRequest(
        account=dict(
            workspace_id=1,
            account=dict(platform="meta_ads", connection_id=2, account_id=3),
            external_advertiser_id="123",
            connection_version="meta:abc:1",
        ),
        mandate=dict(
            mandate_id="a" * 32,
            revision=1,
            consent_id="b" * 32,
            policy_digest="c" * 64,
            ledger_id="d" * 32,
            environment="contract_test",
        ),
        currency="USD",
        time_zone="UTC",
        period_start=NOW,
        period_end=NOW + timedelta(days=1),
    )


def context(req: MetaNativeInventoryRequest, now: datetime) -> MetaNativeInventoryContext:
    return MetaNativeInventoryContext(
        scope=req.account,
        request_digest=req.digest(),
        access_token=SecretStr(PRIVATE),
        app_secret=SecretStr("synthetic-app-secret"),
        expires_at=NOW + timedelta(hours=1),
    )


class Server:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.account: dict[str, Any] = dict(
            account_id="123",
            currency="USD",
            timezone_name="UTC",
            account_status=1,
            spend_cap="10000",
            amount_spent="0",
        )
        self.campaigns = [
            dict(
                id="5",
                account_id="123",
                configured_status="ACTIVE",
                effective_status="ACTIVE",
                daily_budget="100",
                lifetime_budget="0",
                spend_cap="10000",
            )
        ]
        self.adsets = [
            dict(
                id="6",
                account_id="123",
                campaign_id="5",
                configured_status="PAUSED",
                effective_status="PAUSED",
                lifetime_budget="5000",
                lifetime_spend_cap="4000",
            )
        ]
        self.mode: str | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        assert req.method == "GET" and req.url.host == "graph.facebook.com"
        assert req.url.path.startswith("/v26.0/act_123")
        assert req.headers["authorization"] == "Bearer " + PRIVATE
        assert "access_token" not in req.url.params and "appsecret_proof" in req.url.params
        assert req.extensions["timeout"] == dict(connect=5, read=12, write=12, pool=12)
        if self.mode == "timeout":
            raise httpx.ReadTimeout(PRIVATE)
        if self.mode == "error":
            return httpx.Response(400, json={"error": {"message": PRIVATE}})
        if self.mode == "redirect":
            return httpx.Response(302, headers={"location": "https://example.invalid/" + PRIVATE})
        if self.mode == "oversize":
            return httpx.Response(200, content=b"x" * 1_000_001)
        if self.mode == "compressed":
            return httpx.Response(200, headers={"Content-Encoding": "unsupported"}, content=b"x")
        if req.url.path.endswith("act_123"):
            return httpx.Response(200, json=self.account)
        child = req.url.path.endswith("adsets")
        statuses = json.loads(req.url.params["effective_status"])
        assert all(s in statuses for s in ["ACTIVE", "PAUSED", "ARCHIVED", "DELETED"])
        fields = req.url.params["fields"]
        assert "account_id" in fields and "lifetime_budget" in fields
        rows = copy.deepcopy(self.adsets if child else self.campaigns)
        if not child and self.mode in {"page", "foreign_page", "cycle", "duplicate", "no_cursor"}:
            if "after" not in req.url.params or self.mode == "cycle":
                result: dict[str, Any] = {
                    "data": [] if self.mode == "cycle" else rows,
                    "paging": {
                        "next": "https://example.invalid/" + PRIVATE,
                        "cursors": {"after": "opaque"},
                    },
                }
                if self.mode == "no_cursor":
                    del result["paging"]["cursors"]
                return httpx.Response(200, json=result)
            rows = [{**rows[0], "id": "7", "effective_status": "ARCHIVED"}]
            if self.mode == "foreign_page":
                rows[0]["account_id"] = "999"
            if self.mode == "duplicate":
                rows[0]["id"] = "5"
        return httpx.Response(200, json={"data": rows})


def read(server: Server, **kwargs: Any) -> MetaNativeInventory:
    return MetaNativeInventoryHTTP(
        kwargs.pop("context_reader", context),
        clock=kwargs.pop("clock", lambda: NOW),
        transport=httpx.MockTransport(server),
        **kwargs,
    )(request(), NOW)


def test_account_wide_paging_is_diagnostic_not_cap_or_watermark() -> None:
    server = Server()
    server.mode = "page"
    result = read(server)
    assert [r.id for r in result.campaigns] == ["5", "7"]
    assert result.adsets[0].campaign_id == "5" and result.adsets[0].spend_cap_native == 4000
    assert result.amount_spent_native == 0 and result.spend_cap_native == 10000
    assert result.campaigns[0].budget_sharing_enabled is None
    assert result.advertising_inventory_read_complete
    assert result.status_scope == "sdk_known_effective_statuses_only"
    assert result.all_effective_statuses_complete is False
    assert result.unit_semantics == "native_integer_unqualified"
    assert result.cap_semantics == "unqualified" and result.reporting_watermark is None
    assert (
        result.unreported_upper_micros
        is result.unchanged_future_upper_micros
        is result.proposed_owner_upper_micros
        is None
    )
    assert not result.pending_cap_changes_complete and not result.historical_obligations_complete
    assert all(r.url.host == "graph.facebook.com" for r in server.calls)
    assert PRIVATE not in result.model_dump_json() and len(result.digest()) == 64


@pytest.mark.parametrize(
    "mode",
    [
        "timeout",
        "error",
        "redirect",
        "oversize",
        "compressed",
        "foreign_page",
        "cycle",
        "duplicate",
        "no_cursor",
    ],
)
def test_bounded_failures_are_sanitized(mode: str, caplog: pytest.LogCaptureFixture) -> None:
    server = Server()
    server.mode = mode
    with pytest.raises(MetaNativeInventoryUnavailable) as error:
        read(server)
    assert PRIVATE not in str(error.value) + caplog.text
    assert len(server.calls) <= 4


@pytest.mark.parametrize("value", [True, -1, "-1", "NaN", "1.5", 10**16, "1" * 1000, 1.5])
def test_counter_schema_does_not_infer_amounts(value: Any) -> None:
    server = Server()
    server.account["amount_spent"] = value
    with pytest.raises(MetaNativeInventoryUnavailable):
        read(server)


def test_absent_fields_remain_unknown_and_new_status_is_incomplete() -> None:
    server = Server()
    del server.account["amount_spent"]
    del server.account["spend_cap"]
    server.adsets[0]["effective_status"] = "NEW_PROVIDER_STATUS"
    result = read(server)
    assert result.amount_spent_native is result.spend_cap_native is None
    assert (
        not result.advertising_inventory_read_complete and "native_status_unknown" in result.reasons
    )


@pytest.mark.parametrize(
    "change",
    [
        "foreign_child",
        "missing_parent",
        "currency",
        "timezone",
        "missing_owner",
        "bad_flag",
        "too_many",
    ],
)
def test_exact_owned_topology_and_shape(change: str) -> None:
    server = Server()
    if change == "foreign_child":
        server.adsets[0]["account_id"] = "999"
    elif change == "missing_parent":
        server.adsets[0]["campaign_id"] = "999"
    elif change == "currency":
        server.account["currency"] = "GBP"
    elif change == "timezone":
        server.account["timezone_name"] = "Europe/London"
    elif change == "missing_owner":
        del server.campaigns[0]["account_id"]
    elif change == "bad_flag":
        server.campaigns[0]["is_budget_schedule_enabled"] = "false"
    else:
        server.campaigns = [{**server.campaigns[0], "id": str(i)} for i in range(201)]
    with pytest.raises(MetaNativeInventoryUnavailable):
        read(server)


@pytest.mark.parametrize("change", ["generation", "request", "expired", "denied"])
def test_current_context_rechecked_after_blocking_http(change: str) -> None:
    server = Server()

    def fresh(req: MetaNativeInventoryRequest, now: datetime) -> MetaNativeInventoryContext:
        result = context(req, now)
        if server.calls:
            if change == "generation":
                return result.model_copy(
                    update={
                        "scope": req.account.model_copy(update={"connection_version": "meta:abc:2"})
                    }
                )
            if change == "request":
                return result.model_copy(update={"request_digest": "f" * 64})
            if change == "expired":
                return result.model_copy(update={"expires_at": NOW})
            raise RuntimeError(PRIVATE)
        return result

    with pytest.raises(MetaNativeInventoryUnavailable) as error:
        read(server, context_reader=fresh)
    assert PRIVATE not in str(error.value) and len(server.calls) == 1


@pytest.mark.parametrize(
    "field",
    [
        "reporting_watermark",
        "unreported_upper_micros",
        "unchanged_future_upper_micros",
        "proposed_owner_upper_micros",
    ],
)
def test_result_cannot_be_promoted_to_proof(field: str) -> None:
    result = read(Server()).model_dump()
    result[field] = NOW if field == "reporting_watermark" else 0
    with pytest.raises(ValidationError):
        MetaNativeInventory.model_validate(result)


@pytest.mark.parametrize("failure", ["page_bound", "total_bytes", "duplicate_child"])
def test_inventory_limits_include_empty_pages_and_whole_response(failure: str) -> None:
    server = Server()
    count = 0

    def transport(req: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if failure == "duplicate_child":
            server.adsets *= 2
            return server(req)
        if req.url.path.endswith("act_123"):
            return server(req)
        body = {"data": [], "paging": {"next": "ignored", "cursors": {"after": str(count)}}}
        if failure == "total_bytes":
            body["padding"] = "x" * 900_000
        return httpx.Response(200, json=body)

    with pytest.raises(MetaNativeInventoryUnavailable) as error:
        MetaNativeInventoryHTTP(
            context, clock=lambda: NOW, transport=httpx.MockTransport(transport)
        )(request(), NOW)
    assert (
        str(error.value)
        == {
            "page_bound": "inventory_page_bound",
            "total_bytes": "inventory_response_bound",
            "duplicate_child": "inventory_duplicate",
        }[failure]
    )
    assert count <= 11


def test_expiry_during_context_resolution_is_checked_before_first_http() -> None:
    server = Server()
    clock = [NOW]

    def slow(req: MetaNativeInventoryRequest, now: datetime) -> MetaNativeInventoryContext:
        clock[0] += timedelta(minutes=6)
        return context(req, now)

    with pytest.raises(MetaNativeInventoryUnavailable):
        read(server, context_reader=slow, clock=lambda: clock[0])
    assert not server.calls


def test_success_does_not_log_proof_or_tokens(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    caplog.set_level(logging.DEBUG, logger="httpx")
    read(Server())
    assert "appsecret_proof" not in caplog.text and PRIVATE not in caplog.text


@pytest.mark.parametrize("change", ["provider", "period", "identity", "zone"])
def test_invalid_request_is_rejected(change: str) -> None:
    raw = request().model_dump()
    if change == "provider":
        raw["account"]["account"]["platform"] = "google_ads"
    elif change == "period":
        raw["period_end"] = NOW + timedelta(days=367)
    elif change == "identity":
        raw["account"]["external_advertiser_id"] = "../private"
    else:
        raw["time_zone"] = "invalid/zone"
    with pytest.raises((ValidationError, KeyError)):
        MetaNativeInventoryRequest.model_validate(raw)
