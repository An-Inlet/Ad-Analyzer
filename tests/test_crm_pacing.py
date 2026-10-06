"""Synthetic HTTP, disposable DB replicas; no live CRM or stored profiles."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from app.customer_context.http import CRMRateLimited, CRMReadError, KlaviyoHTTPRead, retry_seconds
from app.customer_context.models import CRMCheckpoint, CRMQuota
from app.customer_context.pacing import (
    DeferredRead,
    PageDelivery,
    acknowledge_page,
    prune_expired_quotas,
    read_page,
)
from app.customers.models import CustomerSession
from app.sources import service as source_service
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_crm_http_runtime import CLIENT, SECRET, TOKEN, ProviderHTTP
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_tiktok_sources import configured as configured


def connect(db: Session, name: str) -> tuple[int, str]:
    wid, _ = setup(db, name)
    integration = WorkspaceIntegration(
        workspace_id=wid,
        provider="klaviyo",
        status="active",
        integration_key="klaviyo",
        display_name="Fixture",
    )
    db.add(integration)
    db.flush()
    cid = uuid4().hex
    db.add(
        SourceConnection(
            id=cid,
            workspace_id=wid,
            integration_id=integration.id,
            provider="klaviyo",
            external_id="account1",
            generation=1,
            status="connected",
            window_start=NOW.date(),
            window_end=NOW.date(),
            encrypted_grant=SourceVault().seal(
                wid,
                "klaviyo",
                cid,
                {"access_token": TOKEN, "expires_at": (NOW + timedelta(days=1)).isoformat()},
            ),
        )
    )
    db.commit()
    return wid, cid


def runtime(io: ProviderHTTP) -> KlaviyoHTTPRead:
    return KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(io), clock=lambda: NOW)


def test_acknowledged_pages_crash_retry_and_private_storage(
    customer_engine: Engine, configured: None
) -> None:
    io = ProviderHTTP("klaviyo")
    with Session(customer_engine) as db:
        wid, cid = connect(db, "first")
        first = read_page(db, wid, cid, 1, runtime(io), NOW)
        assert isinstance(first, PageDelivery)
    # A replica cannot advance an unconsumed page. Expired delivery repeats same cursor.
    with Session(customer_engine) as db:
        assert isinstance(
            read_page(db, wid, cid, 1, runtime(io), NOW + timedelta(seconds=5)), DeferredRead
        )
        repeated = read_page(db, wid, cid, 1, runtime(io), NOW + timedelta(seconds=121))
        assert isinstance(repeated, PageDelivery)
        assert "page[cursor]" not in io.calls[-1].url.params
        with pytest.raises(HTTPException):
            acknowledge_page(db, wid, cid, 1, first.receipt, NOW + timedelta(seconds=122))
        db.rollback()
        acknowledge_page(db, wid, cid, 1, repeated.receipt, NOW + timedelta(seconds=122))
        acknowledge_page(db, wid, cid, 1, repeated.receipt, NOW + timedelta(seconds=122))
        second = read_page(db, wid, cid, 1, runtime(io), NOW + timedelta(seconds=126))
        assert isinstance(second, PageDelivery)
        assert io.calls[-1].url.params["page[cursor]"] == "page2"
        acknowledge_page(db, wid, cid, 1, second.receipt, NOW + timedelta(seconds=127))
        assert read_page(db, wid, cid, 1, runtime(io), NOW + timedelta(seconds=132)) is None
        checkpoint = db.get(CRMCheckpoint, cid)
        assert checkpoint is not None
        stored = repr(checkpoint.__dict__) + repr(db.scalars(select(CRMQuota)).one().__dict__)
        for private in (
            TOKEN,
            "private@example.test",
            "private-list",
            "page2",
            "account1",
            first.receipt,
            second.receipt,
        ):
            assert private not in stored
        assert checkpoint.state == "done"


def test_two_replicas_share_account_quota_across_connections(
    customer_engine: Engine, configured: None
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("real independent row locks require PostgreSQL")
    with Session(customer_engine) as db:
        one = connect(db, "one")
        two = connect(db, "two")
    entered, release = Event(), Event()
    io = ProviderHTTP("klaviyo")

    def held(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/accounts":
            entered.set()
            assert release.wait(10)
        return io(request)

    reader = KlaviyoHTTPRead(CLIENT, SECRET, transport=httpx.MockTransport(held), clock=lambda: NOW)

    def first() -> PageDelivery | DeferredRead | None:
        with Session(customer_engine) as db:
            return read_page(db, *one, 1, reader, NOW)

    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(first)
        assert entered.wait(10)
        try:
            with Session(customer_engine) as db:
                deferred = read_page(db, *two, 1, runtime(io), NOW)
                assert isinstance(deferred, DeferredRead)
        finally:
            release.set()
        assert isinstance(running.result(), PageDelivery)
    with Session(customer_engine) as db:
        assert isinstance(
            read_page(db, *two, 1, runtime(io), NOW + timedelta(seconds=4)), DeferredRead
        )
        assert isinstance(
            read_page(db, *two, 1, runtime(io), NOW + timedelta(seconds=4.1)), PageDelivery
        )
    assert len([r for r in io.calls if r.url.path == "/api/accounts"]) == 2


def test_rate_limit_backoff_and_stale_generation_receipt(
    customer_engine: Engine, configured: None
) -> None:
    io = ProviderHTTP("klaviyo")

    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "180"})

    reader = KlaviyoHTTPRead(
        CLIENT, SECRET, transport=httpx.MockTransport(limited), clock=lambda: NOW
    )
    with Session(customer_engine) as db:
        wid, cid = connect(db, "rate")
        result = read_page(db, wid, cid, 1, reader, NOW)
        assert isinstance(result, DeferredRead) and result.due_at == NOW + timedelta(seconds=180)
        connection = db.get(SourceConnection, cid)
        assert connection is not None and connection.status == "connected"
        assert isinstance(
            read_page(db, wid, cid, 1, runtime(io), NOW + timedelta(seconds=179)), DeferredRead
        )
        assert not io.calls
        page = read_page(db, wid, cid, 1, runtime(io), NOW + timedelta(seconds=180))
        assert isinstance(page, PageDelivery)
        row = db.get(SourceConnection, cid)
        assert row is not None
        row.generation = 2
        db.commit()
        with pytest.raises(HTTPException):
            acknowledge_page(db, wid, cid, 1, page.receipt, NOW + timedelta(seconds=181))
        db.rollback()
        with pytest.raises(HTTPException):
            acknowledge_page(db, wid, cid, 2, page.receipt, NOW + timedelta(seconds=181))


def test_wrong_account_never_delivers_profiles(customer_engine: Engine, configured: None) -> None:
    io = ProviderHTTP("klaviyo")
    io.account = "wrong"
    with Session(customer_engine) as db:
        wid, cid = connect(db, "wrong")
        with pytest.raises(CRMReadError, match="account_mismatch"):
            read_page(db, wid, cid, 1, runtime(io), NOW)
        assert len(io.calls) == 1
        checkpoint = db.get(CRMCheckpoint, cid)
        assert checkpoint is not None and checkpoint.state == "ready"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 60),
        ("bad", 60),
        ("-1", 60),
        ("0", 5),
        ("8", 8),
        ("9999999999", 86400),
        ("Mon, 05 Oct 2026 12:03:00 GMT", 181),
    ],
)
def test_retry_after_is_bounded(value: str | None, expected: int) -> None:
    assert retry_seconds(value, NOW) == expected


def test_oauth_rate_limit_is_typed_without_revocation() -> None:
    reader = KlaviyoHTTPRead(
        CLIENT,
        SECRET,
        transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"Retry-After": "30"})),
        clock=lambda: NOW,
    )
    with pytest.raises(CRMRateLimited) as error:
        reader.refresh("synthetic-refresh", "account1")
    assert error.value.retry_after == 30


def test_generation_change_during_http_cannot_deliver(
    customer_engine: Engine, configured: None
) -> None:
    with Session(customer_engine) as db:
        wid, cid = connect(db, "generation-race")
    io = ProviderHTTP("klaviyo")

    def changed(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/profiles":
            with Session(customer_engine) as replica:
                row = replica.get(SourceConnection, cid)
                assert row is not None
                row.generation += 1
                replica.commit()
        return io(request)

    reader = KlaviyoHTTPRead(
        CLIENT, SECRET, transport=httpx.MockTransport(changed), clock=lambda: NOW
    )
    with Session(customer_engine) as db:
        with pytest.raises(HTTPException, match="connection unavailable"):
            read_page(db, wid, cid, 1, reader, NOW)
        db.rollback()
        checkpoint = db.get(CRMCheckpoint, cid)
        assert checkpoint is not None and checkpoint.state == "reading"
        assert checkpoint.ack_digest is None


def test_other_workspace_has_no_read_or_ack_access(
    customer_engine: Engine, configured: None
) -> None:
    io = ProviderHTTP("klaviyo")
    with Session(customer_engine) as db:
        wid, cid = connect(db, "owner")
        other, _ = connect(db, "other-owner")
        with pytest.raises(HTTPException) as denied:
            read_page(db, other, cid, 1, runtime(io), NOW)
        assert denied.value.status_code == 404 and not io.calls
        db.rollback()
        delivery = read_page(db, wid, cid, 1, runtime(io), NOW)
        assert isinstance(delivery, PageDelivery)
        with pytest.raises(HTTPException) as denied:
            acknowledge_page(db, other, cid, 1, delivery.receipt, NOW)
        assert denied.value.status_code == 404


def test_retry_after_starts_at_response_and_expired_response_is_rejected(
    customer_engine: Engine, configured: None
) -> None:
    with Session(customer_engine) as db:
        wid, cid = connect(db, "slow")
        reader = KlaviyoHTTPRead(
            CLIENT,
            SECRET,
            transport=httpx.MockTransport(
                lambda r: httpx.Response(429, headers={"Retry-After": "30"})
            ),
            clock=lambda: NOW + timedelta(seconds=10),
        )
        deferred = read_page(db, wid, cid, 1, reader, NOW)
        assert isinstance(deferred, DeferredRead)
        assert deferred.due_at == NOW + timedelta(seconds=40)
        io = ProviderHTTP("klaviyo")
        reader = KlaviyoHTTPRead(
            CLIENT,
            SECRET,
            transport=httpx.MockTransport(io),
            clock=lambda: NOW + timedelta(seconds=200),
        )
        with pytest.raises(HTTPException, match="superseded"):
            read_page(db, wid, cid, 1, reader, NOW + timedelta(seconds=40))


def test_disconnect_in_flight_removes_checkpoint_and_rejects_result(
    customer_engine: Engine, configured: None
) -> None:
    with Session(customer_engine) as db:
        wid, cid = connect(db, "disconnect-race")
    io = ProviderHTTP("klaviyo")

    def disconnected(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/profiles":
            with Session(customer_engine) as replica:
                row = replica.get(SourceConnection, cid)
                assert row is not None
                source_service.disconnect(replica, row)
                assert replica.get(CRMCheckpoint, cid) is None
        return io(request)

    reader = KlaviyoHTTPRead(
        CLIENT, SECRET, transport=httpx.MockTransport(disconnected), clock=lambda: NOW
    )
    with Session(customer_engine) as db:
        with pytest.raises(HTTPException):
            read_page(db, wid, cid, 1, reader, NOW)
        db.rollback()
        assert db.get(CRMCheckpoint, cid) is None
        with pytest.raises(HTTPException):
            acknowledge_page(db, wid, cid, 1, "old-receipt", NOW)
        db.rollback()
        with pytest.raises(HTTPException):
            read_page(db, wid, cid, 2, runtime(io), NOW + timedelta(seconds=121))
        db.rollback()
        assert db.get(CRMCheckpoint, cid) is None


def test_reconnect_removes_unacknowledged_cursor(customer_engine: Engine, configured: None) -> None:
    io = ProviderHTTP("klaviyo")
    with Session(customer_engine) as db:
        wid, cid = connect(db, "reconnect")
        delivery = read_page(db, wid, cid, 1, runtime(io), NOW)
        assert isinstance(delivery, PageDelivery)
        sid = db.scalars(select(CustomerSession.digest)).first()
        assert sid is not None
        reader = runtime(io)
        nonce = parse_qs(
            urlsplit(source_service.begin(db, "klaviyo", wid, sid, reader, NOW)).query
        )["state"][0]
        source_service.finish(db, "klaviyo", nonce, sid, "synthetic-code", reader, NOW)
        reconnected = source_service.select_account(db, "klaviyo", nonce, sid, "account1", NOW)
        assert reconnected.id == cid and reconnected.generation == 2
        assert db.get(CRMCheckpoint, cid) is None
        with pytest.raises(HTTPException):
            acknowledge_page(db, wid, cid, 1, delivery.receipt, NOW)


def test_quota_cleanup_is_bounded_and_preserves_leases_and_cooldown(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        db.add_all([CRMQuota(key=f"{i:064x}", due_at=NOW - timedelta(days=2)) for i in range(105)])
        db.add(
            CRMQuota(
                key="x" * 64, due_at=NOW - timedelta(days=2), lease_until=NOW + timedelta(seconds=5)
            )
        )
        db.add(CRMQuota(key="y" * 64, due_at=NOW + timedelta(seconds=5)))
        db.commit()
        assert prune_expired_quotas(db, NOW) == 100
        assert prune_expired_quotas(db, NOW) == 5
        assert len(list(db.scalars(select(CRMQuota)))) == 2
