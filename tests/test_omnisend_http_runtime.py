"""First-party contract fixtures through actual HTTP request construction, never live IO."""

import logging
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app.customer_context.http import (
    CRMAuthenticationUnavailable,
    CRMRateLimited,
    CRMReadError,
    OmnisendHTTPRead,
)
from app.customer_context.wire import OMNISEND_REVISION
from app.settings import settings
from app.sources import service
from app.sources.contracts import UnavailableSource, get_source_transport
from app.sources.models import SourceConnection
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_tiktok_sources import configured as configured

TOKEN, REFRESH = "fixture-omni-access", "fixture-omni-refresh"
CALLBACK = "https://inlet.example/api/customer/v1/sources/omnisend/callback"


class OmnisendIO:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.brand: dict[str, Any] = {"brandID": "brand_123", "platform": "shopify"}
        self.grant: dict[str, Any] = {
            "access_token": TOKEN,
            "refresh_token": REFRESH,
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "brands.read contacts.read",
        }
        self.profiles: dict[str, Any] = {"contacts": [], "paging": {"hasMore": False}}
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        assert request.url.host in {"api.omnisend.com", "app.omnisend.com"}
        assert request.extensions["timeout"] == {"connect": 5, "read": 20, "write": 20, "pool": 20}
        if self.status != 200:
            return httpx.Response(
                self.status,
                headers={"Retry-After": "120", "Location": "https://attacker.test"},
                json={"detail": "private response"},
            )
        if request.url.path == "/oauth2/token":
            assert request.method == "POST"
            assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
            body = parse_qs(request.content.decode())
            assert body["client_id"] == ["fixture-client"]
            assert body["client_secret"] == ["fixture-secret"]
            return httpx.Response(200, json=self.grant)
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        assert request.headers["Omnisend-Version"] == OMNISEND_REVISION
        if request.url.path == "/api/brands/current":
            assert not request.url.query
            return httpx.Response(200, json=self.brand)
        assert request.url.path == "/api/contacts"
        assert request.url.params["limit"] == "100"
        return httpx.Response(200, json=self.profiles)


def adapter(io: OmnisendIO) -> OmnisendHTTPRead:
    return OmnisendHTTPRead(
        "fixture-client",
        SecretStr("fixture-secret"),
        transport=httpx.MockTransport(io),
        clock=lambda: NOW,
    )


def test_exact_authorization_exchange_account_and_rotation() -> None:
    io = OmnisendIO()
    runtime = adapter(io)
    url = urlsplit(runtime.authorize_url("a" * 43, CALLBACK))
    query = parse_qs(url.query)
    assert "scope=brands.read%20contacts.read" in url.query
    assert "scopes=" not in url.query
    assert (
        url.scheme == "https"
        and url.netloc == "app.omnisend.com"
        and url.path == "/oauth2/authorize"
    )
    assert query == {
        "response_type": ["code"],
        "client_id": ["fixture-client"],
        "redirect_uri": [CALLBACK],
        "state": ["a" * 43],
        "scope": ["brands.read contacts.read"],
    }
    assert not io.calls
    grant = runtime.exchange("code+with/symbols", CALLBACK)
    assert grant.accounts[0].external_id == "brand_123"
    assert grant.expires_at == NOW + timedelta(hours=1)
    body = parse_qs(io.calls[0].content.decode())
    assert body["code"] == ["code+with/symbols"] and body["redirect_uri"] == [CALLBACK]
    assert body["grant_type"] == ["authorization_code"]
    io.grant["refresh_token"] = "fixture-rotated"
    assert runtime.refresh(REFRESH, "brand_123").refresh_token == SecretStr("fixture-rotated")
    io.grant.pop("refresh_token")
    io.grant.pop("scope")
    renewed = runtime.refresh(REFRESH, "brand_123")
    assert renewed.refresh_token == SecretStr(REFRESH)
    assert parse_qs(io.calls[-2].content.decode())["grant_type"] == ["refresh_token"]
    assert not hasattr(runtime, "revoke")


@pytest.mark.parametrize("expiry", [None, "missing"])
def test_unknown_expiry_is_not_fabricated(expiry: object) -> None:
    io = OmnisendIO()
    if expiry == "missing":
        io.grant.pop("expires_in")
    else:
        io.grant["expires_in"] = expiry
    io.grant.pop("refresh_token")
    grant = adapter(io).exchange("code", CALLBACK)
    assert grant.expires_at is None and grant.refresh_token is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "brands.read contacts.read contacts.write"),
        ("scope", "brands.read"),
        ("scope", None),
        ("token_type", "MAC"),
        ("expires_in", True),
        ("expires_in", -1),
        ("expires_in", "3600"),
        ("expires_in", 10_000_000_001),
        ("access_token", ""),
        ("refresh_token", ""),
        ("refresh_token", None),
    ],
)
def test_invalid_grant_fields_fail_before_account(field: str, value: object) -> None:
    io = OmnisendIO()
    io.grant[field] = value
    with pytest.raises(CRMReadError):
        adapter(io).exchange("code", CALLBACK)
    assert len(io.calls) == 1


@pytest.mark.parametrize(
    "brand",
    [
        {},
        {"id": "wrong"},
        {"brandID": ""},
        {"brandID": 123},
        {"brandID": "../foreign"},
        {"data": {"brandID": "nested"}},
    ],
)
def test_only_canonical_top_level_brand_id_is_authority(brand: dict[str, Any]) -> None:
    io = OmnisendIO()
    io.brand = brand
    with pytest.raises(CRMReadError, match="account_unavailable"):
        adapter(io).page("brand_123", TOKEN, None, NOW)
    assert len(io.calls) == 1


def test_foreign_brand_denies_profiles_and_refresh() -> None:
    io = OmnisendIO()
    runtime = adapter(io)
    with pytest.raises(CRMReadError, match="account_mismatch"):
        runtime.page("other_brand", TOKEN, None, NOW)
    assert len(io.calls) == 1
    with pytest.raises(CRMReadError, match="account_mismatch"):
        runtime.refresh(REFRESH, "other_brand")
    assert all(r.url.path != "/api/contacts" for r in io.calls)


def test_minimal_mixed_profile_projection_and_every_page_account_proof(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="httpx")
    io = OmnisendIO()
    io.profiles = {
        "contacts": [
            {
                "id": "one",
                "identifiers": [
                    {
                        "id": "private@example.test",
                        "channels": {"email": {"status": "subscribed"}, "sms": None},
                    }
                ],
            },
            {"id": "two", "identifiers": None},
            {
                "id": "three",
                "identifiers": [
                    {"channels": None},
                    {"channels": {"sms": {"status": "nonSubscribed"}}},
                ],
            },
            {
                "id": "four",
                "identifiers": [
                    {"channels": {"email": {"status": "subscribed"}}},
                    {"channels": {"email": {"status": "unsubscribed"}}},
                ],
            },
        ],
        "paging": {"hasMore": True, "cursors": {"after": "private-cursor+=="}},
    }
    runtime = adapter(io)
    page = runtime.page("brand_123", TOKEN, None, NOW)
    assert (
        page.profiles[0].email_status == "subscribed" and page.profiles[0].sms_status == "unknown"
    )
    assert all(p.email_status == "unknown" for p in page.profiles[1:])
    assert all(p.sms_status == "unknown" for p in page.profiles)
    assert "private@example.test" not in page.model_dump_json()
    io.profiles = {"contacts": [], "paging": {"hasMore": False, "cursors": {"after": "ignore"}}}
    final = runtime.page("brand_123", TOKEN, page.next_cursor, NOW)
    assert final.next_cursor is None
    assert [r.url.path for r in io.calls] == ["/api/brands/current", "/api/contacts"] * 2
    assert io.calls[-1].url.params["after"] == "private-cursor+=="
    assert TOKEN not in caplog.text and "private" not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {"contacts": [], "paging": {"hasMore": True}},
        {"contacts": [], "paging": {}},
        {"contacts": [], "paging": {"hasMore": "false"}},
        {"contacts": [None], "paging": {"hasMore": False}},
        {
            "contacts": [{"id": "p", "identifiers": [{"channels": {"email": []}}]}],
            "paging": {"hasMore": False},
        },
        {"contacts": [{"id": "p"}] * 251, "paging": {"hasMore": False}},
    ],
)
def test_malformed_pages_and_limits_fail_closed(payload: dict[str, Any]) -> None:
    io = OmnisendIO()
    io.profiles = payload
    with pytest.raises(CRMReadError):
        adapter(io).page("brand_123", TOKEN, None, NOW)


@pytest.mark.parametrize("code", [401, 403, 429, 500, 302])
def test_terminal_auth_rate_and_transient_errors_are_distinct(code: int) -> None:
    io = OmnisendIO()
    io.status = code
    expected = (
        CRMAuthenticationUnavailable
        if code in {401, 403}
        else CRMRateLimited
        if code == 429
        else CRMReadError
    )
    with pytest.raises(expected) as caught:
        adapter(io).account(TOKEN)
    if code == 429:
        assert isinstance(caught.value, CRMRateLimited) and caught.value.retry_after == 120
    if code not in {401, 403}:
        assert not isinstance(caught.value, CRMAuthenticationUnavailable)
    assert "private" not in str(caught.value)
    assert len(io.calls) == 1


def test_factory_opt_in_and_revision_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(get_source_transport("omnisend"), UnavailableSource)
    monkeypatch.setattr(settings, "omnisend_runtime_mode", "provider_read")
    monkeypatch.setattr(settings, "omnisend_client_id", "fixture-client")
    monkeypatch.setattr(settings, "omnisend_client_secret", SecretStr("fixture-secret"))
    assert isinstance(get_source_transport("omnisend"), UnavailableSource)
    monkeypatch.setattr(settings, "omnisend_api_revision", OMNISEND_REVISION)
    assert isinstance(get_source_transport("omnisend"), OmnisendHTTPRead)


def test_shared_source_flow_keeps_workspace_session_and_grant_boundaries(
    customer_engine: Engine,
    configured: None,
) -> None:
    io = OmnisendIO()
    runtime = adapter(io)
    with Session(customer_engine) as db:
        wid, sid = setup(db, "omni-one")
        foreign_wid, foreign_sid = setup(db, "omni-two")
        url = service.begin(db, "omnisend", wid, sid, runtime, NOW)
        state = parse_qs(urlsplit(url).query)["state"][0]
        with pytest.raises(HTTPException):
            service.finish(db, "omnisend", state, foreign_sid, "code", runtime, NOW)
        assert not io.calls
        service.finish(db, "omnisend", state, sid, "code", runtime, NOW)
        connection = service.select_account(db, "omnisend", state, sid, "brand_123", NOW)
        assert service.token(connection, NOW) == TOKEN
        stored = db.get(SourceConnection, connection.id)
        assert stored is not None and stored.workspace_id == wid
        with pytest.raises(HTTPException):
            service.owned(db, foreign_wid, "omnisend", connection.id)
        service.disconnect(db, service.owned(db, wid, "omnisend", connection.id))
        with pytest.raises(HTTPException):
            service.token(connection, NOW)
        with pytest.raises(HTTPException):
            service.finish(db, "omnisend", state, sid, "code", runtime, NOW)


def test_page_cycle_network_failure_body_limit_and_endpoint_allowlist() -> None:
    io = OmnisendIO()
    runtime = adapter(io)
    io.profiles = {"contacts": [], "paging": {"hasMore": True, "cursors": {"after": "same"}}}
    with pytest.raises(CRMReadError, match="cursor_repeated"):
        runtime.page("brand_123", TOKEN, "same", NOW)
    with pytest.raises(CRMReadError, match="endpoint_unavailable"):
        runtime.get("https://attacker.test/api/contacts", {}, {})
    assert len(io.calls) == 2

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private network detail", request=request)

    failed = OmnisendHTTPRead(
        "fixture-client", SecretStr("fixture-secret"), transport=httpx.MockTransport(broken)
    )
    with pytest.raises(CRMReadError, match="^crm_read_unavailable$"):
        failed.account(TOKEN)

    def huge(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2_000_001)

    oversized = OmnisendHTTPRead(
        "fixture-client", SecretStr("fixture-secret"), transport=httpx.MockTransport(huge)
    )
    with pytest.raises(CRMReadError, match="response_exceeds_bounds"):
        oversized.account(TOKEN)


@pytest.mark.parametrize("identifier_type,channel", [("email", "email"), ("phone", "sms")])
@pytest.mark.parametrize(
    "unknown",
    [{}, {"channels": None}, {"channels": {}}, {"channels": {"email": None, "sms": None}}],
)
def test_mixed_known_and_unknown_identifier_remains_unknown(
    identifier_type: str, channel: str, unknown: dict[str, Any]
) -> None:
    io = OmnisendIO()
    io.profiles = {
        "contacts": [
            {
                "id": "mixed",
                "identifiers": [
                    {"type": identifier_type, "channels": {channel: {"status": "subscribed"}}},
                    {"type": identifier_type, **unknown},
                ],
            }
        ],
        "paging": {"hasMore": False},
    }
    page = adapter(io).page("brand_123", TOKEN, None, NOW)
    assert getattr(page.profiles[0], channel + "_status") == "unknown"


@pytest.mark.parametrize(
    "hint,header,expected",
    [
        (180, None, 180),
        (180, "240", 240),
        (240, "180", 240),
        (-1, None, 60),
        (True, None, 60),
        ("180", None, 60),
        (None, None, 60),
        (1.5, None, 60),
        (10**40, None, 86400),
    ],
)
def test_omnisend_problem_retry_delay(hint: Any, header: str | None, expected: int) -> None:
    from app.customer_context.http import CRMRateLimited

    runtime = adapter(OmnisendIO())
    runtime.transport = httpx.MockTransport(
        lambda _: httpx.Response(
            429,
            headers={"Retry-After": header} if header else {},
            json={
                "type": "https://problems.omnisend.com/rate-limit-exceeded",
                "status": 429,
                "retryAfter": hint,
            },
        )
    )
    with pytest.raises(CRMRateLimited) as result:
        runtime.page("brand_123", TOKEN, None, NOW)
    assert result.value.retry_after == expected


@pytest.mark.parametrize("body", [b"invalid json", b"[180]", b"x" * 17000])
def test_omnisend_invalid_problem_preserves_header(body: bytes) -> None:
    from app.customer_context.http import CRMRateLimited

    runtime = adapter(OmnisendIO())
    runtime.transport = httpx.MockTransport(
        lambda _: httpx.Response(
            429,
            headers={"Retry-After": "240"},
            content=body,
        )
    )
    with pytest.raises(CRMRateLimited) as result:
        runtime.page("brand_123", TOKEN, None, NOW)
    assert result.value.retry_after == 240


def test_omnisend_problem_stream_failure_keeps_cooldown_and_closes() -> None:
    from collections.abc import Iterator

    from app.customer_context.http import CRMRateLimited

    class BrokenBody(httpx.SyncByteStream):
        closed = False

        def __iter__(self) -> Iterator[bytes]:
            yield b'{"retryAfter":'
            raise httpx.ReadError("synthetic interrupted error body")

        def close(self) -> None:
            self.closed = True

    body = BrokenBody()
    runtime = adapter(OmnisendIO())
    runtime.transport = httpx.MockTransport(
        lambda _: httpx.Response(
            429,
            headers={"Retry-After": "240"},
            stream=body,
        )
    )
    with pytest.raises(CRMRateLimited) as result:
        runtime.page("brand_123", TOKEN, None, NOW)
    assert result.value.retry_after == 240 and body.closed
