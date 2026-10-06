"""Durable renewal phases with mocked real HTTP and independent DB replicas."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from typing import Any
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
import pytest
from app.customer_context.http import CRMHTTP, HubSpotHTTPRead, KlaviyoHTTPRead, OmnisendHTTPRead
from app.customer_context.models import CRMCheckpoint
from app.customer_context.pacing import DeferredRead, PageDelivery, acknowledge_page, read_page
from app.sources import service
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_tiktok_sources import configured as configured


class RenewalIO:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.account = "77" if provider == "hubspot" else "account1"
        self.calls: list[httpx.Request] = []
        self.token_status = 200
        self.token_error = "invalid_grant"
        self.proof_status = 200
        self.read_status = 200
        self.proof_wrong_account = False
        self.on_token: Any = None
        self.on_proof: Any = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        path = request.url.path
        if path.endswith("/token"):
            assert request.method == "POST"
            data = parse_qs(request.content.decode())
            assert data["grant_type"] == ["refresh_token"]
            if self.on_token:
                self.on_token()
            if self.token_status != 200:
                return httpx.Response(
                    self.token_status,
                    headers={"Retry-After": "30"},
                    json={"error": self.token_error},
                )
            scope = {
                "klaviyo": "accounts:read profiles:read",
                "hubspot": "oauth crm.objects.contacts.read",
                "omnisend": "brands.read contacts.read",
            }[self.provider]
            return httpx.Response(
                200,
                json={
                    "access_token": "renewed-access",
                    "refresh_token": "rotated-refresh",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": scope,
                },
            )
        if path.endswith(("/accounts", "/brands/current", "/introspect")):
            if self.on_proof:
                self.on_proof()
            if self.proof_status != 200:
                return httpx.Response(
                    self.proof_status,
                    headers={"Retry-After": "30"},
                    json={"error": "private provider response"},
                )
            account = "foreign" if self.proof_wrong_account else self.account
            if self.provider == "klaviyo":
                return httpx.Response(200, json={"data": [{"id": account, "type": "account"}]})
            if self.provider == "omnisend":
                return httpx.Response(200, json={"brandID": account})
            data = parse_qs(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "active": True,
                    "token": data["access_token"][0],
                    "expires_in": 3600,
                    "client_id": "fixture-client",
                    "token_use": "access_token",
                    "hub_id": 99 if self.proof_wrong_account else 77,
                    "scopes": ["oauth", "crm.objects.contacts.read"],
                },
            )
        if self.read_status != 200:
            return httpx.Response(self.read_status, json={"error": "private error"})
        last = "page[cursor]" in request.url.params or "after" in request.url.params
        if self.provider == "klaviyo":
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "profile", "attributes": {"subscriptions": {}}}],
                    "links": {
                        "next": None
                        if last
                        else "https://a.klaviyo.com/api/profiles?page%5Bcursor%5D=page-two"
                    },
                },
            )
        if self.provider == "hubspot":
            return httpx.Response(
                200,
                json={
                    "results": [{"id": "profile", "properties": {}}],
                    "paging": {} if last else {"next": {"after": "page-two"}},
                },
            )
        return httpx.Response(
            200,
            json={
                "contacts": [{"id": "profile", "identifiers": []}],
                "paging": {"hasMore": not last, "cursors": {"after": "page-two"}},
            },
        )


def reader(io: RenewalIO) -> CRMHTTP:
    cls = {"klaviyo": KlaviyoHTTPRead, "hubspot": HubSpotHTTPRead, "omnisend": OmnisendHTTPRead}[
        io.provider
    ]
    return cls(
        "fixture-client",
        SecretStr("fixture-secret"),
        transport=httpx.MockTransport(io),
        clock=lambda: NOW,
    )


def connect(
    db: Session,
    io: RenewalIO,
    *,
    expiry: str | None = None,
    name: str = "renewal",
    refresh: bool = True,
) -> tuple[int, str]:
    wid, _ = setup(db, name)
    integration = WorkspaceIntegration(
        workspace_id=wid,
        provider=io.provider,
        status="active",
        integration_key=io.provider,
        display_name="Fixture",
    )
    db.add(integration)
    db.flush()
    cid = uuid4().hex
    bundle = {
        "access_token": "old-access",
        "expires_at": expiry,
        "refresh_token": "original-refresh" if refresh else None,
    }
    row = SourceConnection(
        id=cid,
        workspace_id=wid,
        integration_id=integration.id,
        provider=io.provider,
        external_id=io.account,
        generation=1,
        status="connected",
        window_start=NOW.date(),
        window_end=NOW.date(),
        encrypted_grant=SourceVault().seal(wid, io.provider, cid, bundle),
    )
    db.add(row)
    db.commit()
    return wid, cid


def tokens(db: Session, wid: int, cid: str, provider: str) -> dict[str, Any]:
    row = db.get(SourceConnection, cid, populate_existing=True)
    assert row and row.encrypted_grant
    return SourceVault().open(wid, provider, cid, row.encrypted_grant)


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot", "omnisend"])
def test_rotating_renewal_preserves_cursor_with_separate_paced_proof(
    customer_engine: Engine, configured: None, provider: str
) -> None:
    io = RenewalIO(provider)
    runtime = reader(io)
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=(NOW + timedelta(seconds=61)).isoformat())
        first = read_page(db, wid, cid, 1, runtime, NOW)
        assert isinstance(first, PageDelivery)
        acknowledge_page(
            db, wid, cid, 1, first.receipt, NOW + timedelta(seconds=1), provider=runtime.provider
        )
    with Session(customer_engine) as db:
        issued = read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5))
        assert isinstance(issued, DeferredRead)
        assert tokens(db, wid, cid, provider)["access_token"] == "old-access"
        checkpoint = db.get(CRMCheckpoint, cid)
        assert checkpoint and checkpoint.state == "proof_ready"
        assert "renewed-access" not in repr(checkpoint.__dict__)
        count = len(io.calls)
        assert isinstance(
            read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=6)), DeferredRead
        )
        assert len(io.calls) == count
    with Session(customer_engine) as db:
        assert isinstance(
            read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=10)), DeferredRead
        )
        assert tokens(db, wid, cid, provider)["access_token"] == "renewed-access"
        row = db.get(SourceConnection, cid)
        assert row and row.generation == 1
        page = read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=15))
        assert isinstance(page, PageDelivery)
        assert (
            io.calls[-1].url.params.get("page[cursor]", io.calls[-1].url.params.get("after"))
            == "page-two"
        )
        acknowledge_page(
            db, wid, cid, 1, page.receipt, NOW + timedelta(seconds=16), provider=runtime.provider
        )
        assert read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=20)) is None
    assert len([r for r in io.calls if r.url.path.endswith("/token")]) == 1


@pytest.mark.parametrize("code", [429, 500])
def test_proof_retry_uses_encrypted_candidate_without_reissuing_token(
    customer_engine: Engine, configured: None, code: int
) -> None:
    io = RenewalIO("klaviyo")
    runtime = reader(io)
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat())
        assert isinstance(read_page(db, wid, cid, 1, runtime, NOW), DeferredRead)
    io.proof_status = code
    with Session(customer_engine) as db:
        retry = read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5))
        assert isinstance(retry, DeferredRead)
        assert tokens(db, wid, cid, "klaviyo")["access_token"] == "old-access"
    io.proof_status = 200
    with Session(customer_engine) as db:
        assert isinstance(read_page(db, wid, cid, 1, runtime, retry.due_at), DeferredRead)
        assert tokens(db, wid, cid, "klaviyo")["access_token"] == "renewed-access"
    assert len([r for r in io.calls if r.url.path.endswith("/token")]) == 1


@pytest.mark.parametrize(
    "code,error,expected",
    [
        (400, "invalid_grant", "reconnect_required"),
        (400, "invalid_client", "provider_error"),
        (429, "rate_limited", "provider_error"),
        (500, "server_error", "provider_error"),
    ],
)
def test_token_failures_do_not_replay_rotating_credentials(
    customer_engine: Engine, configured: None, code: int, error: str, expected: str
) -> None:
    io = RenewalIO("omnisend")
    io.token_status, io.token_error = code, error
    runtime = reader(io)
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat())
        with pytest.raises(HTTPException):
            read_page(db, wid, cid, 1, runtime, NOW)
        row = db.get(SourceConnection, cid)
        assert row and row.status == expected and row.encrypted_grant is None
        assert db.get(CRMCheckpoint, cid) is None
        with pytest.raises(HTTPException):
            read_page(db, wid, cid, 1, runtime, NOW + timedelta(minutes=5))
        assert len(io.calls) == 1


def test_read_auth_failure_one_renewal_then_reconnect(
    customer_engine: Engine, configured: None
) -> None:
    io = RenewalIO("klaviyo")
    runtime = reader(io)
    io.read_status = 401
    with Session(customer_engine) as db:
        wid, cid = connect(db, io)  # Unknown TTL never fabricated; auth failure triggers renewal.
        failed = read_page(db, wid, cid, 1, runtime, NOW)
        assert isinstance(failed, DeferredRead)
        assert not any(r.url.path.endswith("/token") for r in io.calls)
        assert isinstance(read_page(db, wid, cid, 1, runtime, failed.due_at), DeferredRead)
        assert isinstance(
            read_page(db, wid, cid, 1, runtime, failed.due_at + timedelta(seconds=5)), DeferredRead
        )
        with pytest.raises(HTTPException, match="reconnect required"):
            read_page(db, wid, cid, 1, runtime, failed.due_at + timedelta(seconds=10))
        row = db.get(SourceConnection, cid)
        assert row and row.status == "reconnect_required"
        assert db.get(CRMCheckpoint, cid) is None


def test_unknown_expiry_does_not_refresh_and_missing_token_reconnects(
    customer_engine: Engine, configured: None
) -> None:
    io = RenewalIO("omnisend")
    with Session(customer_engine) as db:
        wid, cid = connect(db, io)
        assert isinstance(read_page(db, wid, cid, 1, reader(io), NOW), PageDelivery)
        assert not any(r.url.path.endswith("/token") for r in io.calls)
        two = connect(db, io, expiry=NOW.isoformat(), name="no-refresh", refresh=False)
        with pytest.raises(HTTPException):
            read_page(db, *two, 1, reader(io), NOW)
        row = db.get(SourceConnection, two[1])
        assert row and row.status == "reconnect_required"


def test_crash_after_token_consumption_never_replays(
    customer_engine: Engine, configured: None
) -> None:
    io = RenewalIO("klaviyo")

    def crash() -> None:
        raise RuntimeError("synthetic process crash")

    io.on_token = crash
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat())
        with pytest.raises(RuntimeError):
            read_page(db, wid, cid, 1, reader(io), NOW)
    with Session(customer_engine) as db:
        before = read_page(db, wid, cid, 1, reader(io), NOW + timedelta(seconds=60))
        assert isinstance(before, DeferredRead)
        with pytest.raises(HTTPException, match="outcome unknown"):
            read_page(db, wid, cid, 1, reader(io), NOW + timedelta(seconds=121))
        row = db.get(SourceConnection, cid)
        assert row and row.status == "provider_error" and db.get(CRMCheckpoint, cid) is None
    assert len(io.calls) == 1


@pytest.mark.parametrize("phase", ["issue", "proof"])
def test_reconnect_fences_late_renewal_workers(
    customer_engine: Engine, configured: None, phase: str
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent row-lock race requires PostgreSQL")
    io = RenewalIO("klaviyo")
    runtime = reader(io)
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat())
        if phase == "proof":
            read_page(db, wid, cid, 1, runtime, NOW)
    entered, release = Event(), Event()

    def pause() -> None:
        entered.set()
        assert release.wait(20)

    if phase == "issue":
        io.on_token = pause
    else:
        io.on_proof = pause

    def worker() -> None:
        with Session(customer_engine) as db, pytest.raises(HTTPException):
            read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5))

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        assert entered.wait(10)
        try:
            with Session(customer_engine) as duplicate:
                assert isinstance(
                    read_page(duplicate, wid, cid, 1, runtime, NOW + timedelta(seconds=6)),
                    DeferredRead,
                )
            with Session(customer_engine) as db:
                row = service.owned(db, wid, "klaviyo", cid)
                service.discard_context_checkpoint(db, row)
                row.generation += 1
                row.encrypted_grant = SourceVault().seal(
                    wid, "klaviyo", cid, {"access_token": "new-customer-grant", "expires_at": None}
                )
                db.commit()
        finally:
            release.set()
        future.result(timeout=20)
    with Session(customer_engine) as db:
        final_row = db.get(SourceConnection, cid)
        assert final_row and final_row.generation == 2
        assert tokens(db, wid, cid, "klaviyo")["access_token"] == "new-customer-grant"
        assert db.get(CRMCheckpoint, cid) is None


def test_token_success_then_candidate_commit_crash_is_uncertain(
    customer_engine: Engine, configured: None
) -> None:
    io = RenewalIO("omnisend")
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat())

    class CrashBeforeCandidateCommit(Session):
        def commit(self) -> None:
            if any(
                isinstance(row, CRMCheckpoint) and row.state == "proof_ready"
                for row in self.identity_map.values()
            ):
                raise RuntimeError("synthetic lost durable candidate")
            super().commit()

    with CrashBeforeCandidateCommit(customer_engine) as db, pytest.raises(RuntimeError):
        read_page(db, wid, cid, 1, reader(io), NOW)
    with Session(customer_engine) as db:
        checkpoint = db.get(CRMCheckpoint, cid)
        assert checkpoint and checkpoint.state == "refreshing"
        assert tokens(db, wid, cid, "omnisend")["access_token"] == "old-access"
        with pytest.raises(HTTPException, match="outcome unknown"):
            read_page(db, wid, cid, 1, reader(io), NOW + timedelta(seconds=121))
    assert len(io.calls) == 1


@pytest.mark.parametrize("expiry", ["2026-10-05T12:00:00", "not-a-date", "99999-01-01T00:00:00Z"])
def test_invalid_expiry_never_schedules_or_fabricates_refresh(
    customer_engine: Engine, configured: None, expiry: str
) -> None:
    from app.customer_context.http import CRMReadError

    io = RenewalIO("omnisend")
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=expiry)
        with pytest.raises(CRMReadError, match="grant_invalid"):
            read_page(db, wid, cid, 1, reader(io), NOW)
    assert not io.calls


def test_foreign_scope_and_wrong_brand_candidates_never_install(
    customer_engine: Engine, configured: None
) -> None:
    io = RenewalIO("omnisend")
    runtime = reader(io)
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat())
        foreign_wid, _ = setup(db, "foreign")
        with pytest.raises(HTTPException):
            read_page(db, foreign_wid, cid, 1, runtime, NOW)
        assert not io.calls
        with pytest.raises(HTTPException):
            read_page(db, wid, cid, 1, reader(RenewalIO("klaviyo")), NOW)
        assert not io.calls
        assert isinstance(read_page(db, wid, cid, 1, runtime, NOW), DeferredRead)
        io.proof_wrong_account = True
        with pytest.raises(HTTPException, match="reconnect required"):
            read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5))
        row = db.get(SourceConnection, cid)
        assert row and row.status == "reconnect_required" and row.encrypted_grant is None
        assert db.get(CRMCheckpoint, cid) is None


def test_disconnect_wipes_unverified_renewal_candidate(
    customer_engine: Engine, configured: None
) -> None:
    io = RenewalIO("hubspot")
    runtime = reader(io)
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat())
        read_page(db, wid, cid, 1, runtime, NOW)
        assert db.get(CRMCheckpoint, cid) is not None
        service.disconnect(db, service.owned(db, wid, "hubspot", cid))
        assert db.get(CRMCheckpoint, cid) is None
        with pytest.raises(HTTPException):
            read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5))
    assert len(io.calls) == 1


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot", "omnisend"])
@pytest.mark.parametrize("backoff", [False, True])
def test_pending_candidate_bound_to_issuing_oauth_client(
    customer_engine: Engine, configured: None, provider: str, backoff: bool
) -> None:
    io = RenewalIO(provider)
    runtime = reader(io)
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat())
        read_page(db, wid, cid, 1, runtime, NOW)
        if backoff:
            io.proof_status = 429
            assert isinstance(
                read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5)), DeferredRead
            )
        alternate = reader(io)
        alternate.client_id = "different-configured-client"
        count = len(io.calls)
        with pytest.raises(HTTPException, match="client changed"):
            read_page(db, wid, cid, 1, alternate, NOW + timedelta(seconds=40))
        assert len(io.calls) == count
        row = db.get(SourceConnection, cid)
        assert row and row.status == "reconnect_required" and row.encrypted_grant is None
        assert db.get(CRMCheckpoint, cid) is None


@pytest.mark.parametrize("phase", ["read", "issue", "proof"])
def test_omnisend_body_delay_is_durable_for_all_phases(
    customer_engine: Engine, configured: None, phase: str
) -> None:
    io = RenewalIO("omnisend")
    runtime = reader(io)
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat() if phase != "read" else None)
        peer = connect(db, io, name="peer")
        if phase == "proof":
            read_page(db, wid, cid, 1, runtime, NOW)
        runtime.transport = httpx.MockTransport(
            lambda _: httpx.Response(429, json={"retryAfter": 180})
        )
        if phase == "issue":
            with pytest.raises(HTTPException, match="outcome unknown"):
                read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5))
            row = db.get(SourceConnection, cid)
            assert row and row.status == "provider_error" and row.error_code == "renewal_uncertain"
        else:
            delayed = read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5))
            assert isinstance(delayed, DeferredRead)
            assert delayed.due_at == NOW + timedelta(seconds=185)
        count = len(io.calls)
        peer_delay = read_page(db, *peer, 1, reader(io), NOW + timedelta(seconds=126))
        assert isinstance(peer_delay, DeferredRead)
        assert peer_delay.due_at == NOW + timedelta(seconds=185)
        assert len(io.calls) == count


def test_omnisend_clients_share_brand_quota_only(
    customer_engine: Engine, configured: None
) -> None:
    io = RenewalIO("omnisend")
    other_io = RenewalIO("omnisend")
    other_io.account = "other-brand"
    first, second = reader(io), reader(io)
    second.client_id = "second-client"
    unrelated = reader(other_io)
    unrelated.client_id = "second-client"
    first.transport = httpx.MockTransport(lambda _: httpx.Response(429, json={"retryAfter": 180}))
    with Session(customer_engine) as db:
        one = connect(db, io)
        two = connect(db, io, name="second-client")
        other = connect(db, other_io, name="other-brand")
        assert isinstance(read_page(db, *one, 1, first, NOW), DeferredRead)
        delayed = read_page(db, *two, 1, second, NOW + timedelta(seconds=126))
        assert isinstance(delayed, DeferredRead) and delayed.due_at == NOW + timedelta(seconds=180)
        assert not io.calls
        assert isinstance(
            read_page(db, *other, 1, unrelated, NOW + timedelta(seconds=126)), PageDelivery
        )
