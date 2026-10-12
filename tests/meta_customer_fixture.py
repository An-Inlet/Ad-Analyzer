"""Real customer/session/import/planning basis; only advertising wire is simulated."""

import io
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.ads.models import AdvertisingAccount
from app.api import customer_meta_reporting as api
from app.campaign_performance.models import CurrentPerformance
from app.meta import client as meta_wire
from app.meta import presence_staging
from app.meta.client import MetaClient
from app.meta.models import MetaConnection
from app.meta.selected_customer import MetaCustomerRuntime
from app.meta.selected_profile import EVENT
from app.meta.sync import MetaSyncService
from app.settings import Settings, settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.social_common_basis_fixture import prepare_social_common_basis
from tests.test_customer_optimization_api import headers
from tests.test_meta_connection import campaign, insight, page


class MetaFixture:
    def __init__(
        self, engine: Engine, config: Settings, replicas: Any,
        patch: pytest.MonkeyPatch, path: Path,
        *, configure_planning: bool = True,
    ) -> None:
        if engine.dialect.name == "sqlite":
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        self.engine, self.patch = engine, patch
        self.basis, self.body, self.native_calls = prepare_social_common_basis(
            engine, config, replicas, patch, path, platform="meta_ads",
            configure_planning=configure_planning
        )
        self.alice, self.bob, self.provider = replicas
        self.wid, self.aid = self.basis.workspace_id, self.basis.account_id
        self.now = datetime.now(UTC)
        self.config = settings.model_copy(
            update={
                "meta_enabled": True,
                "meta_client_id": "100000000000001",
                "meta_redirect_uri": "https://example.test/dashboard/meta/callback",
            }
        )
        self.value: str | None = "10"
        self.calls: list[str] = []
        self.hook: Any = lambda: None
        payloads = [
            page(campaign("5", "123")),
            page(),
            page(
                *[
                    insight(
                        account_id="123",
                        campaign_id="5",
                        date_start=(date(2026, 8, 1) + timedelta(days=i)).isoformat(),
                        date_stop=(date(2026, 8, 1) + timedelta(days=i)).isoformat(),
                    )
                    for i in range(61)
                ]
            ),
        ]

        class Opener:
            def open(inner, request: Any, timeout: int) -> io.BytesIO:
                assert request.method == "GET"
                return io.BytesIO(json.dumps(payloads.pop(0)).encode())

        patch.setattr(meta_wire, "build_opener", lambda *_: Opener())
        with Session(engine) as db:
            source = db.scalar(select(MetaConnection).where(MetaConnection.account_id == self.aid))
            assert source
            source.window_start, source.window_end = date(2026, 8, 1), date(2026, 9, 30)
            account = db.get(AdvertisingAccount, self.aid)
            assert account
            # Start a genuine fixture-owned acquisition for this explicit closed window.
            presence_staging.begin_presence(db, source, account, self.now)
            db.commit()
            runner = MetaSyncService(db, self.config, MetaClient(self.config))
            for expected in ("syncing", "syncing", "complete"):
                assert runner.page(self.wid, now=self.now, manual=True)["status"] == expected
            assert db.get(CurrentPerformance, self.aid)
        self.runtime = MetaCustomerRuntime(
            self.config, lambda: httpx.MockTransport(self.wire), lambda: self.now
        )
        for client in (self.alice, self.bob):
            client.app.include_router(api.router)
            client.app.dependency_overrides[api.get_meta_reporting_runtime] = lambda: self.runtime
        self.root = f"/api/customer/v1/workspaces/{self.wid}/reporting/meta"

    def wire(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "GET" and request.url.host == "graph.facebook.com"
        self.calls.append(request.url.path)
        self.hook()
        if not request.url.path.endswith("/insights"):
            return httpx.Response(
                200,
                json={"account_id": "123", "currency": "USD", "timezone_name": "America/New_York"},
            )
        rows = []
        for offset in range(61):
            day = (date(2026, 8, 1) + timedelta(days=offset)).isoformat()
            rows.append(
                dict(
                    account_id="123",
                    campaign_id="5",
                    account_currency="USD",
                    date_start=day,
                    date_stop=day,
                    actions=[]
                    if self.value is None
                    else [{"action_type": EVENT, "value": self.value if offset == 45 else "0"}],
                )
            )
        return httpx.Response(200, json={"data": rows})

    def post(self, path: str, body: dict[str, Any], client: Any = None) -> Any:
        c = client or self.alice
        return c.post(self.root + path, headers=headers(c), json=body)

    def reviewed(self) -> dict[str, Any]:
        result = self.post(
            "/available-range",
            dict(
                account_id=self.aid,
                request_id=uuid4().hex,
                requested_starts_on="2026-08-01",
                requested_ends_on="2026-09-30",
            ),
        )
        assert result.status_code == 200, result.text
        return dict(
            account_id=self.aid,
            basis_digest=result.json()["basis_digest"],
            starts_on="2026-08-01",
            ends_on="2026-09-30",
        )

    def selected(self) -> dict[str, Any]:
        body = self.reviewed()
        options = self.post("/event-options", body)
        assert options.status_code == 200, options.text
        confirm = self.post(
            "/event-selection",
            dict(
                **body,
                option_id=options.json()["options"][0]["option_id"],
                expected_selection_id=None,
                expected_selection_digest=None,
            ),
        )
        assert confirm.status_code == 200, confirm.text
        receipt = confirm.json()
        prepared = self.post(
            "/capture-intents",
            dict(
                **body,
                request_nonce=uuid4().hex,
                expected_selection_id=receipt["selection_id"],
                expected_selection_digest=receipt["selection_digest"],
            ),
        )
        assert prepared.status_code == 200, prepared.text
        return dict(prepared.json())
