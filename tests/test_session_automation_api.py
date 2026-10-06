"""Actual HTTPS session/CSRF and owned Start/status/Stop, no fabricated browser authority."""

from dataclasses import replace
from pathlib import Path

import pytest
from app.api.customer_session_automation import router
from app.customers.models import CustomerUser
from app.publication.execution_models import ProviderExecutionApproval
from app.session_automation import worker
from app.session_automation.models import SessionAutomationRun
from app.session_automation.runtime import get_session_automation_runtime
from app.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import ISSUER, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_session_automation import automatic_fixture
from tests.test_shopify_sales import configuration as configuration


def test_real_owned_start_worker_history_and_new_session_stop(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    alice, bob, identity = replicas
    with Session(customer_engine) as db:
        principal, wid, intent, runtime, server = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        actor = principal.user.id
        user = db.get(CustomerUser, actor)
        assert user
        user.issuer, user.subject = ISSUER, "automation-owner"
        db.commit()
    candidate = replace(runtime.review.candidate, identity=identity)
    runtime = replace(
        runtime,
        review=replace(runtime.review, candidate=candidate),
        selection=replace(runtime.selection, candidate=candidate),
    )
    for client in (alice, bob):
        client.app.include_router(router)  # type: ignore[attr-defined]
        client.app.dependency_overrides[get_session_automation_runtime] = lambda: runtime  # type: ignore[attr-defined]
    assert login(alice, "automation-owner:1") == actor
    login(bob, "other-owner:1")
    base = f"/api/customer/v1/workspaces/{wid}/execution/automation"
    payload = intent.model_dump(mode="json")
    assert alice.post(base + "/start", json=payload).status_code == 403
    assert bob.post(base + "/start", json=payload, headers=headers(bob)).status_code in {403, 404}
    catalog = alice.get(base + "/capabilities")
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["available"]
    assert catalog.json()["mandates"][0]["mandate"] == payload["mandate"]
    started = alice.post(base + "/start", json=payload, headers=headers(alice))
    assert started.status_code == 200, started.text
    identifier = started.json()["run_id"]
    assert started.json()["session_bound"] is True
    history = alice.get(base + "/runs")
    assert history.status_code == 200
    assert history.json()["runs"][0]["run_id"] == identifier
    assert "original_session_digest" not in history.text
    assert worker.advance(customer_engine, wid, identifier, runtime) == "completed"
    assert len(server.writes) == 1
    assert bob.get(base + f"/{identifier}").status_code in {403, 404}
    # Revoke the original session, then log in freshly. Stop is revocation only
    # and must remain accessible to an authorized current owner.
    logout = alice.delete("/api/customer/v1/session", headers=headers(alice))
    assert logout.status_code == 204
    assert login(alice, "automation-owner:2") == actor
    assert alice.get(base + f"/{identifier}").json()["status"] == "blocked"
    stopped = alice.post(base + f"/{identifier}/stop", headers=headers(alice))
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "stopped"
    with Session(customer_engine) as db:
        row = db.get(SessionAutomationRun, identifier)
        assert row and row.stopped_by == actor
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0


def test_default_capabilities_are_honestly_unavailable(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    alice, _, _ = replicas
    with Session(customer_engine) as db:
        principal, wid, _, _, _ = automatic_fixture(
            db, configuration, tmp_path, "google_ads", monkeypatch
        )
        principal.user.issuer, principal.user.subject = ISSUER, "default-owner"
        db.commit()
    alice.app.include_router(router)  # type: ignore[attr-defined]
    login(alice, "default-owner:1")
    response = alice.get(f"/api/customer/v1/workspaces/{wid}/execution/automation/capabilities")
    assert response.status_code == 200, response.text
    assert response.json()["available"] is False
    assert response.json()["policies"] == []
    assert response.json()["mandates"] == []
    assert "factory" not in response.text
