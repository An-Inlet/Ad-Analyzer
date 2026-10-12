"""Actual application composition; existing fixture grants, DB/identity and HTTP seams."""

from typing import Any

import httpx
import pytest
from app.api import customer_planning_documents as planning_api
from app.api.customer_meta_reporting import get_meta_reporting_runtime
from app.main import app
from app.meta import selected_runtime
from app.planning_documents.service import PlanningDocumentService
from app.settings import settings
from fastapi.testclient import TestClient

from tests.meta_customer_fixture import MetaFixture
from tests.test_customer_optimization_api import headers


class Assembly:
    def __init__(self, f: MetaFixture, patch: pytest.MonkeyPatch) -> None:
        self.f = f
        self.constructed: list[bool] = []
        self.closed: list[bool] = []
        overrides = {
            k: v
            for k, v in f.alice.app.dependency_overrides.items()
            if k != get_meta_reporting_runtime
        }
        patch.setattr(app, "dependency_overrides", overrides)
        assert get_meta_reporting_runtime not in app.dependency_overrides
        patch.setattr(settings, "customer_meta_reporting_enabled", True)
        patch.setattr(settings, "meta_enabled", True)
        self.alice = TestClient(app, base_url=str(f.alice.base_url))
        self.alice.cookies.update(f.alice.cookies)
        self.f.alice = self.alice
        self.app = app
        # The existing fixture configures the actual canonical private v4 constructor.
        # Also prove that the unchanged production v3 default does not advertise it.
        if settings.customer_planning_policy == "v3":
            self.check_default(patch)

        owner = self

        class Transport(httpx.MockTransport):
            def close(self) -> None:
                owner.closed.append(True)
                super().close()

        def network() -> httpx.BaseTransport:
            self.constructed.append(True)
            return Transport(f.wire)

        patch.setattr(selected_runtime, "network_transport", network)

    def check_default(self, patch: pytest.MonkeyPatch) -> None:
        with patch.context() as scoped:
            scoped.setattr(planning_api, "PlanningDocumentService", PlanningDocumentService)
            default = self.alice.get(
                f"/api/customer/v1/workspaces/{self.f.wid}/planning/plans/capabilities"
            )
            assert (
                default.status_code == 200
                and default.json()["selected_reporting_available"] is False
            )

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self.alice.post(self.f.root + path, headers=headers(self.alice), json=body)
