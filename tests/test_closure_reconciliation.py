"""Local queue cancellation never rewrites completed source-import evidence."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import JobRun
from app.google_connections.dispatcher import deliver_analysis
from app.google_connections.models import GoogleImportCompletion
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_analysis_closure_fence import close
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import NOW, seed


def source(db: Session, wid: int) -> int:
    job = JobRun(
        workspace_id=wid,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        job_name="closure-fixture",
        status=JobRunStatus.SUCCEEDED,
        started_at=NOW,
        finished_at=NOW,
        records_processed=7,
    )
    db.add(job)
    db.flush()
    db.add(GoogleImportCompletion(job_id=job.id, state="pending"))
    db.commit()
    return job.id


def test_closure_cancels_pending_delivery_and_preserves_source(export_engine: Engine) -> None:
    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
        job_id = source(db, wid)
    close(export_engine, wid, uid, sid)
    called: list[int] = []
    assert deliver_analysis(export_engine, lambda engine, job: called.append(job), now=NOW) == 0
    assert called == []
    with Session(export_engine) as db:
        row, job = db.get(GoogleImportCompletion, job_id), db.get(JobRun, job_id)
        assert row is not None and row.state == "canceled" and row.next_attempt_at is None
        assert job is not None and job.status == JobRunStatus.SUCCEEDED
        assert job.records_processed == 7 and job.finished_at is not None


@pytest.mark.parametrize("failed", [False, True])
def test_late_delivery_ack_cannot_resurrect_canceled_queue(
    export_engine: Engine, failed: bool
) -> None:
    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
        job_id = source(db, wid)
    entered, release = Event(), Event()

    def paused(engine: Engine, job: int) -> None:
        assert job == job_id
        entered.set()
        assert release.wait(15)
        if failed:
            raise RuntimeError("fixture late failure")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(deliver_analysis, export_engine, paused, now=NOW)
        try:
            assert entered.wait(10)
            close(export_engine, wid, uid, sid)
        finally:
            release.set()
        assert future.result(timeout=20) == 0
    with Session(export_engine) as db:
        row = db.get(GoogleImportCompletion, job_id)
        assert row is not None and row.state == "canceled"


def test_reconcile_current_observation_receipt_scope_and_legacy_running(
    export_engine: Engine,
) -> None:
    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerSession, CustomerUser
    from app.lifecycle.local_work import reconcile
    from app.lifecycle.models import LifecycleRequest, LifecycleStep
    from fastapi import HTTPException
    from sqlalchemy import select

    from tests.test_customer_identity import FakeProvider

    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
        source(db, wid)
        _, other = seed(db, "other")
        other_job = source(db, other)
        running = JobRun(
            workspace_id=wid,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            job_name="legacy",
            status=JobRunStatus.RUNNING,
            started_at=NOW,
        )
        db.add(running)
        db.commit()
        running_id = running.id
    close(export_engine, wid, uid, sid)
    with Session(export_engine) as db:
        user, session = db.get(CustomerUser, uid), db.get(CustomerSession, sid)
        assert user is not None and session is not None
        principal = CustomerPrincipal(user, session)
        request = db.scalar(select(LifecycleRequest).where(LifecycleRequest.workspace_id == wid))
        assert request is not None
        row, observation = reconcile(db, principal, FakeProvider(), wid, request.id, 2)
        assert observation["admission_fenced"] is True
        assert observation["local_records_drained"] is False
        assert observation["physical_workers_stopped"] is None
        assert observation["unknown_or_nonterminal_records"]["job_runs"] == 1
        assert any(b["code"] == "worker_not_quiescent" for b in row.blockers)
        db.commit()
        assert db.get(GoogleImportCompletion, other_job).state == "pending"  # type: ignore[union-attr]
        with pytest.raises(HTTPException) as stale:
            reconcile(db, principal, FakeProvider(), wid, request.id, 2)
        assert stale.value.status_code == 409
        db.rollback()
        # Actual terminal evidence is required; elapsed time never updates the row.
        legacy = db.get(JobRun, running_id)
        assert legacy is not None and legacy.status == JobRunStatus.RUNNING
        legacy.status, legacy.finished_at = JobRunStatus.FAILED, NOW
        db.commit()
        row, observation = reconcile(db, principal, FakeProvider(), wid, request.id, 3)
        assert observation["local_records_drained"] is True
        assert observation["physical_workers_stopped"] is None
        assert observation["external_obligations_resolved"] is False
        assert not any(b["code"] == "worker_not_quiescent" for b in row.blockers)
        assert any(b["code"] == "retention_policy_unset" for b in row.blockers)
        assert row.state == "blocked" and row.disposition_policy is None
        db.commit()
        step = db.get(LifecycleStep, (row.id, "local_quiescence_v1"))
        assert step is not None and step.request_revision == 4
        assert step.evidence_digest == observation["durable_receipt"]["evidence_digest"]
        assert observation["durable_receipt"]["historical_payload_retained"] is False


def test_reconciliation_failure_rolls_back_queue_and_receipt(
    export_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.lifecycle import local_work
    from app.lifecycle.models import LifecycleRequest, LifecycleStep
    from sqlalchemy import select

    from tests.test_customer_identity import FakeProvider

    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
    close(export_engine, wid, uid, sid)
    with Session(export_engine) as db:
        from app.customers.access import CustomerPrincipal
        from app.customers.models import CustomerSession, CustomerUser

        user, session = db.get(CustomerUser, uid), db.get(CustomerSession, sid)
        assert user is not None and session is not None
        principal = CustomerPrincipal(user, session)
        # A pre-upgrade pending row is not evidence of a newly authorized import.
        legacy_job = source(db, wid)
        row = db.scalar(select(LifecycleRequest).where(LifecycleRequest.workspace_id == wid))
        assert row is not None
        before = db.get(LifecycleStep, (row.id, "analysis_queue_cancel"))
        assert before is not None
        old_digest = before.evidence_digest

        def interrupted(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("interrupted observation")

        monkeypatch.setattr(local_work, "observe", interrupted)
        with pytest.raises(RuntimeError, match="interrupted observation"):
            local_work.reconcile(db, principal, FakeProvider(), wid, row.id, 2)
        db.rollback()
        assert row.revision == 2
        pending = db.get(GoogleImportCompletion, legacy_job)
        assert pending is not None and pending.state == "pending"
        assert before.evidence_digest == old_digest
        assert db.get(LifecycleStep, (row.id, "local_quiescence_v1")) is None


def test_unknown_work_family_fails_closed() -> None:
    from app.database.session import Base
    from app.lifecycle.local_work import verify_work_registry
    from sqlalchemy import Column, Integer, Table

    future = Table("future_worker_runs", Base.metadata, Column("id", Integer, primary_key=True))
    try:
        with pytest.raises(ValueError, match="local work classification incomplete"):
            verify_work_registry()
    finally:
        Base.metadata.remove(future)


def test_postgres_reconcile_refreshes_session_after_workspace_wait(export_engine: Engine) -> None:
    import time

    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerSession, CustomerUser
    from app.lifecycle.local_work import reconcile
    from app.lifecycle.models import LifecycleRequest
    from app.workspaces.locking import lock_workspace_row
    from fastapi import HTTPException
    from sqlalchemy import select, text

    from tests.test_customer_identity import FakeProvider

    if export_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL authority lock wait")
    with Session(export_engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
    close(export_engine, wid, uid, sid)
    with Session(export_engine) as holder:
        lock_workspace_row(holder, wid)
        request_id = holder.scalar(
            select(LifecycleRequest.id).where(LifecycleRequest.workspace_id == wid)
        )
        assert request_id is not None
        holder_pid = holder.scalar(text("select pg_backend_pid()"))
        ready = Event()
        worker_pid: list[int] = []

        def worker() -> int:
            with Session(export_engine) as db:
                user, session = db.get(CustomerUser, uid), db.get(CustomerSession, sid)
                assert user is not None and session is not None
                worker_pid.append(int(db.scalar(text("select pg_backend_pid()"))))
                ready.set()
                try:
                    reconcile(
                        db, CustomerPrincipal(user, session), FakeProvider(), wid, request_id, 2
                    )
                except HTTPException as exc:
                    return exc.status_code
                return 200

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            try:
                assert ready.wait(5)
                deadline = time.monotonic() + 5
                with Session(export_engine) as observer:
                    while time.monotonic() < deadline:
                        if holder_pid in observer.scalar(
                            text("select pg_blocking_pids(:pid)"), {"pid": worker_pid[0]}
                        ):
                            break
                        time.sleep(0.01)
                    else:
                        pytest.fail("reconciliation did not wait on workspace authority")
                session = holder.get(CustomerSession, sid)
                assert session is not None
                session.expires_at = int(time.time()) - 1
                holder.commit()
            finally:
                holder.rollback()
            assert future.result(timeout=10) == 401
        request = holder.get(LifecycleRequest, request_id)
        assert request is not None and request.revision == 2
