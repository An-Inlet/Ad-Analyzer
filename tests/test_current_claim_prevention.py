"""Current claim prevention is separate from original financial highwater commits."""

from collections.abc import Generator
from unittest.mock import Mock

import pytest
from app.customers.models import CustomerMembership
from app.mandates.models import Mandate, MandateAction
from app.mandates.schemas import ClaimInput
from app.settings import Settings, settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.social_producer_retained_fixture import graph
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_mandates import draft, evidence, seed
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("observed", [50, 110])
def test_current_rejected_api_claim_preserves_all_financial_rows(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    observed: int,
) -> None:
    from app.api import customer_mandates as api
    from app.api.customer import router as auth_router
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.database.session import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    clock = Mock()
    clock.now.return_value = NOW
    monkeypatch.setattr(api, "datetime", clock)
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db  # Rejected requests close without any artificial commit.

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    client = TestClient(app, base_url=ORIGIN)
    uid = login(client, "owner:1")
    with Session(customer_engine) as db:
        mandate = seed(db, configuration, approve=False)
        action = draft(db, mandate)
        wid, mid, aid = mandate.workspace_id, mandate.id, action.id
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active"))
        db.commit()
        high = ClaimInput(request_key="high-observation", evidence=evidence(db, mandate, observed))
        lower = ClaimInput(request_key="lower-observation", evidence=evidence(db, mandate, 10))
    path = f"/api/customer/v1/workspaces/{wid}/mandates/{mid}/actions/{aid}/simulate/claim"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
    before = graph(customer_engine)
    try:
        for request in (high, lower):
            response = client.post(path, headers=headers, json=request.model_dump(mode="json"))
            assert response.status_code == 409
            assert response.json() == {"detail": "advertising_writes_disabled_in_planning_mvp"}
            assert graph(customer_engine) == before
        with Session(customer_engine) as db:
            saved, saved_action = db.get(Mandate, mid), db.get(MandateAction, aid)
            assert saved is not None and saved_action is not None
            assert saved.state == "draft" and saved.paused
            assert saved.observed_micros == saved.reserved_micros == 0
            assert saved.actions_used == saved.changes_used == 0
            assert saved_action.state == "eligible"
            assert saved_action.fence is None and saved_action.request_key is None
    finally:
        client.close()
