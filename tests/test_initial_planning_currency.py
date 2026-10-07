"""Explicit reported CPA is not permission to reinterpret the confirmed goal currency."""

from typing import Any

import pytest
from app.api import customer_initial_planning as api
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.models import CalibrationRow, PreviewRow
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests import test_initial_planning_api as history
from tests import test_meta_connection as meta_fixture
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("report_currency", ["USD", "EUR"])
def test_confirmed_goal_currency_gates_explicit_cpa(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    report_currency: str,
) -> None:
    original_metadata = meta_fixture.metadata
    original_insight = meta_fixture.insight
    # Only provider fixture facts change. Real import/capture/goal/API services run.
    monkeypatch.setattr(
        meta_fixture,
        "metadata",
        lambda number="101": {**original_metadata(number), "currency": report_currency},
    )
    monkeypatch.setattr(
        history,
        "insight",
        lambda **changes: original_insight(account_currency=report_currency, **changes),
    )
    alice, _, provider = replicas
    actor = login(alice, "alice:1")
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, actor)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session
        wid, gid, _, _, runtime, observations = history.ready_history(
            customer_engine, configuration, monkeypatch, CustomerPrincipal(user, session), provider
        )
    alice.app.include_router(api.router)
    alice.app.dependency_overrides[api.get_initial_planning_runtime] = lambda: runtime
    result = alice.post(
        f"/api/customer/v1/workspaces/{wid}/initial-planning/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observations[-1],
            "goal_id": gid,
            "goal_revision": 1,
            "maximum_reported_cpa_micros": 10000000,
        },
    )
    if report_currency == "USD":
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "evaluated"
    else:
        assert result.status_code == 409, result.text
        assert result.json()["detail"] == "initial_objective_currency_mismatch"
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(CalibrationRow)) == 0
            assert db.scalar(select(func.count()).select_from(PreviewRow)) == 0
