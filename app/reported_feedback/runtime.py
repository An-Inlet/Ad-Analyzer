"""Server configuration only. No operational profile is installed by default."""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.initial_planning.runtime import InitialPlanningRuntime
from app.reported_feedback.contracts import ReportedFeedbackPolicyV1, ReportedWindowPolicyV1


@dataclass(frozen=True)
class ReportedFeedbackRuntime:
    initial: InitialPlanningRuntime
    window_policy: ReportedWindowPolicyV1 | None = None
    feedback_policy: ReportedFeedbackPolicyV1 | None = None

    @property
    def session_factory(self) -> Callable[[], Session]:
        return self.initial.session_factory


def get_reported_feedback_runtime() -> ReportedFeedbackRuntime | None:
    return None
