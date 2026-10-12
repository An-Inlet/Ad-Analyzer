"""Real owned plan generation and current sales reads; no native IO on progress GET."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.commerce.models import CommerceSnapshot, CommerceStore
from app.customers.models import CustomerMembership, CustomerSession
from app.goals.models import Goal, GoalRevision
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents.models import PlanEventRow, PlanVersionRow
from app.publication.execution_models import ProviderExecutionAttempt
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def ready(engine: Engine, config: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    _, ticket, principal, calls = setup_evidence(
        engine, config, replicas, monkeypatch, "google_ads"
    )
    alice, outsider, provider = replicas
    alice.app.include_router(api.router)
    outsider.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="progress-generation"),
    )
    assert generated.status_code == 200, generated.text
    return alice, outsider, provider, ticket, principal, calls, url, generated.json()


def counts(db: Session) -> tuple[int, ...]:
    return tuple(
        db.scalar(select(func.count()).select_from(model)) or 0
        for model in (CommerceSnapshot, PlanVersionRow, PlanEventRow, ProviderExecutionAttempt)
    )


def test_actual_plan_api_sales_correction_and_no_read_side_effects(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.commerce.sync import CommerceSyncService

    from tests.test_commerce_measurement import FakeMeasurement, agreement, source

    alice, _, _, ticket, _, calls, url, document = ready(
        customer_engine, configuration, replicas, monkeypatch
    )
    with Session(customer_engine) as db:
        before = counts(db)
    number_calls = len(calls)
    response = alice.get(url + "/progress", params={"version": 1})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["document_digest"] == document["document_digest"]
    assert value["sales"]["net_sales_micros"] == -10_000_000
    assert value["net_sales_micros_exact"] == "-10000000"
    assert value["manual_application"] == "not_assessed"
    assert response.headers["cache-control"] == "no-store"
    # Actual owned reimport corrects the same original order's refund record.
    now = datetime.now(UTC)
    with Session(customer_engine) as db:
        store = db.get(CommerceStore, ticket.inputs.goal.definition.store_id)
        assert store
        # Make this actual scheduled import due; do not change production cadence.
        store.last_sync_at = now - timedelta(
            minutes=configuration.shopify_sync_interval_minutes + 1
        )
        db.commit()
        reader = FakeMeasurement(
            configuration, [([source(updated=now - timedelta(seconds=1))], None)]
        )
        reader.facts = [
            agreement(),
            agreement(2, "-22", "-2", "RETURN", datetime(2026, 10, 2, 12, tzinfo=UTC)),
        ]
        result = CommerceSyncService(db, configuration, reader).page(
            ticket.inputs.workspace_id, now=now
        )
        assert result["status"] == "complete", result
        db.commit()
    corrected = alice.get(url + "/progress", params={"version": 1})
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["net_sales_micros_exact"] == "-20000000"
    assert corrected.json()["document_digest"] == document["document_digest"]
    assert len(calls) == number_calls
    with Session(customer_engine) as db:
        assert counts(db) == before


@pytest.mark.parametrize(
    "change,reason",
    [
        ("revision", "goal_changed"),
        ("confirmation", "goal_changed"),
        ("definition", "goal_changed"),
        ("missing_lookup", "goal_unavailable"),
        ("stale", "stale_source"),
        ("import", "import_in_progress"),
        ("disconnected", "source_unavailable"),
    ],
)
def test_controlled_unavailable_keeps_original_goal(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    reason: str,
) -> None:
    from app.goals import service as goals

    alice, _, _, ticket, _, calls, url, document = ready(
        customer_engine, configuration, replicas, monkeypatch
    )
    with Session(customer_engine) as db:
        goal = db.get(Goal, ticket.inputs.goal.goal_id)
        assert goal
        revision = db.get(GoalRevision, (goal.id, goal.revision))
        assert revision
        store = db.get(CommerceStore, ticket.inputs.goal.definition.store_id)
        assert store
        if change == "revision":
            goals.revise(db, goal, None, "fixture", datetime.now(UTC))
        elif change == "confirmation":
            goal.confirmed_preview_id = None
        elif change == "definition":
            assert revision.definition is not None
            revision.definition = {**revision.definition, "target_micros": 999999}
        elif change == "missing_lookup":
            # The actual retained-input FK prevents deleting its goal. Exercise the
            # defensive lookup404 mapping explicitly, without disabling that FK.
            from fastapi import HTTPException

            def missing(*args: Any, **kwargs: Any) -> Any:
                raise HTTPException(404, "goal not found")

            monkeypatch.setattr(goals, "owned", missing)
        elif change == "stale":
            store.last_sync_at = datetime.now(UTC) - timedelta(days=2)
        elif change == "import":
            store.window_end = datetime.now(UTC)
        else:
            store.status = "disconnected"
        db.commit()
    number_calls = len(calls)
    response = alice.get(url + "/progress", params={"version": 1})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["goal"] == document["document"]["inputs"]["goal"]
    assert value["net_sales_micros_exact"] is None
    if change in {"revision", "confirmation", "definition", "missing_lookup"}:
        assert value["binding_reason"] == reason and value["sales"] is None
    else:
        assert value["binding_status"] == "matched" and reason in value["sales"]["reasons"]
    assert len(calls) == number_calls


def test_foreign_viewer_session_privacy_and_required_version(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_customer_identity import login

    alice, outsider, _, ticket, principal, _, url, _ = ready(
        customer_engine, configuration, replicas, monkeypatch
    )
    assert alice.get(url + "/progress").status_code == 422
    assert alice.get(url + "/progress", params={"version": 0}).status_code == 422
    assert alice.get(url + "/progress", params={"version": 999}).status_code == 404
    login(outsider, "foreign-progress:1")
    assert outsider.get(url + "/progress", params={"version": 1}).status_code in {403, 404}
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (principal.user.id, ticket.inputs.workspace_id))
        assert member
        member.role = "viewer"
        db.commit()
    assert alice.get(url + "/progress", params={"version": 1}).status_code == 200
    with Session(customer_engine) as db:
        bump_workspace_export_revision(db, ticket.inputs.workspace_id)
        db.commit()
    assert alice.get(url + "/progress", params={"version": 1}).status_code == 404
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, principal.session.digest)
        assert session
        session.revoked_at = 1
        db.commit()
    assert alice.get(url + "/progress", params={"version": 1}).status_code == 401


@pytest.mark.parametrize(
    "change", ["provider_revoked", "identity_during_refresh", "closing", "final_timeout"]
)
def test_authority_denials_are_not_unavailable_sales(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from dataclasses import replace

    from app.customers.models import CustomerUser
    from app.planning_documents import authority
    from app.planning_documents.authority_diagnostics import PlanningDiagnosticPhase
    from app.planning_documents.service import PlanningDocumentService
    from app.workspaces.models import Workspace
    from fastapi import HTTPException

    alice, _, provider, ticket, principal, _, url, document = ready(
        customer_engine, configuration, replicas, monkeypatch
    )
    if change == "provider_revoked":
        provider.revoked.add(principal.user.subject)
    elif change == "identity_during_refresh":
        original = provider.check_active

        def mutate(subject: str, authenticated_at: int) -> None:
            original(subject, authenticated_at)
            with Session(customer_engine) as db:
                user = db.get(CustomerUser, principal.user.id)
                assert user
                user.subject = "changed-after-provider-check"
                db.commit()

        monkeypatch.setattr(provider, "check_active", mutate)
    elif change == "closing":
        with Session(customer_engine) as db:
            workspace = db.get(Workspace, ticket.inputs.workspace_id)
            assert workspace
            workspace.status = "closing"
            db.commit()
    else:
        original_final = authority.final
        calls = []

        def final(
            current: Any, fact: Any, *, diagnostic_phase: PlanningDiagnosticPhase = "unspecified"
        ) -> None:
            calls.append(1)
            if len(calls) > 1:
                fact = replace(fact, completed_monotonic=fact.completed_monotonic - 6)
            original_final(current, fact, diagnostic_phase=diagnostic_phase)

        monkeypatch.setattr(authority, "final", final)
    with pytest.raises(HTTPException) as error:
        PlanningDocumentService(customer_engine, provider).sales_progress(
            principal, ticket.inputs.workspace_id, document["plan_id"], 1
        )
    expected = (
        401
        if change in {"provider_revoked", "identity_during_refresh"}
        else 404
        if change == "closing"
        else 409
    )
    assert error.value.status_code == expected


def test_identity_io_precedes_sql_and_expired_plan_does_not_hide_sales(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.planning_documents.service import PlanningDocumentService
    from sqlalchemy import event

    alice, _, provider, ticket, principal, calls, url, document = ready(
        customer_engine, configuration, replicas, monkeypatch
    )
    active: set[int] = set()
    checks = []
    original = provider.check_active

    def begin(connection: Any) -> None:
        active.add(id(connection))

    def end(connection: Any) -> None:
        active.discard(id(connection))

    def check(subject: str, authenticated_at: int) -> None:
        assert not active
        checks.append(subject)
        original(subject, authenticated_at)

    monkeypatch.setattr(provider, "check_active", check)
    event.listen(customer_engine, "begin", begin)
    event.listen(customer_engine, "commit", end)
    event.listen(customer_engine, "rollback", end)
    try:
        # Advance only this read's supplied clock beyond the retained native TTL.
        future = datetime.fromisoformat(
            document["document"]["valid_until"].replace("Z", "+00:00")
        ) + timedelta(seconds=1)
        result = PlanningDocumentService(
            customer_engine, provider, clock=lambda: future
        ).sales_progress(principal, ticket.inputs.workspace_id, document["plan_id"], 1)
        assert result.binding_status == "matched" and result.net_sales_micros_exact == "-10000000"
        assert checks and not active
    finally:
        event.remove(customer_engine, "begin", begin)
        event.remove(customer_engine, "commit", end)
        event.remove(customer_engine, "rollback", end)


def test_real_goal_lock_wait_expires_final_authority(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import event

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent row-lock wait requires PostgreSQL")
    alice, _, _, ticket, _, _, url, _ = ready(customer_engine, configuration, replicas, monkeypatch)
    waiting = threading.Event()
    main = threading.get_ident()

    def before_query(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if (
            threading.get_ident() != main
            and "FROM customer_goals" in statement
            and "FOR UPDATE" in statement
        ):
            waiting.set()

    event.listen(customer_engine, "before_cursor_execute", before_query)
    try:
        with Session(customer_engine) as blocker, ThreadPoolExecutor() as pool:
            blocker.scalar(
                select(Goal).where(Goal.id == ticket.inputs.goal.goal_id).with_for_update()
            )
            pending = pool.submit(alice.get, url + "/progress", params={"version": 1})
            assert waiting.wait(10)
            # Real lock wait outside the final security transaction, not an injected
            # sleep within authorization. Existing five-second budget is unchanged.
            threading.Event().wait(5.1)
            blocker.commit()
            response = pending.result(timeout=15)
            assert response.status_code == 409, response.text
            assert response.json()["detail"] == "planning_authority_expired"
    finally:
        event.remove(customer_engine, "before_cursor_execute", before_query)


def test_later_closed_day_and_new_sales_keep_exact_saved_plan(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.commerce.sync import CommerceSyncService

    from tests.test_commerce_measurement import FakeMeasurement, agreement, source

    alice, _, _, ticket, principal, calls, url, document = ready(
        customer_engine, configuration, replicas, monkeypatch
    )
    original = alice.get(url + "/progress", params={"version": 1})
    assert original.status_code == 200, original.text
    now = datetime.now(UTC)
    future = now + timedelta(days=1)
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, principal.session.digest)
        assert session
        # Explicit future-day scenario with matching test session lifetime.
        session.expires_at = int((future + timedelta(hours=1)).timestamp())
        db.commit()
        reader = FakeMeasurement(
            configuration, [([source(updated=future - timedelta(seconds=2))], None)]
        )
        reader.facts = [
            agreement(),
            agreement(2, "-11", "-1", "RETURN", datetime(2026, 10, 2, 12, tzinfo=UTC)),
            agreement(3, "55", "5", "ORDER", now),
        ]
        result = CommerceSyncService(db, configuration, reader).page(
            ticket.inputs.workspace_id, now=future - timedelta(seconds=1)
        )
        assert result["status"] == "complete", result
        db.commit()
    monkeypatch.setattr(api, "utc_now", lambda: future)
    count = len(calls)
    response = alice.get(url + "/progress", params={"version": 1})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["net_sales_micros_exact"] == "40000000"
    assert (
        value["sales"]["coverage"]["closed_day_count"]
        == original.json()["sales"]["coverage"]["closed_day_count"] + 1
    )
    assert value["document_digest"] == document["document_digest"]
    assert len(calls) == count
