"""Explicit scoped fixture dispatcher and durable post-import analysis delivery."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, delete, or_, select
from sqlalchemy.orm import Session

from app.ads.models import JobRun
from app.google_connections.contracts import GoogleReadTransport
from app.google_connections.models import (
    GoogleAuthorization,
    GoogleCustomerConnection,
    GoogleImportCompletion,
)
from app.google_connections.service import GoogleReadUnavailable, tick
from app.workspaces.locking import lock_workspace_row
from app.workspaces.models import Workspace, WorkspaceIntegration


def run_imports(
    engine: Engine, transport: GoogleReadTransport, now: datetime, limit: int = 20
) -> dict[str, int]:
    with Session(engine) as db:
        db.execute(delete(GoogleAuthorization).where(GoogleAuthorization.expires_at <= now))
        db.commit()
        selected = list(
            db.execute(
                select(
                    GoogleCustomerConnection.workspace_id,
                    GoogleCustomerConnection.id,
                    GoogleCustomerConnection.generation,
                )
                .join(Workspace, Workspace.id == GoogleCustomerConnection.workspace_id)
                .join(
                    WorkspaceIntegration,
                    WorkspaceIntegration.id == GoogleCustomerConnection.integration_id,
                )
                .where(
                    Workspace.status == "active",
                    WorkspaceIntegration.status == "active",
                    GoogleCustomerConnection.status == "connected",
                    or_(
                        GoogleCustomerConnection.next_attempt_at.is_(None),
                        GoogleCustomerConnection.next_attempt_at <= now,
                    ),
                )
                .order_by(
                    GoogleCustomerConnection.next_attempt_at.asc().nullsfirst(),
                    GoogleCustomerConnection.last_sync_at.asc().nullsfirst(),
                    GoogleCustomerConnection.id,
                )
                .limit(max(1, min(limit, 100)))
            )
        )
    completed, failed = 0, 0
    for wid, cid, generation in selected:
        with Session(engine) as db:
            try:
                if tick(db, wid, cid, generation, transport, now) is not None:
                    completed += 1
            except Exception as exc:
                db.rollback()
                # A rollback must not leave an invalid final page permanently queued.
                # Lock and recheck after rollback to avoid poisoning fresh consent.
                row = db.scalar(
                    select(GoogleCustomerConnection)
                    .where(
                        GoogleCustomerConnection.id == cid,
                        GoogleCustomerConnection.workspace_id == wid,
                        GoogleCustomerConnection.generation == generation,
                        GoogleCustomerConnection.status == "connected",
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if row is not None:
                    row.next_attempt_at = now + timedelta(minutes=5)
                    if not isinstance(exc, GoogleReadUnavailable):
                        row.error_code = "import_rejected"
                        row.cursor, row.staged = None, {}
                    db.commit()
                failed += 1  # No raw provider/account/error payload logging.
    return {"selected": len(selected), "completed_windows": completed, "failed": failed}


def deliver_analysis(
    engine: Engine,
    analyze: Callable[[Engine, int], object],
    limit: int = 20,
    *,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(UTC)
    # Analysis already has unique source-job/run-key protection. Keep the outbox pending
    # across failures/crashes; successful source imports are never rerun for analysis failure.
    with Session(engine) as db:
        ids = list(
            db.scalars(
                select(GoogleImportCompletion.job_id)
                .join(JobRun, JobRun.id == GoogleImportCompletion.job_id)
                .join(Workspace, Workspace.id == JobRun.workspace_id)
                .where(
                    Workspace.status == "active",
                    GoogleImportCompletion.state == "pending",
                    or_(
                        GoogleImportCompletion.next_attempt_at.is_(None),
                        GoogleImportCompletion.next_attempt_at <= current,
                    ),
                )
                .order_by(GoogleImportCompletion.job_id)
                .limit(max(1, min(limit, 100)))
            )
        )
    delivered = 0
    for job_id in ids:
        # Selection is not authority. Release this transaction before invoking analysis,
        # which independently reacquires its workspace guard after its durable claim.
        with Session(engine) as db:
            wid = db.scalar(select(JobRun.workspace_id).where(JobRun.id == job_id))
            if wid is None:
                continue
            workspace = lock_workspace_row(db, wid)
            row = db.get(GoogleImportCompletion, job_id, populate_existing=True)
            if (
                workspace is None
                or workspace.status != "active"
                or row is None
                or row.state != "pending"
            ):
                continue
        try:
            analyze(engine, job_id)
        except Exception:
            with Session(engine) as db:
                workspace = lock_workspace_row(db, wid)
                row = db.get(GoogleImportCompletion, job_id, populate_existing=True)
                if (
                    workspace is not None
                    and workspace.status == "active"
                    and row is not None
                    and row.state == "pending"
                ):
                    row.next_attempt_at = current + timedelta(minutes=5)
                    db.commit()
            continue
        with Session(engine) as db:
            workspace = lock_workspace_row(db, wid)
            row = db.get(GoogleImportCompletion, job_id, populate_existing=True)
            if (
                workspace is not None
                and workspace.status == "active"
                and row is not None
                and row.state == "pending"
            ):
                row.state = "delivered"
                db.commit()
                delivered += 1
    return delivered
