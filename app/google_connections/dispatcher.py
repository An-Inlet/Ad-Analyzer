"""Explicit scoped fixture dispatcher and durable post-import analysis delivery."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import Engine, delete, or_, select
from sqlalchemy.orm import Session

from app.google_connections.contracts import GoogleReadTransport
from app.google_connections.models import (
    GoogleAuthorization,
    GoogleCustomerConnection,
    GoogleImportCompletion,
)
from app.google_connections.service import tick
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
            except Exception:
                db.rollback()
                failed += 1  # Deliberately no raw transport/account/error payload logging.
    return {"selected": len(selected), "completed_windows": completed, "failed": failed}


def deliver_analysis(
    engine: Engine, analyze: Callable[[Engine, int], object], limit: int = 20
) -> int:
    # Analysis already has unique source-job/run-key protection. Keep the outbox pending
    # across failures/crashes; successful source imports are never rerun for analysis failure.
    with Session(engine) as db:
        ids = list(
            db.scalars(
                select(GoogleImportCompletion.job_id)
                .where(GoogleImportCompletion.state == "pending")
                .order_by(GoogleImportCompletion.job_id)
                .limit(max(1, min(limit, 100)))
            )
        )
    delivered = 0
    for job_id in ids:
        try:
            analyze(engine, job_id)
        except Exception:
            continue
        with Session(engine) as db:
            row = db.get(GoogleImportCompletion, job_id)
            if row is not None:
                row.state = "delivered"
                db.commit()
                delivered += 1
    return delivered
