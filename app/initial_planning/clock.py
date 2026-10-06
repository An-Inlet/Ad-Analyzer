"""Fresh delivery expiry clock; a lagging app clock cannot revive DB-expired data."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.initial_planning.runtime import InitialPlanningRuntime
from app.lifecycle.privacy import database_utc_now
from app.meta.security import utc


def effective_now(db: Session, runtime: InitialPlanningRuntime) -> datetime:
    return max(utc(runtime.clock()), database_utc_now(db))
