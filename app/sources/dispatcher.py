from datetime import datetime, timedelta

from sqlalchemy import Engine, delete, or_, select
from sqlalchemy.orm import Session

from app.sources.advertising import tick
from app.sources.contracts import SourceTransport
from app.sources.models import SourceAuthorization, SourceConnection
from app.workspaces.models import Workspace, WorkspaceIntegration


def run_tiktok(
    engine: Engine, transport: SourceTransport, now: datetime, limit: int = 20
) -> dict[str, int]:
    with Session(engine) as db:
        db.execute(delete(SourceAuthorization).where(SourceAuthorization.expires_at <= now))
        db.commit()
        rows = list(
            db.execute(
                select(
                    SourceConnection.workspace_id, SourceConnection.id, SourceConnection.generation
                )
                .join(Workspace, Workspace.id == SourceConnection.workspace_id)
                .join(
                    WorkspaceIntegration, WorkspaceIntegration.id == SourceConnection.integration_id
                )
                .where(
                    SourceConnection.provider == "tiktok_ads",
                    SourceConnection.status == "connected",
                    Workspace.status == "active",
                    WorkspaceIntegration.status == "active",
                    or_(
                        SourceConnection.next_attempt_at.is_(None),
                        SourceConnection.next_attempt_at <= now,
                    ),
                )
                .order_by(SourceConnection.next_attempt_at.asc().nullsfirst(), SourceConnection.id)
                .limit(max(1, min(limit, 100)))
            )
        )
    completed, failed = 0, 0
    for wid, cid, generation in rows:
        with Session(engine) as db:
            try:
                if tick(db, wid, cid, generation, transport, now) is not None:
                    completed += 1
            except Exception:
                db.rollback()
                # A valid but rejected page must not monopolize the first due slot.
                # Recheck generation/status after rollback: never poison a reconnect.
                row = db.scalar(
                    select(SourceConnection)
                    .where(
                        SourceConnection.id == cid,
                        SourceConnection.workspace_id == wid,
                        SourceConnection.generation == generation,
                        SourceConnection.status == "connected",
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if row is not None:
                    row.next_attempt_at = now + timedelta(minutes=5)
                    if row.error_code != "read_unavailable":
                        row.error_code = "import_rejected"
                        row.cursor, row.staged = None, {}
                    db.commit()
                failed += 1
    return {"selected": len(rows), "completed_windows": completed, "failed": failed}
