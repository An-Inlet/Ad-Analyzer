"""Historical failure bookkeeping fences on disposable SQLite and PostgreSQL."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import JobRun
from app.ads.services import GoogleAdsSyncError, SyncFailureClassification
from app.imports.scope import AdvertisingImportScope
from app.jobs.reliability import (
    _create_authoritative_job_run,
    _FailedJobIdentity,
    _finalize_failed_job_run,
    _finalize_failed_job_run_on_engine,
)
from app.workspaces.locking import lock_workspace_row
from app.workspaces.models import Workspace, WorkspaceIntegration
from sqlalchemy import Engine, create_engine, delete, event, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from tests.import_scope_helpers import seed_google_scope
from tests.test_customer_identity import customer_engine as customer_engine


def make_job(engine: Engine) -> _FailedJobIdentity:
    with Session(engine, expire_on_commit=False) as db:
        job = _create_authoritative_job_run(
            db, AdvertisingImportScope(1, 1, 1, AdvertisingPlatform.GOOGLE_ADS)
        )
        return _FailedJobIdentity.capture(job)


def values(engine: Engine, identity: _FailedJobIdentity) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(select(JobRun.__table__).where(JobRun.id == identity.id)).first()
        return dict(row._mapping) if row else None


def test_original_identity_and_terminal_rows_are_preserved(customer_engine: Engine) -> None:
    engine = customer_engine
    with Session(engine) as db:
        seed_google_scope(db)
    for fresh_engine in (False, True):
        for change in (
            "deleted",
            "succeeded",
            "failed",
            "name",
            "start",
            "created",
            "unfinished",
            "account",
            "connection",
            "platform",
            "workspace",
            "pending",
        ):
            identity = make_job(engine)
            with Session(engine) as db:
                if change == "deleted":
                    db.execute(delete(JobRun).where(JobRun.id == identity.id))
                else:
                    job = db.get(JobRun, identity.id)
                    assert job
                    if change in ("succeeded", "failed"):
                        job.status = JobRunStatus(change)
                        job.finished_at = datetime.now(UTC)
                        job.error_message = "original terminal detail"
                        job.records_processed = 17
                    elif change == "pending":
                        job.status = JobRunStatus.PENDING
                    elif change in ("account", "connection", "platform", "workspace"):
                        job.account_id = None
                        if change != "account":
                            job.connection_id = None
                        if change == "platform":
                            job.platform = AdvertisingPlatform.META_ADS
                        if change == "workspace":
                            other = Workspace(
                                id=2 + int(fresh_engine),
                                slug=f"other-{int(fresh_engine)}", name="Other", client_name="Other"
                            )
                            db.add(other)
                            db.flush()
                            job.workspace_id = other.id
                    elif change == "name":
                        job.job_name = "google_customer_range_read"
                    elif change == "start":
                        job.started_at += timedelta(seconds=1)
                    elif change == "created":
                        job.created_at += timedelta(seconds=1)
                    else:
                        job.finished_at = datetime.now(UTC)
                db.commit()
            before = values(engine, identity)
            if fresh_engine:
                _finalize_failed_job_run_on_engine(engine, identity, ValueError(), 1)
            else:
                with Session(engine) as db:
                    _finalize_failed_job_run(db, identity, ValueError(), 1)
            assert values(engine, identity) == before, (fresh_engine, change)


def test_rollback_and_revoked_source_allow_only_historical_failure(customer_engine: Engine) -> None:
    engine = customer_engine
    with Session(engine) as db:
        seed_google_scope(db)
    identities = [make_job(engine), make_job(engine)]
    with Session(engine) as db:
        db.execute(update(Workspace).where(Workspace.id == 1).values(status="closing"))
        db.execute(
            update(WorkspaceIntegration)
            .where(WorkspaceIntegration.id == 1)
            .values(status="revoked")
        )
        db.commit()
    for index, identity in enumerate(identities):
        before = values(engine, identity)
        assert before
        if index:
            _finalize_failed_job_run_on_engine(engine, identity, ValueError("private"), 2)
        else:
            with Session(engine) as db:
                job = db.get(JobRun, identity.id)
                assert job
                job.job_name = "uncommitted stale mutation"
                job.records_processed = 999
                db.flush()
                _finalize_failed_job_run(db, identity, ValueError("private"), 2)
        after = values(engine, identity)
        assert after
        for field in (
            "id",
            "workspace_id",
            "connection_id",
            "account_id",
            "platform",
            "job_name",
            "started_at",
            "created_at",
        ):
            assert after[field] == before[field]
        assert after["status"] == JobRunStatus.FAILED
        assert after["finished_at"] is not None and after["records_processed"] == 0
        assert "private" not in after["error_message"]
        _finalize_failed_job_run_on_engine(engine, identity, RuntimeError(), 99)
        assert values(engine, identity) == after


def test_workspace_gate_blocks_finalization(customer_engine: Engine, tmp_path: Path) -> None:
    engine = customer_engine
    with Session(engine) as db:
        seed_google_scope(db)
    identity = make_job(engine)
    copied = engine.dialect.name == "sqlite"
    if copied:
        path = tmp_path / "finalization.db"
        with engine.connect() as connection, closing(sqlite3.connect(path)) as destination:
            driver = connection.connection.driver_connection
            assert driver is not None
            driver.backup(destination)
        engine = create_engine(
            f"sqlite:///{path}", poolclass=NullPool, connect_args={"timeout": 0.25}
        )

        @event.listens_for(engine, "connect")
        def foreign_keys(connection: Any, _record: Any) -> None:
            connection.execute("PRAGMA foreign_keys=ON")
            assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    try:
        before = values(engine, identity)
        with Session(engine) as holder:
            if copied:
                holder.execute(text("BEGIN IMMEDIATE"))
            assert lock_workspace_row(holder, 1)
            # The failure writer must block on the original workspace, not merely
            # the job row. PostgreSQL timeout is connection-level across rollback.
            with engine.connect() as connection:
                if not copied:
                    connection.execute(text("SET lock_timeout = '250ms'"))
                    connection.commit()
                try:
                    with Session(connection) as writer:
                        with pytest.raises(DBAPIError) as error:
                            _finalize_failed_job_run(writer, identity, ValueError(), 1)
                        if copied:
                            assert "database is locked" in str(error.value)
                        else:
                            assert getattr(error.value.orig, "sqlstate", None) == "55P03"
                finally:
                    if not copied:
                        connection.execute(text("RESET lock_timeout"))
                        connection.commit()
            holder.rollback()
        assert values(engine, identity) == before
        _finalize_failed_job_run_on_engine(engine, identity, ValueError(), 1)
        after = values(engine, identity)
        assert after and after["status"] == JobRunStatus.FAILED
        # A success transaction already holding the gate wins before a late failure.
        racing = make_job(engine)
        entered, done = Event(), Event()

        def late_failure() -> None:
            entered.set()
            try:
                _finalize_failed_job_run_on_engine(engine, racing, ValueError(), 1)
            finally:
                done.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with Session(engine) as success:
                if copied:
                    success.execute(text("BEGIN IMMEDIATE"))
                assert lock_workspace_row(success, 1)
                job = success.get(JobRun, racing.id)
                assert job
                job.status = JobRunStatus.SUCCEEDED
                job.finished_at = datetime.now(UTC)
                job.records_processed = 7
                success.flush()
                future = pool.submit(late_failure)
                assert entered.wait(2)
                assert not done.wait(0.05)
                success.commit()
            future.result(timeout=5)
        won = values(engine, racing)
        assert won and won["status"] == JobRunStatus.SUCCEEDED
        assert won["records_processed"] == 7 and won["error_message"] is None
    finally:
        if copied:
            engine.dispose()


def test_commit_uncertainty_preserves_committed_failure(customer_engine: Engine) -> None:
    engine = customer_engine
    with Session(engine) as db:
        seed_google_scope(db)
    identity = make_job(engine)

    class LostAcknowledgement(Session):
        def commit(self) -> None:
            super().commit()
            raise RuntimeError("lost commit acknowledgement")

    with LostAcknowledgement(engine) as db:
        with pytest.raises(GoogleAdsSyncError) as error:
            _finalize_failed_job_run(db, identity, ValueError(), 1)
        assert error.value.classification is SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
    before = values(engine, identity)
    assert before and before["status"] == JobRunStatus.FAILED
    _finalize_failed_job_run_on_engine(engine, identity, RuntimeError(), 2)
    assert values(engine, identity) == before
