"""Account cooldown survives a concurrent customer lifecycle transition."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import httpx
import pytest
from app.customer_context.models import CRMCheckpoint, CRMQuota
from app.customer_context.pacing import DeferredRead, PageDelivery, read_page
from app.shopify.security import utc
from app.sources import service
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_crm_renewal import RenewalIO, connect, reader, tokens
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_tiktok_sources import configured as configured


@pytest.mark.parametrize("successor", [False, True])
@pytest.mark.parametrize("phase", ["read", "issue", "proof"])
@pytest.mark.parametrize("lifecycle", ["reconnect", "disconnect"])
def test_late_rate_limit_survives_lifecycle(
    customer_engine: Engine, configured: None, phase: str, lifecycle: str, successor: bool
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent transactions and row locks require PostgreSQL")
    io = RenewalIO("klaviyo")
    other_io = RenewalIO("klaviyo")
    other_io.account = "unrelated-account"
    with Session(customer_engine) as db:
        wid, cid = connect(db, io, expiry=NOW.isoformat() if phase != "read" else None)
        peer = connect(db, io, name="peer")
        other = connect(db, other_io, name="other")
        if phase == "proof":
            read_page(db, wid, cid, 1, reader(io), NOW)
    entered, release = Event(), Event()

    def held(request: httpx.Request) -> httpx.Response:
        targeted = (
            request.url.path.endswith("/token")
            if phase == "issue"
            else request.url.path.endswith("/accounts")
        )
        if targeted:
            entered.set()
            assert release.wait(20)
            return httpx.Response(429, headers={"Retry-After": "3600"})
        return io(request)

    runtime = reader(io)
    runtime.transport = httpx.MockTransport(held)

    def worker() -> None:
        with Session(customer_engine) as db, pytest.raises(HTTPException):
            read_page(db, wid, cid, 1, runtime, NOW + timedelta(seconds=5))

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        assert entered.wait(10)
        try:
            with Session(customer_engine) as db:
                row = service.owned(db, wid, "klaviyo", cid)
                if lifecycle == "disconnect":
                    service.disconnect(db, row)
                else:
                    service.discard_context_checkpoint(db, row)
                    row.generation += 1
                    row.encrypted_grant = SourceVault().seal(
                        wid, "klaviyo", cid, {"access_token": "new-grant", "expires_at": None}
                    )
                    db.commit()
                if successor:
                    limit = db.scalars(select(CRMQuota)).one()
                    limit.fence = "successor-worker"
                    limit.lease_until = NOW + timedelta(seconds=500)
                    db.commit()
        finally:
            release.set()
        future.result(timeout=20)
    with Session(customer_engine) as db:
        limit = db.scalars(select(CRMQuota)).one()
        assert utc(limit.due_at) >= NOW + timedelta(seconds=3605)
        if successor:
            assert limit.fence == "successor-worker"
            assert limit.lease_until and utc(limit.lease_until) == NOW + timedelta(seconds=500)
        else:
            assert limit.fence is None and limit.lease_until is None
        final_row = db.get(SourceConnection, cid)
        assert final_row and final_row.generation == 2
        assert db.get(CRMCheckpoint, cid) is None
        if lifecycle == "reconnect":
            assert tokens(db, wid, cid, "klaviyo")["access_token"] == "new-grant"
        else:
            assert final_row.encrypted_grant is None
        count = len(io.calls)
        delayed = read_page(db, *peer, 1, reader(io), NOW + timedelta(seconds=126))
        assert isinstance(delayed, DeferredRead)
        assert delayed.due_at >= NOW + timedelta(seconds=3605)
        assert len(io.calls) == count
        assert isinstance(
            read_page(db, *other, 1, reader(other_io), NOW + timedelta(seconds=126)), PageDelivery
        )
