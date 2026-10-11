"""Frozen Common Basis through real selected APIs; provider IO is MockHTTP only."""

import json
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.api import customer_planning_documents as planning
from app.api.customer_reporting import get_selected_customer_runtime, router
from app.api.customer_reporting_capture import router as capture_router
from app.api.customer_reporting_range import router as range_router
from app.customers.access import SESSION_COOKIE
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.security import Vault
from app.google_connections.selected_customer import SelectedCustomerRuntime
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.q16_fixture import Q16Basis, prepare_q16_basis
from tests.test_customer_optimization_api import headers
from tests.test_google_aggregate_range_http import campaign, metric


def prepare_selected_common_basis(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    artifacts: Path,
    *,
    value: str | None,
) -> tuple[Q16Basis, dict[str, Any], list[str]]:
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    calls: list[str] = []
    basis = prepare_q16_basis(
        engine,
        config,
        replicas,
        patch,
        artifacts,
        branch="privacy",
        native_calls=calls,
        generation_stage="october",
    )
    alice, _, _ = replicas
    original_cookie = alice.cookies[SESSION_COOKIE]

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.method == "POST"
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json={
                    "access_token": "synthetic-access",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        assert request.url.host == "googleads.googleapis.com"
        assert request.url.path.endswith("/googleAds:search")
        query = json.loads(request.content)["query"]
        rows: list[dict[str, Any]] = []
        if "FROM customer" in query:
            rows = [
                {
                    "customer": {
                        "id": "1234567890",
                        "resourceName": "customers/1234567890",
                        "currencyCode": "USD",
                        "timeZone": "America/New_York",
                    }
                }
            ]
        elif "FROM conversion_action" in query:
            rows = [
                {
                    "conversionAction": {
                        "resourceName": "customers/1234567890/conversionActions/123",
                        "ownerCustomer": "customers/1234567890",
                        "name": "Mug purchase",
                        "status": "ENABLED",
                        "category": "PURCHASE",
                        "type": "WEBPAGE",
                    }
                }
            ]
            if "conversion_action.name" not in query:
                rows = [
                    {
                        "conversionAction": {
                            "resourceName": "customers/1234567890/conversionActions/123",
                            "ownerCustomer": "customers/1234567890",
                        }
                    }
                ]
        elif "segments.conversion_action" in query:
            if value is not None:
                for offset in range(61):
                    day = date(2026, 8, 1) + timedelta(days=offset)
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
                                "conversions": value if day == date(2026, 9, 15) else "0",
                                "conversionsValue": "0",
                            },
                        }
                    )
        elif "metrics." in query:
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
        else:
            row = campaign()
            row["campaign"]["name"] = "Mug Campaign"
            rows = [row]
        return httpx.Response(200, json={"results": rows})

    with httpx.MockTransport(wire) as oauth_transport:
        oauth = GoogleHTTPRead(
            "synthetic-client",
            SecretStr("synthetic-secret"),
            SecretStr("synthetic-developer"),
            "v24",
            transport=oauth_transport,
        )
        runtime = SelectedCustomerRuntime(
            lambda: Session(engine),
            oauth,
            Vault(),
            lambda: httpx.MockTransport(wire),
            lambda: datetime.now(UTC),
        )
        alice.app.include_router(router)
        alice.app.include_router(range_router)
        alice.app.include_router(capture_router)
        alice.app.dependency_overrides[get_selected_customer_runtime] = lambda: runtime
        root = f"/api/customer/v1/workspaces/{basis.workspace_id}/reporting/google"

        def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
            response = alice.post(root + path, headers=headers(alice), json=body)
            assert response.status_code == 200, response.text
            result: dict[str, Any] = response.json()
            return result

        post(
            "/aggregate-range",
            dict(
                account_id=basis.account_id,
                request_id=uuid4().hex,
                requested_starts_on="2026-08-01",
                requested_ends_on="2026-09-30",
            ),
        )
        options = post("/event-options", dict(account_id=basis.account_id))
        option = next(x for x in options["options"] if x["metric_family"] == "conversions")
        selection = post(
            "/event-selection",
            dict(
                account_id=basis.account_id,
                option_id=option["option_id"],
                expected_selection_id=None,
                expected_selection_digest=None,
            ),
        )
        capture_id = uuid4().hex
        post(
            "/captures",
            dict(
                account_id=basis.account_id,
                request_id=capture_id,
                expected_selection_id=selection["selection_id"],
                expected_selection_digest=selection["selection_digest"],
                starts_on="2026-08-01",
                ends_on="2026-09-30",
            ),
        )
    alice.app.dependency_overrides.pop(get_selected_customer_runtime)
    patch.setattr(
        planning,
        "PlanningDocumentService",
        partial(
            PlanningDocumentService,
            policy=PlanningCompositionPolicy(
                version="inlet.descriptive-review.v4",
                generator_version="inlet.descriptive-planning.v4",
            ),
        ),
    )
    body = basis.body
    body["inputs"]["selected_reporting"] = [
        dict(account_id=basis.account_id, capture_id=capture_id)
    ]
    assert alice.cookies[SESSION_COOKIE] == original_cookie
    return basis, body, calls
