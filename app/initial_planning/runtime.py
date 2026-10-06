"""Server-owned dependencies; no installed initial policy or native runtime."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.initial_planning.contracts import InitialPlanningConfiguration
from app.publication.customer_optimization_contracts import CustomerOptimizationRuntime

SessionFactory = Callable[[], Session]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class InitialPlanningRuntime:
    session_factory: SessionFactory
    configuration: InitialPlanningConfiguration | None = None
    native: CustomerOptimizationRuntime | None = None
    clock: Clock = lambda: datetime.now(UTC)


def get_initial_planning_configuration() -> InitialPlanningConfiguration | None:
    return None
