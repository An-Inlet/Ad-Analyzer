from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from app.customers.access import CSRF_COOKIE
from app.customers.models import CustomerMembership, CustomerUser, WorkspaceSignup
from app.workspaces.models import Workspace, WorkspaceConfiguration
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import (
    ORIGIN,
    FakeProvider,
    login,
)
from tests.test_customer_identity import (
    customer_engine as customer_engine,
)
from tests.test_customer_identity import (
    replicas as replicas,
)


def signup(client: TestClient, key: str, slug: str = "my-brand") -> Any:
    return client.post(
        "/api/customer/v1/workspaces",
        json={"name": "My Brand", "slug": slug},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": client.cookies[CSRF_COOKIE],
            "Idempotency-Key": key,
        },
    )


def test_atomic_signup_replay_and_cross_user_conflict(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    first, second, _ = replicas
    first_id, second_id = login(first, "alice:1"), login(second, "bob:1")
    key = "signup-request-0001"
    created = signup(first, key)
    assert created.status_code == 201
    assert signup(first, key).json() == created.json()
    assert signup(first, key).status_code == 200
    assert signup(first, key, "different-brand").status_code == 409
    assert signup(second, key).status_code == 409
    other = signup(second, key, "other-brand")
    assert other.status_code == 201
    assert other.json()["id"] != created.json()["id"]
    assert second.get(f"/api/customer/v1/workspaces/{created.json()['id']}").status_code == 404
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(Workspace)) == 2
        assert db.scalar(select(func.count()).select_from(WorkspaceConfiguration)) == 2
        assert db.scalar(select(func.count()).select_from(WorkspaceSignup)) == 2
        for user_id, workspace_id in [
            (first_id, created.json()["id"]),
            (second_id, other.json()["id"]),
        ]:
            owner = db.get(CustomerMembership, (user_id, workspace_id))
            assert owner is not None and owner.role == "owner" and owner.status == "active"


def test_signup_failure_rolls_back_everything_then_retry_succeeds(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    client, _, _ = replicas
    login(client, "alice:1")

    def fail(*args: object) -> None:
        raise RuntimeError("injected ownership insertion failure")

    event.listen(CustomerMembership, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            signup(client, "signup-request-0002")
    finally:
        event.remove(CustomerMembership, "before_insert", fail)
    with Session(customer_engine) as db:
        for model in (Workspace, WorkspaceConfiguration, CustomerMembership, WorkspaceSignup):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert signup(client, "signup-request-0002").status_code == 201


def test_signup_replay_never_reactivates_membership_or_user(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    client, _, _ = replicas
    user_id = login(client, "alice:1")
    workspace_id = signup(client, "signup-request-0003").json()["id"]
    with Session(customer_engine) as db:
        owner = db.get(CustomerMembership, (user_id, workspace_id))
        assert owner is not None
        owner.status = "suspended"
        db.commit()
    assert signup(client, "signup-request-0003").status_code == 404
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, user_id)
        assert user is not None
        user.status = "suspended"
        db.commit()
    assert signup(client, "signup-request-0004", "different-brand").status_code == 401


def test_concurrent_signup_replays_one_workspace(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    first, second, _ = replicas
    login(first, "alice:1")
    second.cookies.update(first.cookies)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(lambda client: signup(client, "concurrent-signup-01"), (first, second))
        )
    assert sorted(r.status_code for r in replies) == [200, 201]
    assert replies[0].json() == replies[1].json()
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(Workspace)) == 1
        assert db.scalar(select(func.count()).select_from(CustomerMembership)) == 1


def test_signup_rejects_unscoped_or_invalid_input_without_rows(
    replicas: tuple[TestClient, TestClient, FakeProvider],
    customer_engine: Engine,
) -> None:
    client, _, _ = replicas
    login(client, "alice:1")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
    assert (
        client.post(
            "/api/customer/v1/workspaces", headers=headers, json={"name": "Brand", "slug": "brand"}
        ).status_code
        == 422
    )
    assert signup(client, "short").status_code == 422
    headers["Idempotency-Key"] = "signup-request-0099"
    assert (
        client.post(
            "/api/customer/v1/workspaces",
            headers=headers,
            json={"name": "Brand", "slug": "brand", "owner_id": "bob"},
        ).status_code
        == 422
    )
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(Workspace)) == 0
