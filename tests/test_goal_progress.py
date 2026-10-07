from datetime import timedelta
from typing import Any

import pytest
from app.commerce.models import CommerceSnapshot, CommerceStore
from app.goals.models import GoalRevision
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.goal_progress_fixture import ready
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def test_actual_refund_processing_progress_is_signed_current_and_read_only(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
) -> None:
    alice, _, wid, gid, revision, _, _, _ = ready(customer_engine, configuration, replicas)
    with Session(customer_engine) as db:
        count = db.scalar(select(func.count()).select_from(CommerceSnapshot))
    response = alice.get(
        f"/api/customer/v1/workspaces/{wid}/goals/{gid}/progress",
        params={"expected_revision": revision},
    )
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["status"] == "available_as_of" and value["net_sales_micros"] == -10000000
    assert value["target_window"]["time_basis"] == "calendar_month"
    assert value["coverage"]["extent"] == "partial_period"
    assert value["goal_achievement"] == "not_assessed"
    assert response.headers["cache-control"] == "no-store"
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CommerceSnapshot)) == count


@pytest.mark.parametrize(
    "change", ["stale", "import", "disconnected", "draft", "privacy", "history"]
)
def test_unavailable_never_exposes_observed_amount(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    change: str,
) -> None:
    alice, _, wid, gid, revision, sid, _, now = ready(customer_engine, configuration, replicas)
    with Session(customer_engine) as db:
        store = db.get(CommerceStore, sid)
        assert store
        if change == "stale":
            store.last_sync_at = now - timedelta(days=2)
        elif change == "import":
            store.window_end = now
        elif change == "disconnected":
            store.status = "disconnected"
        elif change == "privacy":
            from app.shopify.models import ShopifyConnection
            from app.shopify.privacy import process_event

            source = db.scalar(
                select(ShopifyConnection).where(ShopifyConnection.workspace_id == wid)
            )
            assert source
            process_event(
                db,
                configuration,
                "customers/redact",
                source.shop_domain,
                {"customer": {"id": 100}, "orders_to_redact": [1]},
                now,
            )
        elif change == "history":
            store.covered_from = now - timedelta(hours=1)
        else:
            current = db.get(GoalRevision, (gid, revision))
            assert current
            current.confirmed_at = None
        db.commit()
    result = alice.get(
        f"/api/customer/v1/workspaces/{wid}/goals/{gid}/progress",
        params={"expected_revision": revision},
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "unavailable"
    assert result.json()["net_sales_micros"] is None


def test_revoked_session_while_waiting_for_workspace_cannot_read_amount(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
) -> None:
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from app.customers.models import CustomerSession
    from app.workspaces.models import Workspace
    from sqlalchemy import event, update

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent row-lock wait requires PostgreSQL")
    alice, _, wid, gid, revision, _, principal, _ = ready(customer_engine, configuration, replicas)
    waiting = threading.Event()
    main_thread = threading.get_ident()

    def before_query(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if (
            threading.get_ident() != main_thread
            and "FROM workspaces" in statement
            and ("FOR UPDATE" in statement)
        ):
            waiting.set()

    event.listen(customer_engine, "before_cursor_execute", before_query)
    try:
        with Session(customer_engine) as blocker, ThreadPoolExecutor() as pool:
            blocker.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
            request = pool.submit(
                alice.get,
                f"/api/customer/v1/workspaces/{wid}/goals/{gid}/progress",
                params={"expected_revision": revision},
            )
            assert waiting.wait(10)
            blocker.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == principal.session.digest)
                .values(revoked_at=int(time.time()))
            )
            blocker.commit()
            response = request.result(timeout=10)
            assert response.status_code == 401, response.text
    finally:
        event.remove(customer_engine, "before_cursor_execute", before_query)


@pytest.mark.parametrize("kind,expected", [("zero", 0), ("full_month", -10000000)])
def test_zero_and_full_closed_window(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    expected: int,
) -> None:
    from datetime import UTC, datetime

    from app.api import customer
    from app.goals.progress import read_goal_progress

    # Explicit fixture clock crosses the confirmed target end; real API-issued
    # original session is given a matching test-only lifetime before login.
    monkeypatch.setattr(customer, "TTL_SECONDS", 60 * 86400)
    at = datetime(2026, 11, 2, 12, tzinfo=UTC) if kind == "full_month" else None
    _, provider, wid, gid, revision, _, principal, now = ready(
        customer_engine, configuration, replicas, as_of=at, refund=kind != "zero"
    )
    with Session(customer_engine) as db:
        value = read_goal_progress(db, principal, provider, wid, gid, revision, clock=lambda: now)
        assert value.net_sales_micros == expected
        assert value.goal_achievement == "not_assessed"
        assert value.coverage is not None
        assert value.coverage.extent == ("full_window_as_of" if at else "partial_period")
