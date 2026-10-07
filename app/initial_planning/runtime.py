"""Server-owned dependencies; no installed initial policy or native runtime."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning.contracts import InitialPlanningConfiguration
from app.initial_planning.native_budget_contracts import NativeBudgetReader
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.publication.customer_optimization_contracts import CustomerOptimizationRuntime

SessionFactory = Callable[[], Session]
Clock = Callable[[], datetime]
NativeBudgetFactory = Callable[
    [CustomerPrincipal, IdentityProvider], AbstractContextManager[NativeBudgetReader]
]


@dataclass(frozen=True)
class InitialPlanningRuntime:
    session_factory: SessionFactory
    configuration: InitialPlanningConfiguration | None = None
    native: CustomerOptimizationRuntime | None = None
    clock: Clock = lambda: datetime.now(UTC)
    profile: PlanningReportingProfileV1 | None = None
    native_budget: NativeBudgetFactory | None = None


def get_initial_planning_configuration() -> InitialPlanningConfiguration | None:
    from app.planning_reporting.runtime import configured_profile
    from app.settings import settings

    profile = configured_profile(settings)
    return profile.initial if profile else None
