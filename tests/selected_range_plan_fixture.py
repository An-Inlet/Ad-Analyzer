"""Actual 61-day raw range and selected APIs plus real owned planning inputs.

Provider traffic is injected MockHTTP; this is not live-provider qualification.
"""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from app.ads.models import AdvertisingAccount
from app.api.customer_reporting_capture import router as capture_router
from app.api.customer_reporting_range import router as range_router
from app.collectors import account_diagnostics
from app.planning_documents.context import ReportingWindow
from app.planning_documents.evidence_local import resolve_source_fences
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.read_context import PlanningReadContexts
from app.planning_documents.selected_inputs import SelectedCaptureSelectorV1
from app.settings import Settings
from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_google_aggregate_range_http import campaign, metric
from tests.test_selected_plan_adapter import prepared


def prepared_range_plan(
    engine: Engine,
    config: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    value: str | None = "10",
    family: Literal["conversions", "all_conversions"] = "conversions",
) -> Any:
    reader, ticket, f, calls = prepared(engine, config, replicas, monkeypatch, selected=False)
    with Session(engine) as db, db.begin():
        account = db.get(AdvertisingAccount, f.aid)
        assert account
        account.time_zone = "America/New_York"
    for client in (f.alice, f.bob):
        cast(FastAPI, client.app).include_router(range_router)
        cast(FastAPI, client.app).include_router(capture_router)

    def reporting(request: httpx.Request) -> httpx.Response:
        f.calls.append("range-plan-read")
        assert request.method == "POST" and request.url.path.endswith("/googleAds:search")
        query = json.loads(request.content)["query"]
        if "FROM conversion_action" in query:
            if "conversion_action.name" in query:
                return cast(httpx.Response, f.handle(request))
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
        if "FROM customer" in query:
            rows: list[dict[str, Any]] = [
                {
                    "customer": {
                        "id": "1234567890",
                        "resourceName": "customers/1234567890",
                        "currencyCode": "USD",
                        "timeZone": "America/New_York",
                    }
                }
            ]
        elif "segments.conversion_action" in query:
            rows = []
            if value is not None:
                for offset in range(61):
                    day = date(2026, 8, 1) + timedelta(days=offset)
                    count_key = "conversions" if family == "conversions" else "allConversions"
                    value_key = (
                        "conversionsValue" if family == "conversions" else "allConversionsValue"
                    )
                    rows.append(
                        {
                            "campaign": {
                                "id": "1",
                                "resourceName": "customers/1234567890/campaigns/1",
                            },
                            "segments": {
                                "date": day.isoformat(),
                                "conversionAction": "customers/1234567890/conversionActions/123",
                            },
                            "metrics": {
                                count_key: value if day == date(2026, 9, 15) else "0",
                                value_key: "0",
                            },
                        }
                    )
        elif "metrics." not in query:
            rows = [campaign()]
        else:
            rows = []
            for offset in range(61):
                day = date(2026, 8, 1) + timedelta(days=offset)
                row = metric(day=day.isoformat())
                if day != date(2026, 9, 15):
                    row["metrics"] = {
                        "impressions": "0",
                        "clicks": "0",
                        "costMicros": "0",
                        "conversions": "0",
                        "conversionsValue": "0",
                    }
                rows.append(row)
        return httpx.Response(200, json={"results": rows})

    f.now = datetime.now(UTC)
    f.runtime = replace(f.runtime, transport=lambda: httpx.MockTransport(reporting))
    range_id = uuid4().hex
    response = f.post(
        "/aggregate-range",
        dict(
            account_id=f.aid,
            request_id=range_id,
            requested_starts_on="2026-08-01",
            requested_ends_on="2026-09-30",
        ),
    )
    assert response.status_code == 200, response.text
    options = f.post("/event-options", {"account_id": f.aid})
    assert options.status_code == 200, options.text
    choice = next(x for x in options.json()["options"] if x["metric_family"] == family)
    selection = f.confirm(choice)
    assert selection.status_code == 200, selection.text
    capture_id = uuid4().hex
    response = f.post(
        "/captures",
        dict(
            account_id=f.aid,
            request_id=capture_id,
            expected_selection_id=selection.json()["selection_id"],
            expected_selection_digest=selection.json()["selection_digest"],
            starts_on="2026-08-01",
            ends_on="2026-09-30",
        ),
    )
    assert response.status_code == 200, response.text
    # Keep the existing actual native catalog transport; return the same observed
    # account timezone as the actual range and selected reporting observations.
    native_transport = account_diagnostics.diagnostic_transport()
    assert isinstance(native_transport, httpx.MockTransport)

    def native(request: httpx.Request) -> httpx.Response:
        response = native_transport.handle_request(request)
        body = response.json()
        for row in body.get("results", []):
            if "customer" in row:
                row["customer"]["timeZone"] = "America/New_York"
        return httpx.Response(response.status_code, json=body)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(native)
    )
    zone = ZoneInfo("America/New_York")
    inputs = ticket.inputs.model_copy(
        update={
            "selected_reporting": (
                SelectedCaptureSelectorV1(account_id=f.aid, capture_id=capture_id),
            ),
            "reporting_window": ReportingWindow(
                starts_at=datetime(2026, 9, 1, tzinfo=zone),
                ends_at_exclusive=datetime(2026, 10, 1, tzinfo=zone),
            ),
            "comparison_window": ReportingWindow(
                starts_at=datetime(2026, 8, 1, tzinfo=zone),
                ends_at_exclusive=datetime(2026, 9, 1, tzinfo=zone),
            ),
        }
    )
    reads = PlanningReadContexts(
        lambda: Session(engine), reader.principal, f.provider, f.wid, f.actor
    )
    with reads.open() as db:
        sources = resolve_source_fences(
            db, principal=reader.principal, accounts=inputs.accounts, now=datetime.now(UTC)
        )
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(
            update={
                "inputs": inputs,
                "sources": sources,
                "privacy_revision": sources[0].privacy_revision,
            }
        )
    )
    return reader, ticket, f, range_id, calls
