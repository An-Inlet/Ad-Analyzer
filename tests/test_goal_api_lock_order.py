"""Real PostgreSQL goal GET/progress lock-order interleave, bounded by DB timeout."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any

import pytest
from app.api.customer_goals import router
from app.database.session import get_db
from app.goals import service
from sqlalchemy import Engine, event, text
from sqlalchemy.orm import Session

from tests.goal_progress_fixture import ready
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def test_goal_get_and_progress_share_workspace_first_order(
    customer_engine: Engine,
    configuration: Any,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent PostgreSQL row-lock interleave")
    alice, _, wid, gid, revision, *_ = ready(customer_engine, configuration, replicas)
    bob = replicas[1]
    bob.cookies.update(alice.cookies)
    bob.app.include_router(router)
    goal_locked, workspace_attempted, workspace_acquired = Event(), Event(), Event()
    goal_had_workspace = Event()

    def database(role: str) -> Any:
        def dependency() -> Any:
            with Session(customer_engine) as db:
                db.info["goal_lock_test_role"] = role
                connection = db.connection()
                connection.info["goal_lock_test_role"] = role
                db.execute(text("SET LOCAL lock_timeout='3s'"))
                try:
                    yield db
                finally:
                    connection.info.pop("goal_lock_test_role", None)

        return dependency

    monkeypatch.setitem(alice.app.dependency_overrides, get_db, database("goal"))
    monkeypatch.setitem(bob.app.dependency_overrides, get_db, database("progress"))

    def before(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if (
            "FROM workspaces" in statement
            and "FOR UPDATE" in statement
            and connection.info.get("goal_lock_test_role") == "progress"
        ):
            workspace_attempted.set()

    def after(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if "FROM workspaces" in statement and "FOR UPDATE" in statement:
            if connection.info.get("goal_lock_test_role") == "goal":
                goal_had_workspace.set()
            elif connection.info.get("goal_lock_test_role") == "progress":
                workspace_acquired.set()

    owned = service.owned

    def fenced_owned(db: Session, workspace_id: int, goal_id: str) -> Any:
        result = owned(db, workspace_id, goal_id)
        if db.info.get("goal_lock_test_role") == "goal":
            goal_locked.set()
            # Fixed code already holds workspace, so let the competing request
            # attempt that lock before completing. Old code has only goal: wait
            # for progress to obtain workspace to exercise the actual cycle.
            waiting = workspace_attempted if goal_had_workspace.is_set() else workspace_acquired
            assert waiting.wait(5), "competing progress never reached workspace boundary"
        return result

    monkeypatch.setattr(service, "owned", fenced_owned)
    event.listen(customer_engine, "before_cursor_execute", before)
    event.listen(customer_engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            goal_response = pool.submit(alice.get, f"/api/customer/v1/workspaces/{wid}/goals/{gid}")
            assert goal_locked.wait(5)
            progress_response = pool.submit(
                bob.get,
                f"/api/customer/v1/workspaces/{wid}/goals/{gid}/progress",
                params={"expected_revision": revision},
            )
            assert goal_response.result(timeout=10).status_code == 200
            assert progress_response.result(timeout=10).status_code == 200
            assert goal_had_workspace.is_set()
    finally:
        workspace_attempted.set()
        workspace_acquired.set()
        event.remove(customer_engine, "before_cursor_execute", before)
        event.remove(customer_engine, "after_cursor_execute", after)


@pytest.mark.parametrize("role", ["owner", "admin", "analyst", "viewer"])
def test_existing_goal_read_and_edit_roles_are_preserved(
    customer_engine: Engine,
    configuration: Any,
    replicas: Any,
    role: str,
) -> None:
    from app.customers.models import CustomerMembership

    from tests.test_customer_optimization_api import headers

    alice, _, wid, gid, revision, _, principal, _ = ready(customer_engine, configuration, replicas)
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (principal.user.id, wid))
        assert member
        member.role = role
        db.commit()
    prefix = f"/api/customer/v1/workspaces/{wid}/goals"
    for path in (
        "",
        f"/{gid}",
        f"/{gid}/history",
        "/usage",
        f"/{gid}/progress?expected_revision={revision}",
    ):
        result = alice.get(prefix + path)
        assert result.status_code == 200, result.text
    result = alice.post(
        prefix,
        headers={**headers(alice), "Idempotency-Key": "role-draft-check"},
        json={"definition": None},
    )
    assert result.status_code == (403 if role == "viewer" else 201), result.text
    denied = alice.post(
        prefix + f"/{gid}/confirm",
        headers=headers(alice),
        json={
            "expected_revision": revision,
            "preview_id": "f" * 32,
            "idempotency_key": "role-confirm-check",
        },
    )
    assert denied.status_code == (403 if role in {"viewer", "analyst"} else 409), denied.text
