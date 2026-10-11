"""Actual range/catalog/selection/capture APIs feeding SQL-only traffic readers."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from app.ads.models import Campaign, DailyMetric
from app.api.customer_reporting_capture import router
from app.campaign_performance.presence_models import MetricPresenceRow
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.range_receipts import values as receipt_values
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.google_connections import range_publication
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents.context import AccountRef
from app.planning_documents.evidence_local import resolve_source_fences
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.planning_documents.selected_plan_reader import load_selected_plan_graph
from app.planning_documents.selected_traffic import (
    PreparedRawRangeTrafficProjection,
    RawRangeTrafficGraphV1,
)
from app.planning_documents.selected_traffic_reader import (
    KnownTrafficGap,
    load_raw_range_traffic,
    validate_historical_raw_range_traffic,
)
from app.publication.customer_intents import account
from fastapi import FastAPI, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from tests.test_google_range_publication_api import (
    configured as configured,
)
from tests.test_google_range_publication_api import (
    customer as customer,
)
from tests.test_google_range_publication_api import (
    customer_engine as customer_engine,
)
from tests.test_google_range_publication_api import (
    intent,
)
from tests.test_google_range_publication_api import (
    range_customer as range_customer,
)
from tests.test_google_range_publication_api import (
    replicas as replicas,
)
from tests.test_raw_range_traffic import full_transport, window
from tests.test_selected_customer_api import CustomerFixture


def ready(
    f: CustomerFixture, *, sidecar: bool = True, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, dict[str, Any], Any]:
    full_transport(f)
    with monkeypatch.context() as patch:
        if not sidecar:
            patch.setattr(
                range_publication, "store_raw_range_traffic", lambda *args, **kwargs: None
            )
        response = f.post("/aggregate-range", intent(f))
        assert response.status_code == 200, response.text
    for client in (f.alice, f.bob):
        cast(FastAPI, client.app).include_router(router)

    def handle(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if "FROM conversion_action" in query and "conversion_action.name" not in query:
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
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "campaign": {
                                "id": "1",
                                "resourceName": "customers/1234567890/campaigns/1",
                            },
                            "segments": {
                                "date": "2026-09-15",
                                "conversionAction": "customers/1234567890/conversionActions/123",
                            },
                            "metrics": {"conversions": "10", "conversionsValue": "100"},
                        }
                    ]
                },
            )
        response = f.handle(request)
        body = response.json()
        if "FROM customer" in query:
            body["results"][0]["customer"]["timeZone"] = "America/New_York"
        return httpx.Response(200, json=body)

    f.runtime = replace(f.runtime, transport=lambda: httpx.MockTransport(handle))
    options = f.post("/event-options", {"account_id": f.aid})
    assert options.status_code == 200, options.text
    choice = next(x for x in options.json()["options"] if x["metric_family"] == "conversions")
    selected = f.confirm(choice)
    assert selected.status_code == 200, selected.text
    selection = selected.json()
    capture_id = uuid4().hex
    captured = f.post(
        "/captures",
        dict(
            account_id=f.aid,
            request_id=capture_id,
            expected_selection_id=selection["selection_id"],
            expected_selection_digest=selection["selection_digest"],
            starts_on="2026-08-01",
            ends_on="2026-09-30",
        ),
    )
    assert captured.status_code == 200, captured.text
    with Session(f.engine) as db:
        user, session = db.get(CustomerUser, f.actor), db.get(CustomerSession, f.sid)
        assert user and session
        principal = snapshot(CustomerPrincipal(user, session))
        scope = account(db, f.wid, f.aid)
        ref = AccountRef(
            workspace_id=f.wid,
            account_id=f.aid,
            connection_id=scope.account.connection_id,
            platform="google_ads",
            connection_version=scope.connection_version,
        )
    contexts = PlanningReadContexts(
        lambda: Session(f.engine), principal, f.provider, f.wid, f.actor
    )
    with contexts.open() as db:
        source = resolve_source_fences(
            db, principal=principal, accounts=(ref,), now=datetime.now(UTC)
        )[0]
        pin = load_selected_plan_graph(
            db, account=ref, expected_source=source, capture_id=capture_id
        ).pin()
    return contexts, dict(account=ref, expected_source=source, selected_pin=pin), selection


def test_actual_owned_projection_and_prepared_once(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    contexts, args, _ = ready(range_customer, monkeypatch=monkeypatch)
    with contexts.open() as db:
        graph = load_raw_range_traffic(db, **args)
        assert isinstance(graph, RawRangeTrafficGraphV1)
        prepared = PreparedRawRangeTrafficProjection(graph)
        cid = graph.facts[0].campaign_id
        assert prepared.pin.aggregate == args["selected_pin"].aggregate
        assert prepared.snapshot() == graph

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("whole graph reparsed for each requested window")

        with monkeypatch.context() as patch:
            patch.setattr(RawRangeTrafficGraphV1, "model_validate", forbidden)
            for _ in range(200):
                assert prepared.read(cid, window(9)).clicks.value == 100
                assert prepared.read(cid, window(8)).clicks.value == 0
        validate_historical_raw_range_traffic(db, expected_pin=prepared.pin)


def test_validated_absence_and_no_gap_for_stale_selected(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = range_customer
    contexts, args, _ = ready(f, sidecar=False, monkeypatch=monkeypatch)
    with contexts.open() as db:
        gap = load_raw_range_traffic(db, **args)
        assert isinstance(gap, KnownTrafficGap)
        assert gap.reason == "range_traffic_provenance_unavailable"
        assert gap.selected_pin == args["selected_pin"]
        forged = args["selected_pin"].model_copy(update={"campaign_map_digest": "0" * 64})
        with pytest.raises(HTTPException):
            load_raw_range_traffic(db, **{**args, "selected_pin": forged})


def test_actual_legacy_aggregate_has_no_raw_receipt(customer: CustomerFixture) -> None:
    from tests.test_selected_plan_reader import ready as legacy_ready

    contexts, args, _, _ = legacy_ready(customer)
    with contexts.open() as db:
        selected = load_selected_plan_graph(
            db,
            account=args["account"],
            expected_source=args["expected_source"],
            capture_id=args["capture_id"],
        )
        result = load_raw_range_traffic(
            db,
            account=args["account"],
            expected_source=args["expected_source"],
            selected_pin=selected.pin(),
        )
        assert isinstance(result, KnownTrafficGap)
        assert result.reason == "range_traffic_provenance_unavailable"


@pytest.mark.parametrize(
    "change", ["raw_loss", "metrics", "campaign", "duplicate_receipt", "privacy", "receipt_loss"]
)
def test_present_corruption_and_scope_change_abort(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    f = range_customer
    contexts, args, _ = ready(f, monkeypatch=monkeypatch)
    with contexts.open() as db:
        original = load_raw_range_traffic(db, **args)
        assert isinstance(original, RawRangeTrafficGraphV1)
    with Session(f.engine) as db:
        if change == "raw_loss":
            db.execute(delete(MetricPresenceRow))
        elif change == "receipt_loss":
            db.execute(delete(RangeReceiptRow))
        elif change == "metrics":
            db.execute(update(DailyMetric).values(clicks=12345))
        elif change == "campaign":
            db.execute(
                update(Campaign)
                .where(Campaign.account_id == f.aid)
                .values(external_campaign_id="999")
            )
        elif change == "duplicate_receipt":
            receipt = type(original.receipt).model_validate(
                original.receipt.model_copy(update={"request_id": uuid4().hex})
            )
            db.add(RangeReceiptRow(**receipt_values(receipt)))
        else:
            bump_workspace_export_revision(db, f.wid)
        db.commit()
    with contexts.open() as db:
        with pytest.raises(HTTPException):
            load_raw_range_traffic(db, **args)
        if change in {"raw_loss", "campaign", "privacy", "receipt_loss"}:
            with pytest.raises(HTTPException):
                validate_historical_raw_range_traffic(db, expected_pin=original.pin())


def test_history_ignores_later_metrics_and_full_map_but_not_erasure(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = range_customer
    contexts, args, selection = ready(f, monkeypatch=monkeypatch)
    with contexts.open() as db:
        saved = load_raw_range_traffic(db, **args)
        assert isinstance(saved, RawRangeTrafficGraphV1)
    assert (
        f.post(
            "/event-selection/invalidate",
            dict(
                account_id=f.aid,
                expected_selection_id=selection["selection_id"],
                expected_selection_digest=selection["selection_digest"],
            ),
        ).status_code
        == 200
    )
    full_transport(f)
    assert f.post("/aggregate-range", intent(f)).status_code == 200
    with Session(f.engine) as db:
        old = db.scalars(select(Campaign).where(Campaign.account_id == f.aid)).first()
        assert old
        db.add(
            Campaign(
                account_id=f.aid,
                platform=old.platform,
                external_campaign_id="55",
                name="New later campaign",
            )
        )
        db.commit()
    with contexts.open() as db:
        validate_historical_raw_range_traffic(db, expected_pin=saved.pin())
        with pytest.raises(HTTPException):
            load_raw_range_traffic(db, **args)
        bad = saved.pin().model_copy(update={"presence_fact_digest": "f" * 64})
        with pytest.raises(HTTPException):
            validate_historical_raw_range_traffic(db, expected_pin=bad)
    with Session(f.engine) as db:
        bump_workspace_export_revision(db, f.wid)
        db.commit()
    with contexts.open() as db, pytest.raises(HTTPException):
        validate_historical_raw_range_traffic(db, expected_pin=saved.pin())
