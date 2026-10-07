"""One pinned server policy, actual caller DB bind, no global customer principal."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy.orm import Session

from app.collectors.owned_meta_budget import owned_meta_budget_reader
from app.initial_planning.runtime import InitialPlanningRuntime
from app.planning_reporting.configuration import load_planning_reporting_profile
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.reported_feedback.runtime import ReportedFeedbackRuntime
from app.settings import Settings


@lru_cache(maxsize=4)
def _pinned_profile(path: str | None, digest: str | None) -> PlanningReportingProfileV1 | None:
    return load_planning_reporting_profile(path, digest)


def configured_profile(configuration: Settings) -> PlanningReportingProfileV1 | None:
    """Pin canonical policy for this configured process; never reread provider data."""
    return _pinned_profile(
        configuration.planning_reporting_profile_path,
        configuration.planning_reporting_profile_digest,
    )


def planning_clock() -> datetime:
    """Clock seam only; production consumers still enforce fresh DB/session guards."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class PlanningReportingBundle:
    profile: PlanningReportingProfileV1
    initial: InitialPlanningRuntime
    reported: ReportedFeedbackRuntime


def assemble_planning_reporting(
    sessions: Callable[[], Session],
    profile: PlanningReportingProfileV1,
    configuration: Settings,
    *,
    clock: Callable[[], datetime] | None = None,
) -> PlanningReportingBundle:
    effective_clock = clock or planning_clock
    initial = InitialPlanningRuntime(
        session_factory=sessions,
        configuration=profile.initial,
        profile=profile,
        native_budget=lambda principal, provider: owned_meta_budget_reader(
            sessions, principal, provider, profile, configuration, clock=effective_clock
        ),
        clock=effective_clock,
    )
    reported = ReportedFeedbackRuntime(initial, profile.windows, profile.feedback)
    return PlanningReportingBundle(profile, initial, reported)


def configured_bundle(
    sessions: Callable[[], Session], configuration: Settings
) -> PlanningReportingBundle | None:
    profile = configured_profile(configuration)
    return assemble_planning_reporting(sessions, profile, configuration) if profile else None
