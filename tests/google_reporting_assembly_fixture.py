"""Actual application composition with existing owned fixture grants and synthetic HTTP."""

import json
from datetime import date, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_planning_documents as planning_api
from app.api.customer_reporting import get_selected_customer_runtime
from app.google_connections import selected_runtime
from app.main import app
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings, settings
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.q16_fixture import prepare_q16_basis
from tests.test_customer_optimization_api import headers
from tests.test_google_aggregate_range_http import campaign, metric


class GoogleAssembly:
    def __init__(
        self, engine: Engine, config: Settings, replicas: Any, patch: pytest.MonkeyPatch, path: Path
    ) -> None:
        if engine.dialect.name == "sqlite":
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        self.engine, self.patch = engine, patch
        self.native_calls: list[str] = []
        self.basis = prepare_q16_basis(
            engine,
            config,
            replicas,
            patch,
            path,
            branch="privacy",
            native_calls=self.native_calls,
            generation_stage="october",
        )
        original, _, self.provider = replicas
        self.wid, self.aid = self.basis.workspace_id, self.basis.account_id
        self.root = f"/api/customer/v1/workspaces/{self.wid}/reporting/google"
        self.body = self.basis.body
        self.calls: list[str] = []
        self.constructed: list[bool] = []
        self.closed: list[bool] = []
        self.value: str | None = "10"
        self.hook: Any = lambda _: None
        self.provider_status = 200
        patch.setattr(app, "dependency_overrides", dict(original.app.dependency_overrides))
        assert get_selected_customer_runtime not in app.dependency_overrides
        patch.setattr(settings, "customer_google_reporting_enabled", True)
        patch.setattr(settings, "google_customer_runtime_mode", "google_read")
        patch.setattr(settings, "google_customer_api_version", "v24")
        patch.setattr(settings, "google_customer_developer_token", SecretStr("synthetic-developer"))
        patch.setattr(selected_runtime, "SessionLocal", lambda: Session(engine))
        self.alice = TestClient(app, base_url=str(original.base_url))
        self.alice.cookies.update(original.cookies)
        self.app = app
        default = self.alice.get(
            f"/api/customer/v1/workspaces/{self.wid}/planning/plans/capabilities"
        )
        assert default.status_code == 200 and not default.json()["selected_reporting_available"]
        patch.setattr(
            planning_api,
            "PlanningDocumentService",
            partial(
                PlanningDocumentService,
                policy=PlanningCompositionPolicy(
                    version="inlet.descriptive-review.v4",
                    generator_version="inlet.descriptive-planning.v4",
                ),
            ),
        )
        owner = self

        class Transport(httpx.MockTransport):
            ended = False

            def handle_request(self, request: httpx.Request) -> httpx.Response:
                assert not self.ended, "closed transport reused"
                return super().handle_request(request)

            def close(self) -> None:
                assert not self.ended, "transport closed twice"
                self.ended = True
                owner.closed.append(True)
                super().close()

        def network() -> httpx.BaseTransport:
            self.constructed.append(True)
            return Transport(self.wire)

        patch.setattr(selected_runtime, "network_transport", network)

    def wire(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.host + request.url.path)
        assert request.method == "POST"
        self.hook(request)
        if self.provider_status != 200:
            return httpx.Response(self.provider_status, json={"error": "synthetic-private-failure"})
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
        assert request.url.path == "/v24/customers/1234567890/googleAds:search"
        body = json.loads(request.content)
        query = body["query"]
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
            action = {
                "resourceName": "customers/1234567890/conversionActions/123",
                "ownerCustomer": "customers/1234567890",
            }
            if "conversion_action.name" in query:
                action.update(
                    name="Mug purchase", status="ENABLED", category="PURCHASE", type="WEBPAGE"
                )
            rows = [{"conversionAction": action}]
        elif "segments.conversion_action" in query:
            if self.value is not None:
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
                                "conversions": self.value if offset == 45 else "0",
                                "conversionsValue": "0",
                            },
                        }
                    )
        elif "metrics." in query:
            for offset in range(61):
                day = date(2026, 8, 1) + timedelta(days=offset)
                row = metric(day=day.isoformat())
                if offset != 45:
                    row["metrics"] = dict(
                        impressions="0",
                        clicks="0",
                        costMicros="0",
                        conversions="0",
                        conversionsValue="0",
                    )
                rows.append(row)
        else:
            row = campaign()
            row["campaign"]["name"] = "Mug Campaign"
            rows = [row]
        # Actual collector must exhaust both report pages; no all-pages-at-once seam.
        if len(rows) > 31:
            if body.get("pageToken"):
                assert body["pageToken"] == "fixture-page-2"
                return httpx.Response(200, json={"results": rows[31:]})
            return httpx.Response(
                200, json={"results": rows[:31], "nextPageToken": "fixture-page-2"}
            )
        return httpx.Response(200, json={"results": rows})

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self.alice.post(self.root + path, headers=headers(self.alice), json=body)
