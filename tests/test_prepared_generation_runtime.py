"""Actual configured v6 preparation, fresh boundaries and atomic publication."""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest
from app.campaign_performance.selected_models import CurrentEventSelectionRow
from app.customers.models import CustomerMembership, CustomerSession
from app.goals.models import Goal
from app.google_connections.models import GoogleCustomerConnection
from app.planning_documents import (
    authority,
    creative_finalization,
    repository,
    selected_paired_local,
    selected_plan_local,
)
from app.planning_documents import service as service_module
from app.planning_documents.authority_diagnostics import PlanningDiagnosticPhase
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanRequestRow, PlanRow, PlanVersionRow
from app.workspaces.models import Workspace
from sqlalchemy import Engine, event, func, select, update
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.planning_release_evidence import record_intentional_delay
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_api import generation
from tests.test_owner_review_runtime_authority_delay import _source_snapshot
from tests.test_owner_runtime_composition import actual_owner as actual_owner
from tests.test_shopify_sales import configuration as configuration


def create(actual_owner: Any) -> tuple[Any, str]:
    _, body, _, _, alice, root = actual_owner
    result = alice.post(root, headers=headers(alice), json=body)
    assert result.status_code == 201, result.text
    return alice, root + "/" + result.json()["plan_id"]


def trace_preparation(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    original = vars(service_module)["prepare_generation_checks"]
    captured: list[Any] = []

    def prepare(*args: Any) -> Any:
        result = original(*args)
        assert result is not None, "actual configured v6 must use eligible preparation"
        captured.append((result, args))
        return result

    monkeypatch.setattr(service_module, "prepare_generation_checks", prepare)
    return captured


def test_configured_preparation_work_counts_and_storage(
    actual_owner: Any,
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    alice, url = create(actual_owner)
    captured = trace_preparation(monkeypatch)
    phase = "outside"
    calls: dict[str, int] = {}
    selected_sql_counts: list[int] = []
    original_prepare = vars(service_module)["prepare_generation_checks"]
    original_save = repository.save_generation
    timing: dict[str, float] = {}

    def preparing(*args: Any) -> Any:
        nonlocal phase
        phase = "prepare"
        try:
            return original_prepare(*args)
        finally:
            phase = "outside"

    def saving(*args: Any, **kwargs: Any) -> Any:
        nonlocal phase
        phase = "save"
        assert kwargs["prepared"] is captured[0][0]
        started = time.monotonic()
        try:
            return original_save(*args, **kwargs)
        finally:
            timing["save_seconds"] = time.monotonic() - started
            phase = "outside"

    for module, name in (
        (repository, "_generation_entry"),
        (repository, "_generation_actual_bindings"),
        (repository, "_generation_owner_binding"),
        (selected_paired_local, "_validate_paired_ticket_pair"),
        (selected_plan_local, "_validate_selected_ticket_pair"),
        (service_module, "recheck_selected_paired_sources"),
        (selected_paired_local, "recheck_selected_sources"),
        (selected_plan_local, "capture_selected_proof"),
        (selected_plan_local, "_read_goal_progress_locked"),
    ):
        original = getattr(module, name)

        def counted(*args: Any, _name: str = name, _original: Any = original, **kwargs: Any) -> Any:
            if phase != "outside":
                key = phase + ":" + _name
                calls[key] = calls.get(key, 0) + 1
            if phase == "save" and _name == "recheck_selected_paired_sources":
                connection = args[0].connection()
                count = 0

                def executed(*unused: Any) -> None:
                    nonlocal count
                    count += 1

                event.listen(connection, "before_cursor_execute", executed)
                try:
                    return _original(*args, **kwargs)
                finally:
                    event.remove(connection, "before_cursor_execute", executed)
                    selected_sql_counts.append(count)
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)
    monkeypatch.setattr(service_module, "prepare_generation_checks", preparing)
    monkeypatch.setattr(repository, "save_generation", saving)
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert response.status_code == 200, response.text
    assert len(captured) == 1
    for name in ("_generation_entry", "_generation_actual_bindings", "_generation_owner_binding"):
        assert calls.get("prepare:" + name) == 1
        assert calls.get("save:" + name, 0) == 0
    for name in ("_validate_paired_ticket_pair", "_validate_selected_ticket_pair"):
        assert calls.get("save:" + name, 0) == 0
    for name in (
        "recheck_selected_paired_sources",
        "recheck_selected_sources",
        "capture_selected_proof",
        "_read_goal_progress_locked",
    ):
        assert calls["save:" + name] == 2
    # The original frozen phase diagnostics measured this same pair of source
    # passes. Their SQL work must remain present after pure preparation.
    assert selected_sql_counts == [701, 701]
    seal, (_, _, original_candidate) = captured[0]
    assert seal.snapshots is None and seal.db is None
    document = PlanVersion.model_validate(response.json()["document"])
    assert document.model_dump_json() == original_candidate.model_dump_json()
    with Session(customer_engine) as db:
        row = db.scalars(select(PlanVersionRow)).one()
        assert PlanVersion.model_validate_json(row.canonical_json) == document
        assert row.digest == document.digest()
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200
    assert PlanVersion.model_validate(exported.json()["document"]) == document
    (tmp_path / "prepared-generation-work.json").write_text(
        json.dumps(
            {
                "calls": calls,
                "selected_sql_counts": selected_sql_counts,
                "timing": timing,
                "document_digest": document.digest(),
            },
            indent=2,
        )
    )


@pytest.mark.parametrize(
    "fault",
    ["session", "membership", "privacy", "head", "candidate", "connection", "goal_confirmation"],
)
def test_committed_change_during_final_refresh_is_refused(
    actual_owner: Any, customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    alice, url = create(actual_owner)
    captured = trace_preparation(monkeypatch)
    before = planning_snapshot(customer_engine)
    effects = financial_counts(customer_engine)
    original_refresh = authority.refresh
    changed: list[bool] = []
    expected_rows: list[Any] = []

    def refresh(*args: Any, **kwargs: Any) -> Any:
        fact = original_refresh(*args, **kwargs)
        if not captured:
            return fact
        assert not changed
        changed.append(True)
        _, (ticket, _, candidate) = captured[0]
        wid = ticket.inputs.workspace_id
        if fault == "candidate":
            object.__setattr__(candidate.inputs, "revision", candidate.inputs.revision + 1)
        else:
            # A separate committed transaction between preparation and final save.
            def commit_change() -> None:
                with Session(customer_engine) as db, db.begin():
                    if fault == "session":
                        db.execute(
                            update(CustomerSession)
                            .where(CustomerSession.digest == ticket.session_digest)
                            .values(revoked_at=1)
                        )
                    elif fault == "membership":
                        db.execute(
                            update(CustomerMembership)
                            .where(
                                CustomerMembership.workspace_id == wid,
                                CustomerMembership.user_id == ticket.actor_id,
                            )
                            .values(status="suspended")
                        )
                    elif fault == "privacy":
                        db.execute(
                            update(Workspace)
                            .where(Workspace.id == wid)
                            .values(export_privacy_revision=Workspace.export_privacy_revision + 1)
                        )
                    elif fault == "head":
                        db.execute(
                            update(PlanRow)
                            .where(PlanRow.id == ticket.inputs.plan_id)
                            .values(version_head=PlanRow.version_head + 1)
                        )
                    elif fault == "connection":
                        db.execute(
                            update(GoogleCustomerConnection)
                            .where(GoogleCustomerConnection.workspace_id == wid)
                            .values(generation=GoogleCustomerConnection.generation + 1)
                        )
                    else:
                        db.execute(
                            update(Goal)
                            .where(Goal.id == ticket.inputs.goal.goal_id)
                            .values(confirmed_preview_id=None)
                        )

            if fault == "head":
                with ThreadPoolExecutor(max_workers=1) as writer:
                    writer.submit(commit_change).result(timeout=5)
            else:
                commit_change()
        expected_rows.append(planning_snapshot(customer_engine))
        return fact

    monkeypatch.setattr(authority, "refresh", refresh)
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert changed == [True]
    expected_status, expected_detail = {
        "session": (401, "customer authentication required"),
        "membership": (404, "workspace not found"),
        "privacy": (409, "generation privacy changed"),
        "head": (409, "generation input or version changed"),
        "candidate": (409, "prepared generation evidence changed"),
        "connection": (409, "selected advertising source changed"),
        "goal_confirmation": (409, "confirmed goal changed"),
    }[fault]
    assert response.status_code == expected_status, response.text
    assert response.json() == {"detail": expected_detail}
    assert captured[0][0].snapshots is None
    assert len(expected_rows) == 1
    assert planning_snapshot(customer_engine) == expected_rows[0]
    if fault != "head":
        assert expected_rows[0] == before
    assert financial_counts(customer_engine) == effects


@pytest.mark.parametrize("boundary", ["refresh", "session_entry"])
def test_service_failure_closes_preparation(
    actual_owner: Any, customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    alice, url = create(actual_owner)
    captured = trace_preparation(monkeypatch)
    before = planning_snapshot(customer_engine)
    failure = RuntimeError("controlled final boundary failure")
    if boundary == "refresh":
        original = authority.refresh

        def refresh(*args: Any, **kwargs: Any) -> Any:
            if captured:
                raise failure
            return original(*args, **kwargs)

        monkeypatch.setattr(authority, "refresh", refresh)
    else:
        original_session = vars(service_module)["Session"]

        class FailingContext:
            def __enter__(self) -> Any:
                raise failure

            def __exit__(self, *args: Any) -> None:
                pytest.fail("failed entry cannot exit")

        def session(*args: Any, **kwargs: Any) -> Any:
            return FailingContext() if captured else original_session(*args, **kwargs)

        monkeypatch.setattr(service_module, "Session", session)
    with pytest.raises(RuntimeError) as result:
        alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert result.value is failure
    assert len(captured) == 1 and captured[0][0].snapshots is None
    assert planning_snapshot(customer_engine) == before


@pytest.mark.parametrize(
    "fault",
    [
        "source_before_media",
        "source_after_media",
        "candidate_after_media",
        "candidate_input_after_media",
    ],
)
def test_media_boundary_mutation_rolls_back(
    actual_owner: Any, customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    alice, url = create(actual_owner)
    captured = trace_preparation(monkeypatch)
    wid = actual_owner[0].basis.workspace_id
    before = planning_snapshot(customer_engine), _source_snapshot(customer_engine, wid)
    effects = financial_counts(customer_engine)
    original = vars(service_module)["recheck_collected_creative"]
    changed: list[bool] = []
    privacy_mismatches: list[bool] = []
    original_revision = vars(creative_finalization)["workspace_export_revision"]

    def revision(db: Session, workspace_id: int) -> int:
        value = original_revision(db, workspace_id)
        assert type(value) is int
        if changed:
            privacy_mismatches.append(value != captured[0][1][0].privacy_revision)
        return value

    monkeypatch.setattr(creative_finalization, "workspace_export_revision", revision)
    owner_returned: list[bool] = []
    if fault == "candidate_after_media":
        original_owner = vars(service_module)["recheck_owner_review_input_receipts"]

        def owner(*args: Any, **kwargs: Any) -> Any:
            result = original_owner(*args, **kwargs)
            owner_returned.append(True)
            return result

        monkeypatch.setattr(service_module, "recheck_owner_review_input_receipts", owner)

    def mutate(db: Session) -> None:
        assert len(captured) == 1 and not changed
        changed.append(True)
        if fault.startswith("candidate_"):
            candidate = captured[0][1][2]
            if fault == "candidate_input_after_media":
                object.__setattr__(candidate.inputs, "revision", candidate.inputs.revision + 1)
            else:
                object.__setattr__(candidate, "summary", "Mutated after preparation.")
        else:
            previous_revision = original_revision(db, wid)
            db.execute(
                update(CurrentEventSelectionRow)
                .where(CurrentEventSelectionRow.workspace_id == wid)
                .values(invalidated=True)
            )
            assert original_revision(db, wid) > previous_revision
            clean = not (db.new or db.dirty or db.deleted)
            assert clean, "source mutation must leave clean ORM state"

    def creative(db: Session, **kwargs: Any) -> Any:
        if fault == "source_before_media":
            mutate(db)
        result = original(db, **kwargs)
        if fault != "source_before_media":
            mutate(db)
        return result

    monkeypatch.setattr(service_module, "recheck_collected_creative", creative)
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert changed == [True]
    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": (
            "prepared generation evidence changed"
            if fault == "candidate_after_media"
            else "owner review differs from actual collected evidence"
            if fault == "candidate_input_after_media"
            else "creative image source changed"
            if fault == "source_before_media"
            else "Planning evidence changed. Read current sources again."
        )
    }
    assert owner_returned == ([True] if fault == "candidate_after_media" else [])
    assert privacy_mismatches == ([True] if fault == "source_before_media" else [])
    assert (planning_snapshot(customer_engine), _source_snapshot(customer_engine, wid)) == before
    assert financial_counts(customer_engine) == effects
    assert captured[0][0].snapshots is None


@pytest.mark.parametrize("boundary", ["pre_cas", "post_flush"])
def test_configured_real_expiry_preserves_complete_rollback(
    actual_owner: Any,
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    boundary: str,
    tmp_path: Path,
) -> None:
    alice, url = create(actual_owner)
    captured = trace_preparation(monkeypatch)
    wid = actual_owner[0].basis.workspace_id
    before = planning_snapshot(customer_engine), _source_snapshot(customer_engine, wid)
    effects = financial_counts(customer_engine)
    original_final, original_save = authority.final, repository.save_generation
    active: list[Any] = []
    delayed: list[bool] = []

    def saving(db: Session, **kwargs: Any) -> Any:
        original_preparation = not active and kwargs["prepared"] is captured[0][0]
        assert original_preparation, "one original prepared save required"
        active.append((db, kwargs["fact"]))
        return original_save(db, **kwargs)

    def final(
        principal: Any,
        fact: Any,
        *,
        diagnostic_phase: PlanningDiagnosticPhase = "unspecified",
    ) -> None:
        if active and diagnostic_phase == boundary:
            original_fact = not delayed and fact is active[0][1]
            assert original_fact, "one original final authorization fact required"
            db = active[0][0]
            with db.no_autoflush:
                versions = db.scalar(select(func.count()).select_from(PlanVersionRow))
                receipts = db.scalar(
                    select(func.count())
                    .select_from(PlanRequestRow)
                    .where(PlanRequestRow.operation == "generate")
                )
            assert (versions, receipts) == ((0, 0) if boundary == "pre_cas" else (1, 1))
            record_intentional_delay(fact, boundary, 6)
            delayed.append(True)
            time.sleep(6)  # Original fact and five-second guard remain untouched.
        original_final(principal, fact, diagnostic_phase=diagnostic_phase)

    monkeypatch.setattr(repository, "save_generation", saving)
    monkeypatch.setattr(authority, "final", final)
    response: Any = None
    try:
        response = alice.post(url + "/generate", headers=headers(alice), json=generation())
        assert delayed == [True]
        assert response.status_code == 409
        assert response.json() == {"detail": "planning_authority_expired"}
        records = [
            json.loads(record.getMessage())
            for record in caplog.records
            if record.name == "inlet.planning.authority"
        ]
        assert records == [
            dict(
                event="planning_authority_expired",
                schema_version=1,
                route="generate",
                phase=boundary,
                cause="fact_age_outside_window",
                session_predicate="not_evaluated",
                status=409,
            )
        ]
        assert (
            planning_snapshot(customer_engine),
            _source_snapshot(customer_engine, wid),
        ) == before
        assert financial_counts(customer_engine) == effects
        assert captured[0][0].snapshots is None
    finally:
        _persist_expiry_outcome(
            tmp_path / "expiry-outcome.json",
            response,
            delayed,
            caplog.records,
            failed=sys.exception() is not None,
        )


def _persist_expiry_outcome(
    destination: Path, response: Any, delayed: list[bool], records: list[Any], *, failed: bool
) -> None:
    """Fixed failure evidence only; never replace an active assertion/exception."""
    try:
        status = response.status_code if response is not None else None
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            raise ValueError("invalid diagnostic status")
        category = "no_response" if status is None else "other_response"
        malformed_response = False
        if status is not None and 400 <= status < 500 and len(response.content) <= 4096:
            try:
                payload = response.json()
                malformed_response = type(payload) is not dict
            except (TypeError, ValueError):
                payload = None
                malformed_response = True
            detail = payload.get("detail") if type(payload) is dict else None
            if type(detail) is str and detail in {
                "planning_authority_expired",
                "prepared generation evidence changed",
                "Planning evidence changed. Read current sources again.",
                "customer authentication required",
                "generation evidence expired",
            }:
                category = detail
        expiry: list[dict[str, Any]] = []
        malformed = 0
        expected: dict[str, set[Any]] = {
            "event": {"planning_authority_expired"},
            "schema_version": {1},
            "route": {"generate", "current", "history", "version", "unspecified"},
            "phase": {"lock", "replay", "pre_cas", "post_flush", "unspecified"},
            "cause": {"fact_age_outside_window", "session_expired"},
            "session_predicate": {"not_evaluated", "expired"},
            "status": {409},
        }
        for record in records:
            if record.name != "inlet.planning.authority":
                continue
            if len(expiry) >= 32:
                malformed += 1
                continue
            try:
                if type(record.msg) is not str or record.args or len(record.msg) > 1024:
                    raise ValueError("bounded fixed message required")
                value = json.loads(record.msg)
                if (
                    type(value) is not dict
                    or set(value) != set(expected)
                    or any(
                        type(value[key])
                        is not (int if key in {"schema_version", "status"} else str)
                        or value[key] not in allowed
                        for key, allowed in expected.items()
                    )
                ):
                    raise ValueError("fixed authority fields required")
                if value["session_predicate"] != (
                    "expired" if value["cause"] == "session_expired" else "not_evaluated"
                ):
                    raise ValueError("consistent authority fields required")
                expiry.append(value)
            except (TypeError, ValueError):
                malformed += 1
        with destination.open("x") as target:
            json.dump(
                dict(
                    status=status,
                    category=category,
                    delay_reached=delayed == [True],
                    assertion_or_request_failed=failed,
                    authority_events=expiry,
                    malformed_events=malformed,
                    malformed_response=malformed_response,
                ),
                target,
                indent=2,
                allow_nan=False,
            )
            target.write("\n")
    except BaseException:
        if not failed:
            raise
        with suppress(BaseException):
            print("EXPIRY_OUTCOME_WRITE_FAILED", file=sys.stderr)
