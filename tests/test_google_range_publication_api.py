"""Actual customer API/SQL range publication through raw MockHTTP, never live reads."""

import json
from collections.abc import Iterator
from dataclasses import replace
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from app.ads.models import AdvertisingAccount, DailyMetric, JobRun
from app.api.customer_reporting_range import router
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.range_receipts import read_range_receipt
from app.customers.models import CustomerMembership, CustomerSession
from app.google_connections.models import GoogleCustomerConnection, GoogleImportCompletion
from app.google_connections.security import Vault
from app.lifecycle.privacy import bump_workspace_export_revision
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.test_google_aggregate_range_http import campaign, metric
from tests.test_selected_customer_api import (
    CustomerFixture,
)
from tests.test_selected_customer_api import (
    configured as configured,
)
from tests.test_selected_customer_api import (
    customer as customer,
)
from tests.test_selected_customer_api import (
    customer_engine as customer_engine,
)
from tests.test_selected_customer_api import (
    replicas as replicas,
)


@pytest.fixture
def range_customer(customer: CustomerFixture) -> Iterator[CustomerFixture]:
    f = customer
    with Session(f.engine) as db:
        account = db.get(AdvertisingAccount, f.aid)
        assert account
        account.time_zone = "America/New_York"
        db.commit()

    def handle(req: httpx.Request) -> httpx.Response:
        f.calls.append(req.url.host or "")
        assert req.method == "POST" and req.url.path == "/v24/customers/1234567890/googleAds:search"
        query = json.loads(req.content)["query"]
        if "FROM customer" in query:
            row = {
                "customer": {
                    "id": "1234567890",
                    "resourceName": "customers/1234567890",
                    "currencyCode": "USD",
                    "timeZone": "America/New_York",
                }
            }
        elif "metrics." not in query:
            row = campaign()
        else:
            assert "BETWEEN '2026-08-01' AND '2026-09-30'" in query
            return httpx.Response(
                200, json={"results": [metric(day="2026-08-01"), metric(day="2026-09-30")]}
            )
        return httpx.Response(200, json={"results": [row]})

    f.runtime = replace(f.runtime, transport=lambda: httpx.MockTransport(handle))
    for client in (f.alice, f.bob):
        cast(FastAPI, client.app).include_router(router)
    yield f


def intent(f: CustomerFixture) -> dict[str, Any]:
    return dict(
        account_id=f.aid,
        request_id=uuid4().hex,
        requested_starts_on="2026-08-01",
        requested_ends_on="2026-09-30",
    )


def scheduler(f: CustomerFixture) -> tuple[Any, ...]:
    with Session(f.engine) as db:
        source = db.get(GoogleCustomerConnection, f.source_id)
        assert source
        return tuple(
            getattr(source, name)
            for name in (
                "backfill_through",
                "history_floor",
                "phase",
                "window_start",
                "window_end",
                "cursor",
                "staged",
                "next_attempt_at",
            )
        )


def counts(f: CustomerFixture) -> tuple[int, ...]:
    with Session(f.engine) as db:
        return tuple(
            db.scalar(select(func.count()).select_from(model)) or 0
            for model in (
                DailyMetric,
                JobRun,
                PerformanceCompletion,
                RangeReceiptRow,
                GoogleImportCompletion,
            )
        )


def test_actual_range_receipt_and_no_http_replay(range_customer: CustomerFixture) -> None:
    f = range_customer
    before = scheduler(f)
    old = counts(f)
    body = intent(f)
    response = f.post("/aggregate-range", body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["row_count"] == 2 and not result["spending_authorized"]
    assert response.headers["cache-control"] == "no-store"
    assert scheduler(f) == before
    assert counts(f)[1:] == (old[1] + 1, old[2] + 1, 1, old[4])
    with Session(f.engine) as db:
        receipt = read_range_receipt(db, f.wid, f.aid, body["request_id"])
        assert receipt.requested_starts_on.isoformat() == "2026-08-01"
        assert receipt.requested_ends_on.isoformat() == "2026-09-30"
        assert receipt.final_scope.time_zone == "America/New_York"
        job = db.get(JobRun, receipt.job_id)
        assert job and job.job_name == "google_customer_range_read"
        assert job.workspace_id == f.wid and job.account_id == f.aid
        assert receipt.completion_id == result["completion_id"]
    issued = len(f.calls)
    replay = f.post("/aggregate-range", body)
    assert replay.status_code == 200 and replay.json() == result
    assert len(f.calls) == issued
    assert (
        f.post("/aggregate-range", {**body, "requested_starts_on": "2026-08-02"}).status_code == 409
    )
    assert len(f.calls) == issued
    assert "fixture-access" not in response.text and "customers/123" not in response.text


@pytest.mark.parametrize("change", ["grant", "login", "schedule", "privacy", "role", "session"])
def test_oauth_races_leave_no_publication(range_customer: CustomerFixture, change: str) -> None:
    f = range_customer
    initial = counts(f)

    def mutate() -> None:
        with Session(f.engine) as db:
            source = db.get(GoogleCustomerConnection, f.source_id)
            assert source
            if change == "grant":
                source.encrypted_grant = Vault().seal(f.wid, source.id, "other")
            if change == "login":
                source.login_customer_id = "9999999999"
            if change == "schedule":
                source.phase = "refresh"
            if change == "privacy":
                bump_workspace_export_revision(db, f.wid)
            if change == "role":
                member = db.get(CustomerMembership, (f.actor, f.wid))
                assert member
                member.role = "viewer"
            if change == "session":
                session = db.get(CustomerSession, f.sid)
                assert session
                session.revoked_at = 1
            db.commit()

    f.hook = mutate
    response = f.post("/aggregate-range", intent(f))
    assert response.status_code in {401, 403, 409}
    assert counts(f) == initial


def test_pending_foreign_csrf_and_stale_receipt_do_not_fetch(
    range_customer: CustomerFixture,
) -> None:
    f = range_customer
    body = intent(f)
    assert f.post("/aggregate-range", body, f.bob).status_code == 404
    assert f.alice.post(f.base + "/aggregate-range", json=body).status_code == 403
    with Session(f.engine) as db:
        source = db.get(GoogleCustomerConnection, f.source_id)
        assert source
        source.cursor = "pending"
        db.commit()
    assert f.post("/aggregate-range", body).status_code == 409
    assert not f.calls
    with Session(f.engine) as db:
        source = db.get(GoogleCustomerConnection, f.source_id)
        assert source
        source.cursor = None
        db.commit()
    assert f.post("/aggregate-range", body).status_code == 200
    with Session(f.engine) as db:
        pointer = db.get(CurrentPerformance, f.aid)
        assert pointer
        db.delete(pointer)
        db.commit()
    issued = len(f.calls)
    assert f.post("/aggregate-range", body).status_code == 409
    assert len(f.calls) == issued


@pytest.mark.parametrize("phase", ["before_receipt", "after_receipt"])
def test_failure_after_publication_rolls_back_entire_graph(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    from app.google_connections import range_publication

    f = range_customer
    initial, state = counts(f), scheduler(f)

    def fail(db: Session, receipt: Any) -> None:
        raise ValueError("fixture storage failure")

    if phase == "before_receipt":
        monkeypatch.setattr(range_publication, "store_range_receipt", fail)
    else:
        actual = read_range_receipt

        def reject_retained(*args: Any, **kwargs: Any) -> Any:
            actual(*args, **kwargs)
            raise ValueError("fixture post-savepoint failure")

        monkeypatch.setattr(range_publication, "read_range_receipt", reject_retained)
    assert f.post("/aggregate-range", intent(f)).status_code == 409
    assert counts(f) == initial and scheduler(f) == state


@pytest.mark.parametrize("change", ["grant", "login", "schedule", "pointer", "privacy"])
def test_after_last_http_races_leave_no_publication(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from app.google_connections.range_http import GoogleAggregateRangeHTTP

    f = range_customer
    initial = counts(f)
    acquire = GoogleAggregateRangeHTTP.__call__

    def delayed(self: Any, request: Any) -> Any:
        result = acquire(self, request)
        with Session(f.engine) as db:
            source = db.get(GoogleCustomerConnection, f.source_id)
            assert source
            if change == "grant":
                source.encrypted_grant = Vault().seal(f.wid, source.id, "changed-after-read")
            elif change == "login":
                source.login_customer_id = "9999999999"
            elif change == "schedule":
                source.cursor = "new-import"
            elif change == "pointer":
                pointer = db.get(CurrentPerformance, f.aid)
                assert pointer
                db.delete(pointer)
            else:
                bump_workspace_export_revision(db, f.wid)
            db.commit()
        return result

    monkeypatch.setattr(GoogleAggregateRangeHTTP, "__call__", delayed)
    assert f.post("/aggregate-range", intent(f)).status_code == 409
    assert counts(f) == initial


def test_concurrent_same_request_winner_is_replayed_without_second_publication(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.google_connections.range_http import GoogleAggregateRangeHTTP

    f = range_customer
    body = intent(f)
    before = counts(f)
    acquire = GoogleAggregateRangeHTTP.__call__
    winner: dict[str, Any] = {}
    competing = False

    def delayed(self: Any, request: Any) -> Any:
        nonlocal competing
        result = acquire(self, request)
        if not competing:
            competing = True
            response = f.post("/aggregate-range", body)
            assert response.status_code == 200, response.text
            winner.update(response.json())
        return result

    monkeypatch.setattr(GoogleAggregateRangeHTTP, "__call__", delayed)
    response = f.post("/aggregate-range", body)
    assert response.status_code == 200 and response.json() == winner
    assert counts(f)[1:] == (before[1] + 1, before[2] + 1, 1, before[4])
