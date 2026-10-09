"""Current owned completion reads over genuine original creation; no current ad writes."""

import time
from pathlib import Path
from typing import Any, cast

import pytest
from app.api.customer_execution import router
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.publication.execution_models import GoogleOriginalCompletion, ProviderExposureReservation
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.google_created_retained_fixture import GoogleCreatedIds, Mode, retained_google_created
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login, replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize(
    "mode", ["closing", "revoked", "expired", "viewer", "late_expired", "unknown"]
)
def test_current_completion_privacy_and_unknown_hold(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:

    source_mode: Mode = "daily_unknown" if mode == "unknown" else "daily_completed"
    with retained_google_created(customer_engine, tmp_path / "original", source_mode) as (
        engine,
        ids,
    ):
        current_case(engine, ids, monkeypatch, mode)


def current_case(
    customer_engine: Engine, ids: GoogleCreatedIds, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:

    with Session(customer_engine) as db:
        actor = db.get(CustomerUser, ids.actor_id)
        assert actor
        identity = (actor.issuer, actor.subject)
        sessions = set(db.scalars(select(CustomerSession.digest)))
    clients = cast(Any, replicas).__wrapped__(customer_engine, monkeypatch)
    alice, other, _ = clients
    alice.app.include_router(router)
    try:
        assert login(alice, "configured-google:current-completion") == ids.actor_id
        assert digest(alice.cookies[SESSION_COOKIE]) not in sessions
        with Session(customer_engine) as db:
            actor = db.get(CustomerUser, ids.actor_id)
            assert actor and (actor.issuer, actor.subject) == identity
        exercise(alice, customer_engine, ids, monkeypatch, mode)
    finally:
        alice.close()
        other.close()


def exercise(
    alice: Any,
    customer_engine: Engine,
    ids: GoogleCreatedIds,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    from app.publication import google_execution_completion as service
    from app.workspaces.models import Workspace

    base = f"/api/customer/v1/workspaces/{ids.workspace_id}/execution"
    attempt, wid = ids.attempts[0].attempt_id, ids.workspace_id
    session_key = digest(alice.cookies[SESSION_COOKIE])
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, session_key)
        assert session is not None
        member = db.scalar(
            select(CustomerMembership).where(
                CustomerMembership.user_id == session.user_id,
                CustomerMembership.workspace_id == wid,
            )
        )
        assert member is not None
        if mode == "closing":
            workspace = db.get(Workspace, wid)
            assert workspace
            workspace.status = "closing"
        elif mode == "revoked":
            session.revoked_at = int(time.time())
        elif mode == "expired":
            session.expires_at = int(time.time()) - 1
        elif mode == "viewer":
            member.role = "viewer"
        db.commit()
    if mode == "late_expired":
        original = service._read

        def expire(db: Session, *args: Any, **kwargs: Any) -> Any:
            result = original(db, *args, **kwargs)
            session = db.get(CustomerSession, session_key)
            assert session
            session.expires_at = int(time.time()) - 1
            db.flush()
            return result

        monkeypatch.setattr(service, "_read", expire)
    response = alice.get(base + f"/attempts/{attempt}/receipt")
    expected = (
        401 if mode in {"revoked", "expired", "late_expired"} else 403 if mode == "viewer" else 200
    )
    assert response.status_code == expected, response.text
    if expected == 200:
        projection = response.json()["original_operation_completion"]
        assert projection["status"] == ("unavailable" if mode == "unknown" else "completed")
        assert projection["financial_finality"] == "unavailable"
        if mode == "unknown":
            assert projection["commitment"] is None
            denied = alice.post(base + f"/runs/{ids.run_id}/advance", headers=headers(alice))
            assert denied.status_code == 409, denied.text
            assert denied.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
            assert ids.provider_posts == 1
    with Session(customer_engine) as db:
        hold = db.scalar(select(ProviderExposureReservation))
        assert hold and hold.state == "held"
        assert db.scalar(select(func.count()).select_from(GoogleOriginalCompletion)) == (
            0 if mode == "unknown" else 1
        )
