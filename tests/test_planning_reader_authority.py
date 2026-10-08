"""Actual SQL transactions and identity/native callbacks across planning reads."""

import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from app.collectors import account_diagnostics
from app.customers.models import CustomerSession, CustomerUser
from app.planning_documents import evidence_adapter
from app.planning_documents.evidence_local import recheck_local_sources
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, event, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_identity_and_native_io_are_outside_every_actual_transaction(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    reader, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    active: set[int] = set()
    identity_count = 0
    native_count = 0
    locks = 0

    def begin(connection: Any) -> None:
        active.add(id(connection))

    def end(connection: Any) -> None:
        active.discard(id(connection))

    def statement(
        connection: Any, cursor: Any, sql: str, parameters: Any, context: Any, many: bool
    ) -> None:
        nonlocal locks
        compiled = getattr(context, "compiled", None)
        if getattr(getattr(compiled, "statement", None), "_for_update_arg", None) is not None:
            locks += 1

    original_identity = reader.provider.check_active
    transport = account_diagnostics.diagnostic_transport()

    def check(subject: str, authenticated_at: int) -> None:
        nonlocal identity_count
        assert not active, "identity IO began while a SQL transaction remained open"
        identity_count += 1
        original_identity(subject, authenticated_at)

    def native(request: httpx.Request) -> httpx.Response:
        nonlocal native_count
        assert not active, "native IO began while a SQL transaction remained open"
        native_count += 1
        return transport.handle_request(request)

    monkeypatch.setattr(reader.provider, "check_active", check)
    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(native)
    )
    hooks: list[tuple[str, Callable[..., Any]]] = [
        ("begin", begin),
        ("commit", end),
        ("rollback", end),
        ("before_cursor_execute", statement),
    ]
    for name, callback in hooks:
        event.listen(customer_engine, name, callback)
    try:
        bundle = reader.collect(ticket)
        assert bundle.performance and bundle.commerce
        assert identity_count > 5 and native_count > 1 and locks > identity_count
        assert not active
    finally:
        for name, callback in hooks:
            event.remove(customer_engine, name, callback)


@pytest.mark.parametrize("change", ["subject", "issuer", "authenticated_at", "revoked", "expired"])
def test_detached_original_identity_race_before_locks_denied(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    reader, ticket, _, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    original = reader.provider.check_active

    def change_during_refresh(subject: str, authenticated_at: int) -> None:
        original(subject, authenticated_at)
        with Session(customer_engine) as db:
            if change in {"subject", "issuer"}:
                db.execute(
                    update(CustomerUser)
                    .where(CustomerUser.id == ticket.actor_id)
                    .values(**{change: "changed"})
                )
            else:
                values = (
                    {"authenticated_at": authenticated_at + 1}
                    if change == "authenticated_at"
                    else {"revoked_at": 1}
                    if change == "revoked"
                    else {"expires_at": 1}
                )
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == ticket.session_digest)
                    .values(**values)
                )
            db.commit()

    monkeypatch.setattr(reader.provider, "check_active", change_during_refresh)
    with pytest.raises(HTTPException):
        reader.collect(ticket)
    assert not calls


def test_final_five_second_age_after_source_work_is_not_refreshed(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    real_monotonic = time.monotonic
    offset = [0.0]
    monkeypatch.setattr(
        "app.planning_documents.authority.time.monotonic", lambda: real_monotonic() + offset[0]
    )
    original = recheck_local_sources

    def late(*args: Any, **kwargs: Any) -> None:
        original(*args, **kwargs)
        offset[0] += 5.001

    monkeypatch.setattr(evidence_adapter, "recheck_local_sources", late)
    with pytest.raises(HTTPException) as error:
        reader.collect(ticket)
    assert error.value.detail == "planning_authority_expired"


def test_context_callback_cannot_escape_or_refresh_under_locks(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    calls = []
    original = reader.provider.check_active

    def check(subject: str, authenticated_at: int) -> None:
        calls.append(subject)
        original(subject, authenticated_at)

    monkeypatch.setattr(reader.provider, "check_active", check)
    contexts = PlanningReadContexts(
        reader.sessions,
        reader.principal,
        reader.provider,
        ticket.inputs.workspace_id,
        ticket.actor_id,
    )
    with contexts.open() as db:
        with pytest.raises(HTTPException), contexts.open():
            pytest.fail("nested context admitted")
        contexts.authorize(db, ticket.inputs.workspace_id, ticket.actor_id)
    assert len(calls) == 1
    with Session(customer_engine) as other, pytest.raises(HTTPException):
        contexts.authorize(other, ticket.inputs.workspace_id, ticket.actor_id)
    assert len(calls) == 1


def test_unloaded_identity_snapshot_never_lazy_loads(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    from app.customers.access import CustomerPrincipal

    with Session(customer_engine) as db:
        user = db.get(CustomerUser, ticket.actor_id)
        session = db.get(CustomerSession, ticket.session_digest)
        assert user and session
        db.expire(user, ["subject"])

        def forbidden(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("snapshot triggered SQL")

        event.listen(customer_engine, "before_cursor_execute", forbidden)
        try:
            with pytest.raises(HTTPException):
                snapshot(CustomerPrincipal(user, session))
        finally:
            event.remove(customer_engine, "before_cursor_execute", forbidden)
