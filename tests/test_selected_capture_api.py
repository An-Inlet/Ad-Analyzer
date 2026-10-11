"""Actual customer acquisition with read-only injected HTTP and retained SQL receipts."""

import json
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from app.api.customer_reporting_capture import router
from app.campaign_performance.selected_models import SelectedCaptureRow, SelectedFactRow
from app.customers.models import CustomerMembership, CustomerSession
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import bump_workspace_export_revision
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import configured as configured
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_customer_api import customer as customer


def prepare(f: CustomerFixture, value: str | None = "10") -> dict[str, Any]:
    for client in (f.alice, f.bob):
        cast(FastAPI, client.app).include_router(router)
    options = f.post("/event-options", {"account_id": f.aid})
    assert options.status_code == 200, options.text
    choice = next(x for x in options.json()["options"] if x["metric_family"] == "conversions")
    selected = f.confirm(choice)
    assert selected.status_code == 200, selected.text
    receipt = selected.json()

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path.endswith("/googleAds:search")
        body = json.loads(request.content)
        query = body["query"]
        if "FROM conversion_action" in query:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "conversionAction": {
                                "resourceName": "customers/1234567890/conversionActions/123",
                                "ownerCustomer": "customers/1234567890",
                            }
                        }
                    ]
                },
            )
        if "segments.conversion_action" in query:
            f.calls.append("selected-search")
            return httpx.Response(
                200,
                json={
                    "results": []
                    if value is None
                    else [
                        {
                            "campaign": {
                                "id": "1",
                                "resourceName": "customers/1234567890/campaigns/1",
                            },
                            "segments": {
                                "date": f.day.isoformat(),
                                "conversionAction": "customers/1234567890/conversionActions/123",
                            },
                            "metrics": {"conversions": value, "conversionsValue": "100"},
                        }
                    ]
                },
            )
        return f.handle(request)

    f.runtime = replace(f.runtime, transport=lambda: httpx.MockTransport(handle))
    return {
        "account_id": f.aid,
        "request_id": uuid4().hex,
        "expected_selection_id": receipt["selection_id"],
        "expected_selection_digest": receipt["selection_digest"],
        "starts_on": f.day.isoformat(),
        "ends_on": f.day.isoformat(),
    }


@pytest.mark.parametrize("value", ["10", "0", None])
def test_real_acquisition_retained_replay_and_presence(
    customer: CustomerFixture, value: str | None
) -> None:
    f = customer
    body = prepare(f, value)
    response = f.post("/captures", body)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["spending_authorized"] is False
    assert receipt["returned_rows"] == (0 if value is None else 1)
    assert "1234567890" not in response.text and "fixture-access" not in response.text
    assert response.headers["cache-control"] == "no-store"
    calls = len(f.calls)
    assert f.post("/captures", body).json() == receipt
    assert len(f.calls) == calls
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 1
        facts = list(db.scalars(select(SelectedFactRow)))
        assert len(facts) == (0 if value is None else 1)
        if facts:
            document = json.loads(facts[0].canonical_json)
            assert document["selected_conversions"]["presence"] == "present"
            assert str(document["selected_conversions"]["value"]) == value
    changed = {**body, "starts_on": (f.day + timedelta(days=1)).isoformat()}
    assert f.post("/captures", changed).status_code in {409, 422}
    assert len(f.calls) == calls


@pytest.mark.parametrize("change", ["session", "role", "source", "privacy", "deadline"])
def test_io_races_publish_no_partial_capture(customer: CustomerFixture, change: str) -> None:
    f = customer
    body = prepare(f)

    def revoke() -> None:
        f.hook = lambda: None
        if change == "deadline":
            f.now += timedelta(seconds=61)
            return
        with Session(f.engine) as db:
            if change == "session":
                session = db.get(CustomerSession, f.sid)
                assert session
                session.revoked_at = int(f.now.timestamp())
            elif change == "role":
                membership = db.get(CustomerMembership, (f.actor, f.wid))
                assert membership
                membership.role = "viewer"
            elif change == "source":
                source = db.get(GoogleCustomerConnection, f.source_id)
                assert source
                source.generation += 1
            else:
                bump_workspace_export_revision(db, f.wid)
            db.commit()

    f.hook = revoke
    response = f.post("/captures", body)
    assert response.status_code in {401, 403, 409}, response.text
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == 0


def test_foreign_and_csrf_and_stale_retained_capture(customer: CustomerFixture) -> None:
    f = customer
    body = prepare(f)
    calls = len(f.calls)
    assert f.post("/captures", body, f.bob).status_code in {403, 404}
    assert f.alice.post(f.base + "/captures", json=body).status_code == 403
    assert len(f.calls) == calls
    response = f.post("/captures", body)
    assert response.status_code == 200, response.text
    with Session(f.engine) as db:
        source = db.get(GoogleCustomerConnection, f.source_id)
        assert source
        source.generation += 1
        db.commit()
    calls = len(f.calls)
    assert f.post("/captures", body).status_code == 409
    assert len(f.calls) == calls


@pytest.mark.parametrize("change", ["grant", "login"])
@pytest.mark.parametrize("operation", ["options", "confirm", "capture"])
def test_final_transaction_rejects_changed_private_source_pin(
    customer: CustomerFixture,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    operation: str,
) -> None:
    from app.campaign_performance.selected_models import EventSelectionRow
    from app.google_connections import selected_acquisition
    from app.google_connections.selected_collection import collect_google_selected_capture
    from app.google_connections.selected_customer import SelectedCustomerService

    f = customer
    body = prepare(f) if operation == "capture" else {"account_id": f.aid}
    if operation == "confirm":
        options = f.post("/event-options", body).json()
        body = {
            **body,
            "option_id": options["options"][0]["option_id"],
            "expected_selection_id": None,
            "expected_selection_digest": None,
        }

    def change_source() -> None:
        with Session(f.engine) as db:
            source = db.get(GoogleCustomerConnection, f.source_id)
            assert source
            if change == "grant":
                source.encrypted_grant = f.runtime.vault.seal(
                    f.wid, source.id, "fixture-replaced-grant"
                )
            else:
                source.login_customer_id = "9876543210"
            db.commit()

    if operation == "capture":
        collect = collect_google_selected_capture

        def collected(*args: Any, **kwargs: Any) -> Any:
            result = collect(*args, **kwargs)
            change_source()
            return result

        monkeypatch.setattr(selected_acquisition, "collect_google_selected_capture", collected)
        suffix = "/captures"
    else:
        catalog = SelectedCustomerService.catalog

        def catalogued(*args: Any, **kwargs: Any) -> Any:
            result = catalog(*args, **kwargs)
            change_source()
            return result

        monkeypatch.setattr(SelectedCustomerService, "catalog", catalogued)
        suffix = "/event-options" if operation == "options" else "/event-selection"
    response = f.post(suffix, body)
    assert response.status_code == 409, response.text
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == 0
        assert db.scalar(select(func.count()).select_from(EventSelectionRow)) == (
            1 if operation == "capture" else 0
        )


@pytest.mark.parametrize("foreign_winner", [False, True])
def test_insert_collision_recovers_only_owned_semantic_winner(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, foreign_winner: bool
) -> None:
    from app.campaign_performance.selected_contracts import SelectedCaptureV1
    from app.campaign_performance.selected_storage import capture_values, store_selected_capture
    from app.google_connections import selected_acquisition
    from app.google_connections.selected_acquisition import CaptureIntent
    from app.google_connections.selected_customer import SelectedCustomerService
    from fastapi import HTTPException
    from sqlalchemy import insert

    f = customer
    body = prepare(f)
    inserted = [False]
    existing = selected_acquisition._existing

    def collision(db: Session, capture: SelectedCaptureV1) -> None:
        # Publish a real winning graph, then provoke a real database header-ID
        # uniqueness error inside a rolled-back savepoint, exactly at insertion.
        store_selected_capture(db, capture)
        inserted[0] = True
        with db.begin_nested():
            db.execute(insert(SelectedCaptureRow).values(**capture_values(capture)))

    def scoped_lookup(
        db: Session, service: SelectedCustomerService, intent: CaptureIntent
    ) -> SelectedCaptureV1 | None:
        if inserted[0] and foreign_winner:
            # Deterministic foreign-winner seam: actual cross-workspace membership
            # denial is covered separately; this exercises post-error translation.
            raise HTTPException(409, "reporting_capture_unavailable")
        return existing(db, service, intent)

    monkeypatch.setattr(selected_acquisition, "store_selected_capture", collision)
    monkeypatch.setattr(selected_acquisition, "_existing", scoped_lookup)
    response = f.post("/captures", body)
    assert response.status_code == (409 if foreign_winner else 200), response.text
    assert inserted[0]
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == (
            0 if foreign_winner else 1
        )
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == (
            0 if foreign_winner else 1
        )


def test_integrity_translation_is_narrow() -> None:
    import sqlite3
    from types import SimpleNamespace

    from app.google_connections.selected_acquisition import _capture_id_collision
    from sqlalchemy.exc import IntegrityError

    class PGError(Exception):
        sqlstate = "23505"
        diag = SimpleNamespace(
            table_name="selected_reporting_captures",
            constraint_name="selected_reporting_captures_pkey",
        )

    original = PGError()
    assert _capture_id_collision(IntegrityError("", {}, original))
    original.diag = SimpleNamespace(table_name="other", constraint_name="other_pkey")
    assert not _capture_id_collision(IntegrityError("", {}, original))
    sql = sqlite3.IntegrityError("UNIQUE constraint failed: selected_reporting_captures.id")
    sql.sqlite_errorcode = 1555
    assert _capture_id_collision(IntegrityError("", {}, sql))
    sql.sqlite_errorcode = 787
    assert not _capture_id_collision(IntegrityError("", {}, sql))
    assert not _capture_id_collision(IntegrityError("", {}, ValueError("unrelated")))


@pytest.mark.parametrize("operation", ["confirm", "capture"])
def test_final_deadline_rolls_back_released_storage_savepoints(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    from app.campaign_performance.selected_models import EventSelectionRow
    from app.campaign_performance.selected_storage import store_selected_capture, store_selection
    from app.google_connections import selected_acquisition, selected_customer

    f = customer
    if operation == "capture":
        body = prepare(f)
        original: Any = store_selected_capture
        module: Any = selected_acquisition
        name, suffix = "store_selected_capture", "/captures"
    else:
        options = f.post("/event-options", {"account_id": f.aid}).json()
        body = {
            "account_id": f.aid,
            "option_id": options["options"][0]["option_id"],
            "expected_selection_id": None,
            "expected_selection_digest": None,
        }
        original = store_selection
        module = selected_customer
        name, suffix = "store_selection", "/event-selection"

    def expire_after_storage(*args: Any, **kwargs: Any) -> None:
        original(*args, **kwargs)
        f.now += timedelta(seconds=61)

    monkeypatch.setattr(module, name, expire_after_storage)
    response = f.post(suffix, body)
    assert response.status_code == 409, response.text
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == 0
        assert db.scalar(select(func.count()).select_from(EventSelectionRow)) == (
            1 if operation == "capture" else 0
        )
