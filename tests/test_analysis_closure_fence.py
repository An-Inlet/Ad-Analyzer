"""Selected/claimed analysis versus actual customer closure, with real SQL transactions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
from app.analysis.models import AnalysisRun
from app.analysis.repository import AnalysisRunRepository
from app.analysis.service import AnalysisRunService
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.lifecycle.quiescing import quiesce
from app.workspaces.models import Workspace
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import NOW, seed
from tests.test_customer_quiescing import confirmed


def close(engine: Engine, wid: int, uid: str, sid: str) -> None:
    with Session(engine) as db:
        user, session = db.get(CustomerUser, uid), db.get(CustomerSession, sid)
        assert user is not None and session is not None
        principal = CustomerPrincipal(user, session)
        request, evidence = confirmed(db, principal, wid)
        quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, NOW)
        db.commit()


def execute(db: Session, wid: int, key: str = "closure-race") -> AnalysisRun:
    return AnalysisRunService(db).execute(
        workspace_id=wid,
        cadence=AnalysisCadence.NIGHTLY,
        run_key=key,
        scheduled_for=NOW,
        window_days=7,
        as_of=NOW,
    )


def test_selected_before_closure_cannot_claim_new_analysis(export_engine: Engine) -> None:
    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
    selected, proceed = Event(), Event()

    def worker() -> str:
        with Session(export_engine) as db:
            workspace = db.get(Workspace, wid)
            assert workspace is not None and workspace.status == "active"
            selected.set()
            assert proceed.wait(15)
            try:
                return execute(db, wid).status.value
            except ValueError:
                db.rollback()
                return "blocked"

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        try:
            assert selected.wait(10)
            close(export_engine, wid, uid, sid)
        finally:
            proceed.set()
        outcome = future.result(timeout=20)
    assert outcome == "blocked", f"analysis after closure produced {outcome}"
    with Session(export_engine) as db:
        assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 0


def test_closure_wins_after_durable_claim_before_local_outputs(
    export_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
    claimed, proceed, analyzed = Event(), Event(), Event()
    original_claim, original_analyze = AnalysisRunRepository.claim, AnalysisRunService._analyze

    def paused(self, **kwargs):  # type: ignore[no-untyped-def]
        result = original_claim(self, **kwargs)
        claimed.set()
        assert proceed.wait(15)
        return result

    def traced(self, **kwargs):  # type: ignore[no-untyped-def]
        analyzed.set()
        return original_analyze(self, **kwargs)

    monkeypatch.setattr(AnalysisRunRepository, "claim", paused)
    monkeypatch.setattr(AnalysisRunService, "_analyze", traced)
    with ThreadPoolExecutor(max_workers=1) as pool:

        def worker() -> str:
            with Session(export_engine) as db:
                return execute(db, wid).status.value

        future = pool.submit(worker)
        try:
            assert claimed.wait(10)
            close(export_engine, wid, uid, sid)
        finally:
            proceed.set()
        outcome = future.result(timeout=20)
    assert not analyzed.is_set(), "analysis created fresh outputs after closure"
    assert outcome == AnalysisRunStatus.FAILED.value


def test_direct_success_persistence_requires_active_workspace(export_engine: Engine) -> None:
    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
        row, _ = AnalysisRunRepository(db).claim(
            workspace_id=wid,
            account_id=None,
            source_job_run_id=None,
            run_key="direct-finish",
            cadence=AnalysisCadence.NIGHTLY,
            schedule_policy_version="v1",
            scheduled_for=NOW,
            metric_date_from=NOW.date(),
            metric_date_to=NOW.date(),
            outcome_date_from=NOW.date(),
            outcome_date_to=NOW.date(),
            started_at=NOW,
        )
        run_id = row.id
    close(export_engine, wid, uid, sid)
    with Session(export_engine) as db:
        persisted = db.get(AnalysisRun, run_id)
        assert persisted is not None
        with pytest.raises(ValueError):
            AnalysisRunRepository(db).finish_succeeded(
                persisted,
                finished_at=NOW,
                accounts_analyzed=0,
                findings_count=0,
                high_severity_findings_count=0,
                recommendations_created_count=0,
                recommendations_deduplicated_count=0,
                outcome_analysis_ready=False,
                outcome_campaign_count=0,
                attributed_journey_count=0,
                unattributed_journey_count=0,
                blocking_reasons=[],
            )
        db.rollback()
        assert persisted.status == AnalysisRunStatus.RUNNING


def test_postgres_closure_waits_for_local_result_commit(
    export_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    if export_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock ordering")
    from sqlalchemy import event

    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
    analyzing, release, closing = Event(), Event(), Event()
    original = AnalysisRunService._analyze
    locks: list[str] = []

    def paused(self, **kwargs):  # type: ignore[no-untyped-def]
        analyzing.set()
        assert release.wait(15)
        return original(self, **kwargs)

    def record(conn, cursor, statement, parameters, context, many):  # type: ignore[no-untyped-def]
        if "FOR " in statement:
            locks.append(statement)
            if "FROM workspaces" in statement and analyzing.is_set():
                closing.set()

    monkeypatch.setattr(AnalysisRunService, "_analyze", paused)
    event.listen(export_engine, "before_cursor_execute", record)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:

            def worker() -> str:
                with Session(export_engine) as db:
                    return execute(db, wid).status.value

            run = pool.submit(worker)
            try:
                assert analyzing.wait(10)
                closure = pool.submit(close, export_engine, wid, uid, sid)
                assert closing.wait(10)
                assert not closure.done()
            finally:
                release.set()
            assert run.result(timeout=20) == AnalysisRunStatus.SUCCEEDED.value
            closure.result(timeout=20)
        assert "FROM workspaces" in locks[0]
        assert "FOR NO KEY UPDATE" in locks[0]
        with Session(export_engine) as db:
            workspace = db.get(Workspace, wid)
            assert workspace is not None and workspace.status == "closing"
            row = db.scalar(select(AnalysisRun).where(AnalysisRun.workspace_id == wid))
            assert row is not None and row.status == AnalysisRunStatus.SUCCEEDED
    finally:
        event.remove(export_engine, "before_cursor_execute", record)


def test_missing_workspace_does_not_fall_back_to_other_tenant(export_engine: Engine) -> None:
    with Session(export_engine) as db:
        _, wid = seed(db)
        with pytest.raises(ValueError, match="workspace unavailable"):
            execute(db, wid + 10000)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 0
        row = execute(db, wid)
        assert row.workspace_id == wid and row.status == AnalysisRunStatus.SUCCEEDED
