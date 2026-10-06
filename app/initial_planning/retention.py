"""Bounded local cleanup, independent of capture configuration or paid access."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, select, union
from sqlalchemy.orm import Session

from app.initial_planning.models import CalibrationRow, ObservationRow, PreviewRow
from app.lifecycle.privacy import bump_workspace_export_revision, database_utc_now
from app.workspaces.models import Workspace

TABLES = (ObservationRow, CalibrationRow, PreviewRow)


def purge_expired_observations(
    session_factory: Callable[[], Session],
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    batch_limit: int = 20,
) -> int:
    """Observation expiry erases the workspace graph; derived expiry preserves observations.

    Persisted deadlines remain authoritative when capture policy is absent. A fresh
    post-lock clock decides expiry; no active-workspace admission or external IO.
    """
    if isinstance(batch_limit, bool) or not 1 <= batch_limit <= 100:
        raise ValueError("retention batch limit must be between one and one hundred")
    before = clock()
    with session_factory() as db:
        candidates = union(
            *[select(model.workspace_id).where(model.expires_at <= before) for model in TABLES]
        ).subquery()
        ids = list(
            db.scalars(
                select(candidates.c.workspace_id)
                .order_by(candidates.c.workspace_id)
                .limit(batch_limit)
            )
        )
    purged = 0
    for wid in ids:
        with session_factory() as db:
            workspace = db.scalar(
                select(Workspace.id).where(Workspace.id == wid).with_for_update(key_share=True)
            )
            if workspace is None:
                continue
            # Only actual DB-expired derived rows qualify for the trigger's no-bump
            # exemption. A fixture or lagging/ahead application clock is not proof.
            now = min(clock(), database_utc_now(db))
            expired = any(
                db.scalar(
                    select(model.id)
                    .where(model.workspace_id == wid, model.expires_at <= now)
                    .limit(1)
                )
                is not None
                for model in TABLES
            )
            if not expired:
                continue
            if (
                db.scalar(
                    select(ObservationRow.id)
                    .where(ObservationRow.workspace_id == wid, ObservationRow.expires_at <= now)
                    .limit(1)
                )
                is not None
            ):
                bump_workspace_export_revision(db, wid)
            else:
                for model in (PreviewRow, CalibrationRow):
                    db.execute(
                        delete(model).where(model.workspace_id == wid, model.expires_at <= now)
                    )
                # Expired derived rows need no counter bump: exports enforce their
                # captured deadline against fresh application AND database clocks.
                # Before-expiry raw deletions still bump through the DB trigger.
            db.commit()
            purged += 1
    return purged


def run_retention_tick(engine: Engine) -> int:
    return purge_expired_observations(lambda: Session(engine))
