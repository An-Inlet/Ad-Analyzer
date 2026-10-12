"""Injected acquisition through actual owned SQL/history/archive on both backends."""

import io
import json
import os
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event
from typing import Any
from uuid import uuid4

import pytest
from app.api.customer_exports import router as export_router
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import Base
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents import authority, repository
from app.planning_documents import google_budget_observation_service as budget_service
from app.planning_documents import service as planning_service
from app.planning_documents.documents import PlanVersion
from app.planning_documents.google_budget_events import BudgetInvalidationIntent, BudgetReadIntent
from app.planning_documents.google_budget_observation_service import GoogleBudgetObservationService
from app.planning_documents.models import PlanEventRow, PlanRow
from app.planning_documents.storage import document_for_row
from app.publication import customer_intents
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine, create_engine, text, update
from sqlalchemy import event as sql_event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.google_budget_read_fixture import Search, ticket
from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_exports import unpack
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_api import generation
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.fixture(params=["sqlite", "postgres"])
def customer_engine(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Generator[Engine, None, None]:
    if request.param == "sqlite":
        engine = create_engine("sqlite:///" + str(tmp_path / "budget.sqlite"))
        with engine.begin() as db:
            db.exec_driver_sql("PRAGMA journal_mode=WAL")
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()
        return
    url = os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
    assert url and os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
    schema = "inlet_budget_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text('CREATE SCHEMA "' + schema + '"'))
    engine = create_engine(url, connect_args={"options": "-csearch_path=" + schema})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text('DROP SCHEMA "' + schema + '" CASCADE'))
        admin.dispose()


def principal(engine: Engine, client: Any) -> CustomerPrincipal:
    with Session(engine) as db:
        session = db.get(CustomerSession, digest(client.cookies[SESSION_COOKIE]))
        assert session is not None
        user = db.get(CustomerUser, session.user_id)
        assert user is not None
        return CustomerPrincipal(user, session)


def prepare(
    engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Any:
    fixture, body, calls, _ = configured_owner_review(
        engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, provider = replicas
    wid = fixture.basis.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert generated.status_code == 200, generated.text
    doc = PlanVersion.model_validate(generated.json()["document"])
    assert doc.google_budget_owner_review is not None
    review = doc.google_budget_owner_review.reviews[0]
    with Session(engine) as db:
        scope = customer_intents.account(db, wid, review.intent.account_id)
    acquisition = ticket(doc, scope)
    request = BudgetReadIntent(
        **acquisition.binding.model_dump(),
        expected_event_sequence=0,
        request_key="budget-read-original",
    )
    search = Search(scope.external_advertiser_id, amount=review.intent.requested_amount_micros)
    search.data["customer"][0]["customer"]["timeZone"] = (
        review.witness.catalog_evidence.catalog.native_observation.time_zone
    )
    service = GoogleBudgetObservationService(engine, provider, search)
    return alice, provider, doc, request, search, service, url, root, fixture, calls


def change_source(engine: Engine, account_id: int) -> None:
    with Session(engine) as db, db.begin():
        db.execute(
            update(GoogleCustomerConnection)
            .where(GoogleCustomerConnection.account_id == account_id)
            .values(generation=GoogleCustomerConnection.generation + 1)
        )


def test_injected_budget_history_replay_invalidation_and_erasure(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    alice, provider, doc, request, search, service, url, root, fixture, calls = prepare(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    owner = principal(customer_engine, alice)
    effects = financial_counts(customer_engine)
    provider_counts = (len(calls), len(fixture.calls))
    baseline = planning_snapshot(customer_engine)
    original_append = GoogleBudgetObservationService._append

    def fail_after_insert(*args: Any, **kwargs: Any) -> Any:
        original_append(*args, **kwargs)
        raise RuntimeError("fixture publication rollback")

    with monkeypatch.context() as patch:
        patch.setattr(GoogleBudgetObservationService, "_append", staticmethod(fail_after_insert))
        with pytest.raises(RuntimeError, match="fixture publication rollback"):
            service.observe(owner, request)
    assert planning_snapshot(customer_engine) == baseline
    inserted = False
    real_final = authority.final

    def inserted_then_expired(*args: Any, **kwargs: Any) -> Any:
        nonlocal inserted
        result = original_append(*args, **kwargs)
        inserted = True
        return result

    def final_expiry(current: Any, fact: Any, **kwargs: Any) -> None:
        if inserted:
            fact = replace(fact, completed_monotonic=time.monotonic() - 6)
        real_final(current, fact, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(
            GoogleBudgetObservationService, "_append", staticmethod(inserted_then_expired)
        )
        patch.setattr(authority, "final", final_expiry)
        with pytest.raises(HTTPException) as expired:
            service.observe(owner, request)
        assert inserted and expired.value.detail == "planning_authority_expired"
    assert planning_snapshot(customer_engine) == baseline
    observed = service.observe(owner, request)
    assert observed.event_sequence == 1 and observed.event.finding == "matches_hypothesis"
    saved = planning_snapshot(customer_engine)
    count = len(search.calls)
    assert service.observe(owner, request) == observed
    assert len(search.calls) == count and planning_snapshot(customer_engine) == saved
    real_document = document_for_row

    def revoke_after_preparation(*args: Any, **kwargs: Any) -> Any:
        result = real_document(*args, **kwargs)
        provider.revoked.add(owner.user.subject)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(budget_service, "document_for_row", revoke_after_preparation)
        with pytest.raises(HTTPException) as late_replay:
            service.observe(owner, request)
        assert late_replay.value.status_code == 401
    provider.revoked.clear()
    assert len(search.calls) == count and planning_snapshot(customer_engine) == saved

    decoded = False
    snapshot_sequence = 1
    real_values = repository.values

    def changed_snapshot(row: Any) -> dict[str, Any]:
        # Simulate a corrupted later row snapshot without bypassing SQL immutability.
        result = real_values(row)
        if decoded and isinstance(row, PlanEventRow) and row.sequence == snapshot_sequence:
            result["recorded_at"] += timedelta(seconds=1)
        return result

    def change_after_preparation(*args: Any, **kwargs: Any) -> Any:
        nonlocal decoded
        result = real_document(*args, **kwargs)
        decoded = True
        return result

    with monkeypatch.context() as patch:
        patch.setattr(budget_service, "document_for_row", change_after_preparation)
        patch.setattr(repository, "values", changed_snapshot)
        with pytest.raises(HTTPException) as row_changed:
            service.observe(owner, request)
        assert row_changed.value.detail == "budget receipt changed during preparation"
    assert len(search.calls) == count and planning_snapshot(customer_engine) == saved
    with pytest.raises(HTTPException) as changed:
        service.observe(owner, request.model_copy(update={"expected_event_sequence": 1}))
    assert changed.value.status_code == 409 and planning_snapshot(customer_engine) == saved
    foreign = replicas[1]
    login(foreign, "budget-foreign:1")
    with pytest.raises(HTTPException) as denied:
        service.observe(principal(customer_engine, foreign), request)
    assert denied.value.status_code in (403, 404)
    invalidation = BudgetInvalidationIntent(
        **request.model_dump(exclude={"request_key", "expected_event_sequence"}),
        request_key="budget-invalidation",
        expected_event_sequence=1,
        observation_event_id=observed.event.event_id,
        observation_digest=observed.event.digest(),
        observation_sequence=1,
    )
    with pytest.raises(HTTPException, match="has not changed"):
        service.invalidate_source_change(owner, invalidation)
    assert planning_snapshot(customer_engine) == saved
    decision = alice.post(
        url + "/decisions",
        headers=headers(alice),
        json=dict(
            expected_version=request.version,
            expected_event_sequence=1,
            document_digest=request.document_digest,
            action_key=request.action_key,
            action_digest=request.action_digest,
            decision="deferred",
            reason="Keep the historical budget investigation under review.",
            supersedes_event_id=None,
            request_key="budget-history-decision",
        ),
    )
    assert decision.status_code == 200, decision.text
    saved = planning_snapshot(customer_engine)
    invalidation = invalidation.model_copy(update={"expected_event_sequence": 2})
    change_source(customer_engine, observed.event.proof.ticket.account.account.account_id)
    decoded = False
    with monkeypatch.context() as patch:
        patch.setattr(budget_service, "document_for_row", change_after_preparation)
        patch.setattr(repository, "values", changed_snapshot)
        with pytest.raises(HTTPException) as prior_changed:
            service.invalidate_source_change(owner, invalidation)
        assert prior_changed.value.detail == "budget observation changed during preparation"
    assert planning_snapshot(customer_engine) == saved
    invalidated = service.invalidate_source_change(owner, invalidation)
    assert invalidated.event_sequence == 3
    assert invalidated.event.reason == "source_generation_changed"
    assert service.invalidate_source_change(owner, invalidation) == invalidated
    assert service.observe(owner, request) == observed  # historical replay after invalidation
    assert len(search.calls) == count
    with pytest.raises(HTTPException, match="already invalidated"):
        service.invalidate_source_change(
            owner,
            invalidation.model_copy(
                update={"request_key": "another-invalidation", "expected_event_sequence": 3}
            ),
        )
    history = alice.get(url + "/events")
    assert history.status_code == 200, history.text
    expected = [
        observed.event.model_dump(mode="json"),
        decision.json()["event"],
        invalidated.event.model_dump(mode="json"),
    ]
    assert [r["event"] for r in history.json()["items"]] == expected
    decoded, snapshot_sequence = False, 2  # Change only the unreturned lookahead row.
    with monkeypatch.context() as patch:
        patch.setattr(planning_service, "document_for_row", change_after_preparation)
        patch.setattr(repository, "values", changed_snapshot)
        changed_page = alice.get(url + "/events?limit=1")
        assert changed_page.status_code == 409
        assert changed_page.json()["detail"] == "event page changed during preparation"
    decoded, snapshot_sequence = False, 1
    with monkeypatch.context() as patch:
        patch.setattr(planning_service, "document_for_row", change_after_preparation)
        patch.setattr(repository, "values", changed_snapshot)
        changed_receipt = alice.get(root + "/requests/budget_observe/" + request.request_key)
        assert changed_receipt.status_code == 409
        assert changed_receipt.json()["detail"] == "budget request changed during preparation"
    for operation, intent, result in (
        ("budget_observe", request, observed),
        ("budget_invalidate", invalidation, invalidated),
    ):
        replay = alice.get(root + "/requests/" + operation + "/" + intent.request_key)
        assert replay.status_code == 200, replay.text
        assert replay.json() == result.model_dump(mode="json")
    monkeypatch.setattr(settings, "customer_export_enabled", True)
    monkeypatch.setattr(settings, "media_storage_mode", "local_dev")
    monkeypatch.setattr(settings, "media_local_directory", str(tmp_path / "media"))
    alice.app.include_router(export_router)
    exports = f"/api/customer/v1/workspaces/{doc.inputs.workspace_id}/exports"
    export = alice.post(
        exports, headers={**headers(alice), "Idempotency-Key": "budget-history-export"}, json={}
    )
    assert export.status_code == 200, export.text
    download = alice.get(exports + "/" + export.json()["request_id"] + "/download")
    assert download.status_code == 200, download.text[:500]
    _, entries = unpack(io.BytesIO(download.content))
    archived = [
        json.loads(line)["document"]
        for line in entries["data/planning_document_events.jsonl"].splitlines()
    ]
    assert archived == expected
    provider.revoked.add(owner.user.subject)
    assert alice.get(url + "/events").status_code == 401
    with pytest.raises(HTTPException) as revoked:
        service.observe(owner, request)
    assert revoked.value.status_code == 401
    provider.revoked.clear()

    def erase_after_preparation(*args: Any, **kwargs: Any) -> Any:
        result = real_document(*args, **kwargs)
        with Session(customer_engine) as db, db.begin():
            bump_workspace_export_revision(db, doc.inputs.workspace_id)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(budget_service, "document_for_row", erase_after_preparation)
        with pytest.raises(HTTPException) as late_erasure:
            service.observe(owner, request)
        assert late_erasure.value.status_code == 404
    assert all(not table for table in planning_snapshot(customer_engine))
    assert alice.get(url + "/events").status_code == 404
    with pytest.raises(HTTPException) as erased:
        service.observe(owner, request)
    assert erased.value.status_code == 404
    assert financial_counts(customer_engine) == effects
    assert (len(calls), len(fixture.calls)) == provider_counts
    (tmp_path / "budget-history.json").write_text(
        json.dumps(
            dict(
                history=history.json(),
                archive=archived,
                replay_without_reads=True,
                erased=True,
                provenance="injected_fixture",
            ),
            indent=2,
        )
    )


def test_budget_acquisition_late_revocation_expiry_and_event_cas(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    alice, provider, doc, request, search, service, _, _, _, _ = prepare(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    owner = principal(customer_engine, alice)
    before = planning_snapshot(customer_engine)

    def revoked_read(ticket: Any, query: str, cursor: str | None) -> str:
        answer = search(ticket, query, cursor)
        assert isinstance(answer, str)
        if "FROM campaign_budget" in query:
            provider.revoked.add(owner.user.subject)
        return answer

    service.search = revoked_read
    with pytest.raises(HTTPException) as denied:
        service.observe(owner, request)
    assert denied.value.status_code == 401 and planning_snapshot(customer_engine) == before
    provider.revoked.clear()
    offset = timedelta()

    def expiring_read(ticket: Any, query: str, cursor: str | None) -> str:
        nonlocal offset
        answer = search(ticket, query, cursor)
        assert isinstance(answer, str)
        offset = timedelta(minutes=6)
        return answer

    service.search = expiring_read
    service.clock = lambda: datetime.now(UTC) + offset
    with pytest.raises(ValueError, match="expired"):
        service.observe(owner, request)
    assert planning_snapshot(customer_engine) == before
    service.clock = lambda: datetime.now(UTC)
    barrier = Barrier(2) if customer_engine.dialect.name == "postgresql" else None

    def overlap(ticket: Any, query: str, cursor: str | None) -> str:
        answer = search(ticket, query, cursor)
        assert isinstance(answer, str)
        if barrier is not None and "FROM campaign_budget" in query:
            barrier.wait(timeout=10)
        return answer

    service.search = overlap

    def run(key: str) -> dict[str, Any]:
        try:
            result = service.observe(owner, request.model_copy(update={"request_key": key}))
            return dict(status=200, result=result.model_dump(mode="json"))
        except HTTPException as error:
            return dict(status=error.status_code, detail=error.detail)

    outcomes: list[dict[str, Any]] = []
    try:
        if barrier is not None:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(run, key) for key in ("budget-race-left", "budget-race-right")
                ]
                for future in futures:
                    outcomes.append(future.result(timeout=30))
        else:
            outcomes = [run("budget-race-left"), run("budget-race-right")]
    finally:
        active_error = sys.exception()
        try:
            (tmp_path / "budget-cas-outcomes.json").write_text(json.dumps(outcomes, indent=2))
        except OSError:
            if active_error is None:
                raise
            active_error.add_note("CAS evidence write failed; original test failure retained")
    assert sorted(r["status"] for r in outcomes) == [200, 409]
    after = planning_snapshot(customer_engine)
    assert len(after[4]) == len(before[4]) + 1 and len(after[5]) == len(before[5]) + 1
    with Session(customer_engine) as db:
        plan = db.get(PlanRow, (doc.inputs.workspace_id, doc.inputs.plan_id))
        assert plan is not None and plan.event_sequence == 1
    service.search = search

    def source_change(ticket: Any, query: str, cursor: str | None) -> str:
        answer = search(ticket, query, cursor)
        assert isinstance(answer, str)
        if "FROM campaign_budget" in query:
            change_source(customer_engine, ticket.account.account.account_id)
        return answer

    service.search = source_change
    with pytest.raises(HTTPException) as changed:
        service.observe(
            owner,
            request.model_copy(update={"request_key": "late-source", "expected_event_sequence": 1}),
        )
    assert changed.value.status_code == 409 and planning_snapshot(customer_engine) == after


def test_budget_final_read_to_publication_source_fence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    alice, _, _, request, _, service, _, _, _, _ = prepare(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    owner = principal(customer_engine, alice)
    before = planning_snapshot(customer_engine)
    original = GoogleBudgetObservationService._append
    attempted, committed = Event(), Event()
    futures: list[Any] = []
    mutation_pid: list[int] = []

    def mutation(account_id: int) -> None:
        with Session(customer_engine) as db, db.begin():
            if customer_engine.dialect.name == "postgresql":
                pid = db.scalar(text("SELECT pg_backend_pid()"))
                assert isinstance(pid, int)
                mutation_pid.append(pid)
            db.execute(
                update(GoogleCustomerConnection)
                .where(GoogleCustomerConnection.account_id == account_id)
                .values(generation=GoogleCustomerConnection.generation + 1)
            )
        committed.set()

    def executing(
        connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        if statement.startswith("UPDATE google_customer_connections"):
            attempted.set()

    sql_event.listen(customer_engine, "before_cursor_execute", executing)
    with ThreadPoolExecutor(max_workers=1) as executor:

        def boundary(*args: Any, **kwargs: Any) -> Any:
            event = args[3]
            writer = (
                args[0].scalar(text("SELECT pg_backend_pid()"))
                if customer_engine.dialect.name == "postgresql"
                else None
            )
            futures.append(executor.submit(mutation, event.proof.ticket.account.account.account_id))
            assert attempted.wait(5)
            if customer_engine.dialect.name == "sqlite":
                futures[0].result(timeout=5)  # WAL writer committed after our SELECT snapshot.
                assert committed.is_set()
            else:
                blocked = False
                deadline = time.monotonic() + 3
                observer = create_engine(
                    customer_engine.url,
                    connect_args={"connect_timeout": 2, "options": "-cstatement_timeout=1000"},
                )
                try:
                    with observer.connect() as monitor:
                        while time.monotonic() < deadline:
                            blocked = bool(
                                monitor.scalar(
                                    text("SELECT :writer = ANY(pg_blocking_pids(:mutator))"),
                                    {"writer": writer, "mutator": mutation_pid[0]},
                                )
                            )
                            if blocked:
                                break
                            committed.wait(0.01)
                finally:
                    observer.dispose()
                assert blocked and not committed.is_set()
            return original(*args, **kwargs)

        monkeypatch.setattr(GoogleBudgetObservationService, "_append", staticmethod(boundary))
        try:
            if customer_engine.dialect.name == "sqlite":
                with pytest.raises(OperationalError, match="locked"):
                    service.observe(owner, request)
                assert planning_snapshot(customer_engine) == before
            else:
                assert service.observe(owner, request).event_sequence == 1
            futures[0].result(timeout=5)
            assert committed.is_set()
        finally:
            sql_event.remove(customer_engine, "before_cursor_execute", executing)


def test_budget_receipt_committed_during_acquisition_recovers_original(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    alice, provider, _, request, search, service, _, _, _, _ = prepare(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    owner = principal(customer_engine, alice)
    before = planning_snapshot(customer_engine)
    winning: list[Any] = []
    inner = GoogleBudgetObservationService(customer_engine, provider, search)

    def committed_receipt(ticket: Any, query: str, cursor: str | None) -> str:
        answer = search(ticket, query, cursor)
        assert isinstance(answer, str)
        if "FROM campaign_budget" in query:
            winning.append(inner.observe(owner, request))
        return answer

    service.search = committed_receipt
    result = service.observe(owner, request)
    assert winning == [result] and result.event_sequence == 1
    after = planning_snapshot(customer_engine)
    assert len(after[4]) == len(before[4]) + 1 and len(after[5]) == len(before[5]) + 1
    count = len(search.calls)
    assert service.observe(owner, request) == result and len(search.calls) == count


@pytest.mark.parametrize("reader", ["history", "receipt"])
def test_budget_http_prepared_read_revocation_and_erasure(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    reader: str,
) -> None:
    alice, provider, doc, request, search, service, url, root, _, _ = prepare(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    owner = principal(customer_engine, alice)
    service.observe(owner, request)
    before = planning_snapshot(customer_engine)
    calls = len(search.calls)
    endpoint = (
        url + "/events"
        if reader == "history"
        else (root + "/requests/budget_observe/" + request.request_key)
    )

    def revoked(*args: Any, **kwargs: Any) -> Any:
        result = document_for_row(*args, **kwargs)
        provider.revoked.add(owner.user.subject)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(planning_service, "document_for_row", revoked)
        assert alice.get(endpoint).status_code == 401
    provider.revoked.clear()
    assert planning_snapshot(customer_engine) == before

    def erased(*args: Any, **kwargs: Any) -> Any:
        result = document_for_row(*args, **kwargs)
        with Session(customer_engine) as db, db.begin():
            bump_workspace_export_revision(db, doc.inputs.workspace_id)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(planning_service, "document_for_row", erased)
        assert alice.get(endpoint).status_code == 404
    assert len(search.calls) == calls
    assert all(not table for table in planning_snapshot(customer_engine))
