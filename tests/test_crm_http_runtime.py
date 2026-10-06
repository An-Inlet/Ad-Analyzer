"""Mock HTTP only: real request paths and account proof, no credentialed network IO."""

import base64
import hashlib
import logging
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app.customer_context.http import (
    CRMReadError,
    HubSpotHTTPRead,
    KlaviyoHTTPRead,
    OmnisendHTTPRead,
)
from app.customer_context.wire import KLAVIYO_REVISION, ProfileReader
from app.settings import settings
from app.sources import service
from app.sources.contracts import UnavailableSource, get_source_transport
from app.sources.models import SourceAuthorization
from app.sources.security import SourceVault
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_context import IO
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_tiktok_sources import configured as configured

CLIENT = "fixture-client"
SECRET = SecretStr("synthetic-private-secret")
TOKEN = "synthetic-access-token"
REFRESH = "synthetic-refresh-token"


def callback(provider: str) -> str:
    return f"https://inlet.example/api/customer/v1/sources/{provider}/callback"


class ProviderHTTP:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.calls: list[httpx.Request] = []
        self.account = "account1" if provider == "klaviyo" else "123"
        self.client = CLIENT
        self.active = True
        self.extra_scope = False
        self.profiles: dict[str, Any] | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        path = request.url.path
        if path.endswith("/token"):
            scopes = (
                "accounts:read profiles:read"
                if self.provider == "klaviyo"
                else "oauth crm.objects.contacts.read"
            )
            return httpx.Response(
                200,
                json={
                    "token_type": "Bearer",
                    "access_token": TOKEN,
                    "refresh_token": REFRESH,
                    "expires_in": 3600,
                    "scope": scopes + (" profiles:write" if self.extra_scope else ""),
                },
            )
        if path.endswith("/introspect"):
            return httpx.Response(
                200,
                json={
                    "active": self.active,
                    "token": TOKEN,
                    "expires_in": 1800,
                    "hub_id": int(self.account),
                    "client_id": self.client,
                    "token_use": "access_token",
                    "scopes": ["oauth", "crm.objects.contacts.read"]
                    + (["crm.objects.contacts.write"] if self.extra_scope else []),
                },
            )
        if path == "/api/accounts":
            return httpx.Response(200, json={"data": [{"type": "account", "id": self.account}]})
        if path.endswith("/revoke"):
            return httpx.Response(200)
        if self.profiles is not None:
            return httpx.Response(200, json=self.profiles)
        if self.provider == "klaviyo":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "p1",
                            "attributes": {
                                "email": "private@example.test",
                                "subscriptions": {
                                    "email": {
                                        "marketing": {
                                            "consent": "SUBSCRIBED",
                                            "suppression": [],
                                            "list_suppressions": [{"list_id": "private-list"}],
                                        }
                                    }
                                },
                            },
                        }
                    ],
                    "links": {
                        "next": "https://a.klaviyo.com/api/profiles?page%5Bcursor%5D=page2"
                        if "page[cursor]" not in request.url.params
                        else None
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "p2",
                        "properties": {
                            "lifecyclestage": "customer",
                            "email": "private@example.test",
                            "revenue": 999,
                        },
                    }
                ],
                "paging": {"next": {"after": "page2", "link": "https://evil.test/token"}}
                if "after" not in request.url.params
                else {},
            },
        )


def adapter(provider: str, io: ProviderHTTP) -> KlaviyoHTTPRead | HubSpotHTTPRead:
    cls = KlaviyoHTTPRead if provider == "klaviyo" else HubSpotHTTPRead
    return cls(CLIENT, SECRET, transport=httpx.MockTransport(io), clock=lambda: NOW)


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot"])
def test_real_requests_prove_account_and_strip_personal_payloads(
    provider: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    io = ProviderHTTP(provider)
    runtime = adapter(provider, io)
    if isinstance(runtime, KlaviyoHTTPRead):
        url = runtime.authorize_url_pkce("s" * 43, callback(provider), "c" * 43)
        grant = runtime.exchange_pkce("synthetic-code", callback(provider), "v" * 43)
    else:
        url = runtime.authorize_url("s" * 43, callback(provider))
        grant = runtime.exchange("synthetic-code", callback(provider))
    assert SECRET.get_secret_value() not in url
    assert parse_qs(urlsplit(url).query)["state"] == ["s" * 43]
    assert grant.accounts[0].external_id == io.account
    assert grant.expires_at == NOW + timedelta(hours=1)
    first = runtime.page(io.account, TOKEN, None, NOW)
    assert first.next_cursor == "page2"
    second = runtime.page(io.account, TOKEN, first.next_cursor, NOW)
    assert second.next_cursor is None
    assert "private@" not in first.model_dump_json()
    assert "private-list" not in first.model_dump_json()
    assert "revenue" not in first.model_dump_json()
    if provider == "klaviyo":
        assert first.profiles[0].email_status == "subscribed"
        assert first.profiles[0].email_suppression_scope == "list"
        assert io.calls[-1].headers["revision"] == KLAVIYO_REVISION
        assert io.calls[-1].url.params["fields[profile]"] == "subscriptions"
        assert parse_qs(io.calls[0].content.decode())["code_verifier"] == ["v" * 43]
    else:
        assert first.profiles[0].lifecycle == "customer"
        assert io.calls[-1].url.params["properties"] == "lifecyclestage"
        introspections = [c for c in io.calls if c.url.path.endswith("/introspect")]
        assert len(introspections) == 3
        assert all(c.method == "POST" and not c.url.query for c in introspections)
    for secret in [TOKEN, REFRESH, SECRET.get_secret_value(), "private@example.test", "v" * 43]:
        assert secret not in caplog.text
        assert all(secret not in str(c.url) for c in io.calls)
    assert all(
        c.method == "GET"
        or c.url.path in {"/oauth/token", "/oauth/v3/token", "/oauth/v3/token/introspect"}
        for c in io.calls
    )


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot"])
def test_account_mismatch_prevents_profile_read_and_refresh_change(provider: str) -> None:
    io = ProviderHTTP(provider)
    runtime = adapter(provider, io)
    with pytest.raises(CRMReadError, match="account_mismatch"):
        runtime.page("other-account", TOKEN, None, NOW)
    assert len(io.calls) == 1
    with pytest.raises(CRMReadError, match="account_mismatch"):
        runtime.refresh(REFRESH, "other-account")
    assert not any(
        c.url.path.endswith("/profiles") or c.url.path.endswith("/contacts") for c in io.calls
    )


@pytest.mark.parametrize("status", [301, 401, 403, 410, 429, 500])
def test_provider_errors_are_bounded_sanitized_and_not_retried(status: int) -> None:
    calls = []

    def fail(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status, json={"secret": TOKEN}, headers={"location": "https://evil.test"}
        )

    runtime = KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(fail))
    with pytest.raises(CRMReadError) as error:
        runtime.page("a", TOKEN, None, NOW)
    assert len(calls) == 1 and TOKEN not in str(error.value)


@pytest.mark.parametrize("fault", ["timeout", "oversize", "invalid", "shape"])
def test_http_failure_boundaries(fault: str) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        if fault == "timeout":
            raise httpx.ReadTimeout(TOKEN)
        if fault == "oversize":
            return httpx.Response(200, content=b"x" * 2_000_001)
        if fault == "invalid":
            return httpx.Response(200, content=b"not-json-private")
        return httpx.Response(200, json=[])

    runtime = KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(fail))
    with pytest.raises(CRMReadError) as error:
        runtime.page("a", TOKEN, None, NOW)
    assert TOKEN not in str(error.value)


def test_hubspot_inactive_wrong_client_or_overbroad_scope_rejected() -> None:
    for field, value in [("active", False), ("client", "other-client"), ("extra_scope", True)]:
        io = ProviderHTTP("hubspot")
        setattr(io, field, value)
        with pytest.raises(CRMReadError, match="account_unavailable"):
            adapter("hubspot", io).page("123", TOKEN, None, NOW)
        assert len(io.calls) == 1


def test_klaviyo_scope_revision_and_pkce_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    io = ProviderHTTP("klaviyo")
    runtime = KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(io))
    with pytest.raises(CRMReadError, match="pkce_required"):
        runtime.exchange("code", callback("klaviyo"))
    with pytest.raises(CRMReadError, match="pkce_required"):
        runtime.authorize_url("s" * 43, callback("klaviyo"))
    assert not io.calls
    io.extra_scope = True
    with pytest.raises(CRMReadError, match="scope_mismatch"):
        runtime.exchange_pkce("code", callback("klaviyo"), "v" * 43)
    monkeypatch.setattr(settings, "klaviyo_runtime_mode", "provider_read")
    monkeypatch.setattr(settings, "klaviyo_client_id", CLIENT)
    monkeypatch.setattr(settings, "klaviyo_client_secret", SECRET)
    monkeypatch.setattr(settings, "klaviyo_api_revision", "unverified")
    assert isinstance(get_source_transport("klaviyo"), UnavailableSource)
    monkeypatch.setattr(settings, "klaviyo_api_revision", KLAVIYO_REVISION)
    assert isinstance(get_source_transport("klaviyo"), KlaviyoHTTPRead)


def test_runtime_factories_disabled_and_cross_provider_readiness(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert isinstance(get_source_transport("klaviyo"), UnavailableSource)
    assert isinstance(get_source_transport("hubspot"), UnavailableSource)
    assert isinstance(get_source_transport("omnisend"), UnavailableSource)
    monkeypatch.setattr(settings, "hubspot_runtime_mode", "provider_read")
    monkeypatch.setattr(settings, "hubspot_client_id", CLIENT)
    monkeypatch.setattr(settings, "hubspot_client_secret", SECRET)
    runtime = get_source_transport("hubspot")
    assert isinstance(runtime, HubSpotHTTPRead)
    with pytest.raises(HTTPException, match="provider mismatch"):
        service.ready(runtime, "klaviyo")


def test_omnisend_documented_projection_and_unverified_identity_fail_closed() -> None:
    payload = {
        "contacts": [
            {
                "id": "p",
                "identifiers": [
                    {"id": "private@example.test", "channels": {"email": {"status": "subscribed"}}}
                ],
            }
        ],
        "paging": {"hasMore": False, "cursors": {"after": "do-not-follow"}},
    }
    page = ProfileReader("omnisend", IO(payload)).page("fixture", TOKEN, None, NOW)
    assert page.next_cursor is None and page.profiles[0].email_status == "subscribed"
    payload["paging"] = {"hasMore": True, "cursors": {}}
    with pytest.raises(ValueError, match="missing continuation"):
        ProfileReader("omnisend", IO(payload)).page("fixture", TOKEN, None, NOW)
    calls = []

    def no_io(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200)

    runtime = OmnisendHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(no_io))
    with pytest.raises(CRMReadError, match="unverified"):
        runtime.page("caller-account", TOKEN, None, NOW)
    assert not calls


def test_two_pkce_attempts_are_durable_isolated_and_cleared(
    customer_engine: Engine, configured: None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    io = ProviderHTTP("klaviyo")
    runtime = KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(io), clock=lambda: NOW)
    with Session(customer_engine) as db:
        wid, sid = setup(db, "pkce-one")
        wid2, sid2 = setup(db, "pkce-two")
        urls = [
            service.begin(db, "klaviyo", wid, sid, runtime, NOW),
            service.begin(db, "klaviyo", wid2, sid2, runtime, NOW),
        ]
        params = [parse_qs(urlsplit(url).query) for url in urls]
        nonces = [p["state"][0] for p in params]
        rows = list(db.scalars(select(SourceAuthorization)))
        verifiers = {}
        for row in rows:
            assert row.encrypted_grant
            value = SourceVault().open(
                row.workspace_id, row.provider, row.digest, row.encrypted_grant
            )["pkce_verifier"]
            verifiers[row.workspace_id] = value
            assert value not in row.encrypted_grant and value not in str(row.accounts)
            assert value not in caplog.text and all(value not in url for url in urls)
        assert verifiers[wid] != verifiers[wid2]
        for i, workspace in enumerate([wid, wid2]):
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifiers[workspace].encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            assert params[i]["code_challenge"] == [challenge]
        with pytest.raises(HTTPException):
            service.finish(db, "klaviyo", nonces[0], sid2, "code", runtime, NOW)
        # A newly constructed adapter receives the durable verifier, no shared adapter state.
        for index, session_id in [(1, sid2), (0, sid)]:
            replica = KlaviyoHTTPRead(
                CLIENT, SECRET, transport=httpx.MockTransport(io), clock=lambda: NOW
            )
            row = service.finish(db, "klaviyo", nonces[index], session_id, "code", replica, NOW)
            assert row.encrypted_grant
            assert "pkce_verifier" not in SourceVault().open(
                row.workspace_id, row.provider, row.digest, row.encrypted_grant
            )
        forms = [parse_qs(c.content.decode()) for c in io.calls if c.url.path.endswith("/token")]
        assert forms[0]["code_verifier"] == [verifiers[wid2]]
        assert forms[1]["code_verifier"] == [verifiers[wid]]
        with pytest.raises(HTTPException, match="already consumed"):
            service.finish(db, "klaviyo", nonces[0], sid, "code", runtime, NOW)


def test_pkce_uncertain_exchange_clears_verifier_and_blocks_replay(
    customer_engine: Engine, configured: None
) -> None:
    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private token")

    runtime = KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(fail))
    with Session(customer_engine) as db:
        wid, sid = setup(db, "pkce-fail")
        nonce = parse_qs(urlsplit(service.begin(db, "klaviyo", wid, sid, runtime, NOW)).query)[
            "state"
        ][0]
        with pytest.raises(HTTPException, match="restart connection"):
            service.finish(db, "klaviyo", nonce, sid, "code", runtime, NOW)
        db.close()
    with Session(customer_engine) as db:
        row = service.authorization(db, "klaviyo", nonce, sid, NOW)
        assert row.state == "exchanging" and row.encrypted_grant is None
        with pytest.raises(HTTPException, match="already consumed"):
            service.finish(db, "klaviyo", nonce, sid, "code", runtime, NOW)


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot"])
def test_fixed_http_endpoints_and_cursor_validation(provider: str) -> None:
    io = ProviderHTTP(provider)
    runtime = adapter(provider, io)
    with pytest.raises(CRMReadError, match="endpoint_unavailable"):
        runtime.get("https://evil.test/profiles", {"Authorization": TOKEN}, {})
    with pytest.raises(CRMReadError, match="endpoint_unavailable"):
        runtime._request("POST", "https://api.hubapi.com/crm/v3/objects/contacts", data={})
    with pytest.raises(CRMReadError, match="value_invalid"):
        runtime.page(io.account, TOKEN, "\nprivate", NOW)
    assert not io.calls
    runtime.page(io.account, TOKEN, None, NOW)
    assert all(c.extensions["timeout"]["connect"] == 5 for c in io.calls)
    assert all(c.extensions["timeout"]["read"] == 20 for c in io.calls)
    if provider == "klaviyo":
        io.profiles = {
            "data": [],
            "links": {"next": "https://a.klaviyo.com.evil.test/api/profiles?page[cursor]=x"},
        }
    else:
        io.profiles = {"results": [], "paging": {"next": {"after": "repeat"}}}
    with pytest.raises(CRMReadError, match="invalid|repeated"):
        runtime.page(io.account, TOKEN, "repeat", NOW)


def test_klaviyo_refresh_rotation_and_revoke_are_explicit_requests() -> None:
    io = ProviderHTTP("klaviyo")
    runtime = KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(io), clock=lambda: NOW)
    renewed = runtime.refresh("synthetic-old-refresh", io.account)
    assert renewed.refresh_token and renewed.refresh_token.get_secret_value() == REFRESH
    form = parse_qs(io.calls[0].content.decode())
    assert form == {"grant_type": ["refresh_token"], "refresh_token": ["synthetic-old-refresh"]}
    runtime.revoke(REFRESH)
    assert io.calls[-1].url.path == "/oauth/revoke"
    assert parse_qs(io.calls[-1].content.decode()) == {
        "token_type_hint": ["refresh_token"],
        "token": [REFRESH],
    }


def test_pkce_expiry_and_swapped_context_cannot_exchange(
    customer_engine: Engine, configured: None
) -> None:
    io = ProviderHTTP("klaviyo")
    runtime = KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(io), clock=lambda: NOW)
    with Session(customer_engine) as db:
        wid, sid = setup(db, "pkce-expiry")
        wid2, sid2 = setup(db, "pkce-swap")
        nonce = parse_qs(urlsplit(service.begin(db, "klaviyo", wid, sid, runtime, NOW)).query)[
            "state"
        ][0]
        other = parse_qs(urlsplit(service.begin(db, "klaviyo", wid2, sid2, runtime, NOW)).query)[
            "state"
        ][0]
        row = service.authorization(db, "klaviyo", nonce, sid, NOW)
        second = service.authorization(db, "klaviyo", other, sid2, NOW)
        row.encrypted_grant = second.encrypted_grant
        db.commit()
        with pytest.raises(HTTPException, match="reconnect required"):
            service.finish(db, "klaviyo", nonce, sid, "code", runtime, NOW)
        with pytest.raises(HTTPException, match="authorization unavailable"):
            service.finish(db, "klaviyo", other, sid2, "code", runtime, NOW + timedelta(minutes=5))
        assert not io.calls


def test_provider_cursor_does_not_leak_through_httpx_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    io = ProviderHTTP("hubspot")
    runtime = adapter("hubspot", io)
    runtime.page(io.account, TOKEN, "private-cursor@example.test", NOW)
    assert "private-cursor" not in caplog.text
    assert "details redacted" in caplog.text


def test_hubspot_introspection_cannot_substitute_another_token() -> None:
    io = ProviderHTTP("hubspot")
    with pytest.raises(CRMReadError, match="account_unavailable"):
        adapter("hubspot", io).page("123", "other-token", None, NOW)
    assert len(io.calls) == 1
