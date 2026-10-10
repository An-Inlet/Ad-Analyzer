"""Real configured reported reads, current API sessions, immutable advertising history."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from app.jobs.customer_runtime import run_customer_tick
from app.settings import Settings, settings
from sqlalchemy import Engine

from tests.configured_reported_current_fixture import configured_current_reported_customer
from tests.configured_reported_original_fixture import retained_configured_reported_original
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def current_reported_source(
    customer_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    path = tmp_path / "configured-reported-original"
    with retained_configured_reported_original(customer_engine, path) as (engine, ids):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            yield engine, ids, path, clients
        finally:
            try:
                clients[0].close()
            finally:
                clients[1].close()


def read_candidate(
    current_reported_source: Any, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> Any:
    engine, ids, path, clients = current_reported_source
    alice, base, wire, clock, mandate, policy, automatic, _, _ = (
        configured_current_reported_customer(engine, configuration, path, monkeypatch, clients, ids)
    )
    response = alice.post(
        base + "/candidates/reads",
        headers=headers(alice),
        json={
            "mandate_id": mandate["mandate_id"],
            "mandate_revision": mandate["revision"],
            "policy": {"policy_id": policy.policy_id, "revision": policy.revision},
        },
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["job_ids"]) == 1
    job = response.json()["job_ids"][0]
    result = run_customer_tick(engine, configuration=settings, now=clock[0])
    assert result["candidate_reads"] == "completed", result
    response = alice.get(base + "/candidates/reads/" + job)
    assert response.status_code == 200, response.text
    assert response.json()["decision"]["status"] == "suggested", response.text
    assert response.json()["basis_details"]["causal_lift"] == "unavailable"
    return alice, base, wire, clock, mandate, automatic, job, response.json()


@pytest.mark.planning_boundary
def test_current_configured_reported_candidate(
    current_reported_source: Any, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice, base, wire, _, _, _, _, result = read_candidate(
        current_reported_source, configuration, monkeypatch
    )
    reviewed = alice.post(
        base + f"/candidates/results/{result['result_id']}/review",
        headers=headers(alice),
        json={
            "result_id": result["result_id"],
            "expected_decision_digest": result["decision_digest"],
        },
    )
    assert reviewed.status_code == 409
    assert reviewed.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
    assert not wire.meta.posts and not wire.google.writes


def start_body(engine: Engine, wid: int, mandate: Any, automatic: Any) -> dict[str, Any]:
    from app.publication import customer_intents
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        binding = customer_intents.binding(db, wid, mandate["mandate_id"], mandate["revision"])
    return {
        "schema_version": "inlet.start-reported-rule-automation.v1",
        "decision_basis": "operational_reported_efficiency_rule",
        "mandate": binding.model_dump(mode="json"),
        "policy": {"policy_id": automatic.policy_id, "revision": automatic.revision},
        "expected_policy_digest": automatic.digest(),
    }


def revoke(engine: Engine, alice: Any, clock: Any) -> None:
    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        original = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert original
        original.revoked_at = int(clock[0].timestamp())
        db.commit()


def no_automatic_factory(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.production_runtime import reported_automation

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("planning-only automation constructed a factory")

    monkeypatch.setattr(reported_automation, "pinned", forbidden)
    assert reported_automation.run_configured_session_automation(engine, settings) == {}


@pytest.mark.planning_boundary
@pytest.mark.parametrize("change", ["none", "session", "capsule", "source", "unknown"])
def test_current_configured_reported_start_prevented(
    current_reported_source: Any,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    engine, ids, _, _ = current_reported_source
    alice, base, wire, clock, mandate, automatic, _, _ = read_candidate(
        current_reported_source, configuration, monkeypatch
    )
    caps = alice.get(base + "/automation/capabilities")
    assert caps.status_code == 200, caps.text
    assert caps.json()["available"] is False
    assert caps.json()["reason"] == "automation_not_available"
    assert caps.json()["policies"] == caps.json()["mandates"] == []
    body = start_body(engine, ids.workspace_id, mandate, automatic)
    if change == "session":
        revoke(engine, alice, clock)
    elif change == "capsule":
        from app.reported_feedback.models import ReportedWindowCapsule

        with Session(engine) as db:
            capsule = db.scalar(select(ReportedWindowCapsule))
            assert capsule
            db.delete(capsule)
            db.commit()
    elif change == "source":
        from app.production_runtime import candidate_assembly

        monkeypatch.setattr(candidate_assembly, "registered_candidate_source", lambda _: None)
    elif change == "unknown":
        wire.meta.ignore = wire.meta.timeout = True
    response = alice.post(base + "/automation/start", headers=headers(alice), json=body)
    assert response.status_code == (401 if change == "session" else 409), response.text
    assert response.json()["detail"] == (
        "authentication failed"
        if change == "session"
        else "advertising_writes_disabled_in_planning_mvp"
    )
    no_automatic_factory(engine, monkeypatch)
    assert not wire.meta.posts and not wire.google.writes


@pytest.mark.planning_boundary
def test_current_configured_reported_new_session_cannot_adopt(
    current_reported_source: Any, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_customer_identity import login

    engine, ids, _, _ = current_reported_source
    alice, base, wire, clock, mandate, automatic, job, _ = read_candidate(
        current_reported_source, configuration, monkeypatch
    )
    body = start_body(engine, ids.workspace_id, mandate, automatic)
    revoke(engine, alice, clock)
    login(alice, "configured-meta:second")
    response = alice.get(base + "/candidates/reads/" + job)
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "candidate_original_session_required"
    response = alice.post(base + "/automation/start", headers=headers(alice), json=body)
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
    no_automatic_factory(engine, monkeypatch)
    assert not wire.meta.posts and not wire.google.writes
