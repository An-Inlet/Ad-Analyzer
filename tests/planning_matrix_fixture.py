"""Independent owned API fixtures with configuration frozen before any matrix request."""

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from app.ads.models import AdvertisingAccount
from app.api.customer import router
from app.api.v1 import router as operator_router
from app.collectors import account_diagnostics
from app.commerce.models import CommerceStore
from app.customers.models import CustomerMembership
from app.main import app
from app.settings import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.owner_review_runtime_fixture import configured_owner_review
from tests.planning_concurrency_harness import Size
from tests.planning_matrix_identity import FixtureIdentity, install_shared_configuration
from tests.test_campaign_review import png
from tests.test_customer_optimization_api import headers
from tests.test_owner_runtime_composition import owner_config


@dataclass
class OwnedMatrixPlan:
    fixture: Any
    client: TestClient
    body: dict[str, Any]
    catalog: dict[str, Any]
    calls: list[tuple[str, str]]
    identity: FixtureIdentity
    url: str = ""

    @property
    def workspace(self) -> int:
        return int(self.fixture.basis.workspace_id)

    def provider_counts(self) -> tuple[int, int]:
        return len(self.calls), len(self.fixture.calls)

    def create(self) -> None:
        root = f"/api/customer/v1/workspaces/{self.workspace}/planning/plans"
        response = self.client.post(root, headers=headers(self.client), json=self.body)
        assert response.status_code == 201, response.status_code
        self.url = root + "/" + response.json()["plan_id"]


def build_pair(
    engine: Engine,
    configuration: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    root: Path,
    size: Size,
    stack: ExitStack,
) -> tuple[OwnedMatrixPlan, OwnedMatrixPlan]:
    owner_config(patch, root / "private-media")
    install_shared_configuration(patch)
    base, _, provider = replicas
    dependencies = dict(base.app.dependency_overrides)
    plans: list[OwnedMatrixPlan] = []
    transports: dict[str, Callable[[], httpx.BaseTransport | None]] = {}
    for identity in (
        FixtureIdentity("matrix-a", "2234567890", size),
        FixtureIdentity("matrix-b", "3234567890", size),
    ):
        replica_app = FastAPI()
        replica_app.include_router(router)
        replica_app.include_router(operator_router)
        replica_app.dependency_overrides = dict(dependencies)
        replica = stack.enter_context(TestClient(replica_app, base_url=str(base.base_url)))
        fixture, body, calls, catalog = configured_owner_review(
            engine,
            configuration,
            (replica, replica, provider),
            patch,
            root / identity.namespace,
            configured_runtime=True,
            identity=identity,
        )
        if size == "large":
            uploaded = replica.post(
                f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/media",
                headers=headers(replica),
                content=png(),
            )
            assert uploaded.status_code == 200, uploaded.status_code
            media = uploaded.json()
            assert media["media_id"] != fixture.basis.media_id
            assert media["sha256"] != fixture.basis.media_sha256
            body["inputs"]["creative"]["media_selections"].append(
                dict(media_id=media["media_id"], expected_sha256=media["sha256"])
            )
            body["inputs"]["maximum_creative_assets"] = 2
            body["inputs"]["product_offer"] += " Second owned image is a synthetic green swatch."
        transports[identity.customer] = account_diagnostics.diagnostic_transport
        plans.append(OwnedMatrixPlan(fixture, replica, body, catalog, calls, identity))
    frozen = MappingProxyType(dict(transports))

    def wire(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            token = parse_qs(request.content.decode())["refresh_token"][0]
            customer = {
                "synthetic-refresh-matrix-a": "2234567890",
                "synthetic-refresh-matrix-b": "3234567890",
            }[token]
        else:
            assert request.url.host == "googleads.googleapis.com"
            customer = request.url.path.split("/customers/", 1)[1].split("/", 1)[0]
        transport = frozen[customer]()
        assert transport is not None
        with transport:
            return transport.handle_request(request)

    patch.setattr(account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire))
    patch.setattr(app, "dependency_overrides", dependencies)
    for plan in plans:
        actual = stack.enter_context(TestClient(app, base_url=str(base.base_url)))
        actual.cookies.update(plan.client.cookies)
        plan.client = actual
    assert plans[0].workspace != plans[1].workspace
    with Session(engine) as db:
        stores = list(db.scalars(select(CommerceStore)))
        assert len(stores) == 2 and len({store.shop_key for store in stores}) == 2
        owners = list(db.scalars(select(CustomerMembership)))
        assert len(owners) == 2 and len({owner.user_id for owner in owners}) == 2
        accounts = list(db.scalars(select(AdvertisingAccount)))
        assert len(accounts) == 2 and len({a.external_account_id for a in accounts}) == 2
    return plans[0], plans[1]


def scoped_counts(engine: Engine, workspace: int) -> dict[str, int]:
    """Counts only; do not retain identifiers, native responses or credential columns."""
    from app.database.session import Base

    with Session(engine) as db:
        return {
            name: int(
                db.scalar(
                    select(func.count()).select_from(table).where(table.c.workspace_id == workspace)
                )
                or 0
            )
            for name, table in sorted(Base.metadata.tables.items())
            if "workspace_id" in table.c
        }
