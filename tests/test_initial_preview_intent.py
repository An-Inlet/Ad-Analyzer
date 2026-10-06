"""Ordinary stale client selections are controlled conflicts, never server errors."""

from typing import Any

import pytest
from app.api import customer_initial_planning as api
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning import native
from app.initial_planning.models import PreviewRow
from app.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_initial_planning_api import ready_history
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("endpoint", ["native-options", "previews"])
@pytest.mark.parametrize("mismatch", ["account", "goal", "revision"])
def test_stale_native_selection_returns_controlled_conflict_before_io(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    endpoint: str,
    mismatch: str,
) -> None:
    alice, _, provider = replicas
    actor = login(alice, "alice:1")
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, actor)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session
        wid, gid, aid, _, runtime, observations = ready_history(
            customer_engine, configuration, monkeypatch, CustomerPrincipal(user, session), provider
        )
    alice.app.include_router(api.router)
    alice.app.dependency_overrides[api.get_initial_planning_runtime] = lambda: runtime
    root = f"/api/customer/v1/workspaces/{wid}/initial-planning"
    report = alice.post(
        root + "/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observations[-1],
            "goal_id": gid,
            "goal_revision": 1,
            "maximum_reported_cpa_micros": 10000000,
        },
    )
    assert report.status_code == 200, report.text
    choice = {"goal_id": gid, "goal_revision": 1, "account_id": aid, "option_id": "a" * 64}
    choice.update(
        {"account_id": aid + 1}
        if mismatch == "account"
        else {"goal_id": "f" * 32}
        if mismatch == "goal"
        else {"goal_revision": 2}
    )
    native_reads = []

    def no_native_reads(*args: Any, **kwargs: Any) -> Any:
        native_reads.append(True)
        raise AssertionError("Mismatched selection must fail before provider IO")

    monkeypatch.setattr(native, "catalog", no_native_reads)
    with TestClient(
        alice.app, base_url=str(alice.base_url), raise_server_exceptions=False
    ) as client:
        client.cookies.update(alice.cookies)
        response = client.post(
            root + "/" + endpoint,
            headers=headers(client),
            json={
                "calibration_id": report.json()["id"],
                "observation_id": observations[-1],
                "choice": choice,
                "mandate_id": "b" * 32,
                "mandate_revision": 1,
            },
        )
    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": "The selected campaign or goal changed. Refresh and choose again."
    }
    assert native_reads == []
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PreviewRow)) == 0
