"""Original-session authority and confirmed-goal ceiling on planning mutations."""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from app.api import customer_mandates as api
from app.customers.access import CustomerPrincipal, guard_customer_mutation
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.goals import service as goals
from app.mandates import service as simulation
from app.mandates.models import Mandate, MandateRevision
from app.settings import Settings
from app.workspaces.models import Workspace
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, select, text, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import ISSUER, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_inlet_customer_journey import JourneyClock
from tests.test_provider_qualification import seeded
from tests.test_shopify_sales import configuration as configuration


def fixture(
    db: Session, configuration: Settings, path: Path
) -> tuple[int, str, str, int, Any, int]:
    wid, _, actor, _ = seeded(db, configuration, path)
    user = db.get(CustomerUser, actor)
    assert user
    user.issuer, user.subject = ISSUER, "review-owner"
    mandate = db.scalar(select(Mandate).where(Mandate.workspace_id == wid))
    assert mandate
    policy = simulation.policy(db, mandate)
    simulation.edit(db, mandate, mandate.revision, policy, actor, JourneyClock.now())
    goal = goals.owned(db, wid, policy.goal_id)
    goal_definition = goals.current(db, goal).definition
    assert goal_definition is not None
    ceiling = goal_definition["budget_micros"]
    db.commit()
    return wid, actor, mandate.id, mandate.revision, policy, ceiling


@pytest.mark.parametrize("change", ["revoked_session", "lost_owner"])
def test_approval_rechecks_after_real_postgres_workspace_wait(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    change: str,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock race")
    with Session(customer_engine) as db:
        wid, actor, mid, revision, _, _ = fixture(db, configuration, tmp_path)
    alice, _, _ = replicas
    alice.app.include_router(api.router)  # type: ignore[attr-defined]
    monkeypatch.setattr(api, "datetime", JourneyClock)
    login(alice, "review-owner:1")
    began = Event()
    backend: list[int] = []

    def before(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: Any
    ) -> None:
        if "FROM workspaces" in statement and "FOR " in statement:
            backend.append(conn.connection.driver_connection.info.backend_pid)
            began.set()

    with Session(customer_engine) as blocker:
        blocker.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
        event.listen(customer_engine, "before_cursor_execute", before)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(
                    alice.post,
                    f"/api/customer/v1/workspaces/{wid}/mandates/{mid}/approve",
                    json={"expected_revision": revision},
                    headers=headers(alice),
                )
                try:
                    assert began.wait(5)
                    deadline = time.monotonic() + 5
                    while not blocker.scalar(
                        text("select cardinality(pg_blocking_pids(:pid))"), {"pid": backend[0]}
                    ):
                        assert time.monotonic() < deadline, (
                            "Request never blocked on workspace lock"
                        )
                        time.sleep(0.01)
                    assert not pending.done()
                    if change == "revoked_session":
                        blocker.execute(
                            update(CustomerSession)
                            .where(CustomerSession.user_id == actor)
                            .values(revoked_at=int(time.time()))
                        )
                    else:
                        blocker.execute(
                            update(CustomerMembership)
                            .where(
                                CustomerMembership.user_id == actor,
                                CustomerMembership.workspace_id == wid,
                            )
                            .values(role="viewer")
                        )
                    blocker.commit()
                finally:
                    blocker.rollback()
                response = pending.result(timeout=10)
        finally:
            event.remove(customer_engine, "before_cursor_execute", before)
    assert response.status_code == (401 if change == "revoked_session" else 403)
    with Session(customer_engine) as db:
        mandate = db.get(Mandate, mid)
        assert mandate and mandate.state == "draft"
        row = db.get(MandateRevision, (mid, revision))
        assert row and row.approved_at is None


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
@pytest.mark.parametrize("operation", ["create", "edit", "approve"])
@pytest.mark.parametrize("amount", ["above", "zero", "ceiling"])
def test_simulation_goal_ceiling_at_each_boundary(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    operation: str,
    amount: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, mid, revision, policy, ceiling = fixture(db, configuration, tmp_path)
        cap = {"above": ceiling + 1, "zero": 0, "ceiling": ceiling}[amount]
        definition = policy.model_copy(
            update={
                "total_cap_micros": cap,
                "per_action_cap_micros": min(cap, policy.per_action_cap_micros),
            }
        )
        mandate = db.get(Mandate, mid)
        assert mandate
        if operation == "create":
            # The fixture's old simulation is removed in this disposable schema so
            # overlap rejection cannot mask the ceiling check.
            db.delete(mandate)
            db.flush()

            def call() -> None:
                simulation.create(db, wid, definition, actor, JourneyClock.now())
        elif operation == "edit":

            def call() -> None:
                simulation.edit(db, mandate, revision, definition, actor, JourneyClock.now())
        else:
            # Model a historical saved draft written before the ceiling repair.
            row = db.get(MandateRevision, (mid, revision))
            assert row
            row.definition = definition.model_dump(mode="json")
            db.flush()

            def call() -> None:
                simulation.approve(db, mandate, revision, actor, JourneyClock.now())

        if amount == "above":
            with pytest.raises(HTTPException, match="confirmed goal budget") as error:
                call()
            assert error.value.status_code == 422
        else:
            call()


@pytest.mark.parametrize("role", ["owner", "admin", "analyst", "viewer"])
def test_existing_role_permissions_and_guard_default(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    role: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, mid, revision, policy, _ = fixture(db, configuration, tmp_path)
        db.execute(
            update(CustomerMembership)
            .where(CustomerMembership.user_id == actor, CustomerMembership.workspace_id == wid)
            .values(role=role)
        )
        db.commit()
    alice, _, provider = replicas
    alice.app.include_router(api.router)  # type: ignore[attr-defined]
    monkeypatch.setattr(api, "datetime", JourneyClock)
    login(alice, "review-owner:1")
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, actor)
        session = db.scalar(select(CustomerSession).where(CustomerSession.user_id == actor))
        assert user and session
        principal = CustomerPrincipal(user, session)
        if role in {"owner", "admin"}:
            assert guard_customer_mutation(db, principal, wid) == role
        else:
            with pytest.raises(HTTPException) as error:
                guard_customer_mutation(db, principal, wid)
            assert error.value.status_code == 403
        db.rollback()
    root = f"/api/customer/v1/workspaces/{wid}/mandates/{mid}"
    response = alice.put(
        root,
        json={"expected_revision": revision, "definition": policy.model_dump(mode="json")},
        headers=headers(alice),
    )
    assert response.status_code == (403 if role == "viewer" else 200)
    if response.status_code == 200:
        revision = response.json()["revision"]
    response = alice.post(
        root + "/approve", json={"expected_revision": revision}, headers=headers(alice)
    )
    assert response.status_code == (200 if role == "owner" else 403)
    response = alice.post(root + "/stop/pause", headers=headers(alice))
    assert response.status_code == (200 if role in {"owner", "admin"} else 403)
