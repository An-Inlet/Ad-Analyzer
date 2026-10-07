"""Original customer authority must survive an unlocked offline interpretation."""

import time
from typing import Any

import pytest
from app.customers.access import CSRF_COOKIE
from app.customers.models import CustomerMembership, CustomerSession
from app.goals import service
from app.goals.interpreter import GoalInterpreter, get_interpreter
from app.goals.models import GoalUsage
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.goal_progress_fixture import ready
from tests.test_customer_identity import ORIGIN, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("change", ["revoked", "expired", "role", "goal", "source", "privacy"])
def test_interpretation_rechecks_after_adapter(
    customer_engine: Engine, configuration: Any, replicas: Any, change: str
) -> None:
    alice, _, wid, gid, revision, store_id, principal, now = ready(
        customer_engine, configuration, replicas
    )
    calls: list[str] = []

    class Controlled(GoalInterpreter):
        def interpret(self, milestone: str) -> str:
            calls.append(milestone)
            # reserve() has committed: this independent connection changes authority
            # while no customer/workspace/goal locks are held by the adapter caller.
            with Session(customer_engine) as db:
                if change in {"revoked", "expired"}:
                    session = db.get(CustomerSession, principal.session.digest)
                    assert session
                    if change == "revoked":
                        session.revoked_at = int(time.time())
                    else:
                        session.expires_at = int(time.time()) - 1
                elif change == "role":
                    member = db.get(CustomerMembership, (principal.user.id, wid))
                    assert member
                    member.role = "viewer"
                elif change == "source":
                    from app.commerce.models import CommerceStore

                    store = db.get(CommerceStore, store_id)
                    assert store
                    store.status = "disconnected"
                    store.revision += 1
                elif change == "privacy":
                    from app.workspaces.models import Workspace

                    workspace = db.get(Workspace, wid)
                    assert workspace
                    workspace.export_privacy_revision += 1
                else:
                    goal = service.owned(db, wid, gid)
                    service.revise(db, goal, None, principal.user.id, now)
                db.commit()
            return super().interpret(milestone)

    alice.app.dependency_overrides[get_interpreter] = Controlled
    response = alice.post(
        f"/api/customer/v1/workspaces/{wid}/goals/{gid}/interpret",
        headers={"Origin": ORIGIN, "X-CSRF-Token": alice.cookies[CSRF_COOKIE]},
        json={
            "expected_revision": revision,
            "milestone": "A monthly sales goal",
            "idempotency_key": "controlled-interpretation",
        },
    )
    assert (
        response.status_code
        == {
            "revoked": 401,
            "expired": 401,
            "role": 403,
            "goal": 409,
            "source": 409,
            "privacy": 409,
        }[change]
    ), response.text
    assert "needs_clarification" not in response.text
    assert len(calls) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(GoalUsage)) == 1
        usage = db.get(GoalUsage, (wid, "controlled-interpretation"))
        assert usage and usage.reserved_micros == usage.charged_micros == 0
        assert usage.state == "completed"  # Actual call counted; no output persisted.
        if change == "role":
            member = db.get(CustomerMembership, (principal.user.id, wid))
            assert member
            member.role = "owner"
            db.commit()
    # A new authorized session cannot replay/refund a call whose result was denied.
    login(alice, "goal-progress:2")
    retried = alice.post(
        f"/api/customer/v1/workspaces/{wid}/goals/{gid}/interpret",
        headers={"Origin": ORIGIN, "X-CSRF-Token": alice.cookies[CSRF_COOKIE]},
        json={
            "expected_revision": revision,
            "milestone": "A monthly sales goal",
            "idempotency_key": "controlled-interpretation",
        },
    )
    assert retried.status_code == 409, retried.text
    assert len(calls) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(GoalUsage)) == 1


def test_interpretation_rechecks_after_accounting_commit(
    customer_engine: Engine, configuration: Any, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice, _, wid, gid, revision, _, principal, _ = ready(customer_engine, configuration, replicas)
    original_commit = Session.commit
    changed: list[bool] = []

    def commit(db: Session) -> None:
        completed = any(isinstance(row, GoalUsage) and row.state == "completed" for row in db.dirty)
        original_commit(db)
        if completed and not changed:
            changed.append(True)
            with Session(customer_engine) as other:
                session = other.get(CustomerSession, principal.session.digest)
                assert session
                session.revoked_at = int(time.time())
                original_commit(other)

    monkeypatch.setattr(Session, "commit", commit)
    response = alice.post(
        f"/api/customer/v1/workspaces/{wid}/goals/{gid}/interpret",
        headers={"Origin": ORIGIN, "X-CSRF-Token": alice.cookies[CSRF_COOKIE]},
        json={
            "expected_revision": revision,
            "milestone": "A monthly sales goal",
            "idempotency_key": "commit-gap-interpretation",
        },
    )
    assert changed and response.status_code == 401, response.text
    assert "needs_clarification" not in response.text
    with Session(customer_engine) as db:
        usage = db.get(GoalUsage, (wid, "commit-gap-interpretation"))
        assert usage and usage.state == "completed"
        assert usage.reserved_micros == usage.charged_micros == 0
