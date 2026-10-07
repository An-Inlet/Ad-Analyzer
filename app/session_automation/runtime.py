"""Explicit server composition; no production policies or producers ship registered."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.optimization_candidates.contracts import CandidateDecision
from app.optimization_candidates.review_bridge import CandidateReviewRuntime
from app.optimization_candidates.selection import CandidateSelectionRuntime
from app.publication.execution_contracts import ProviderMandateBinding
from app.reported_feedback.automatic_contracts import ReportedRuleAutomaticPolicyV1
from app.session_automation.contracts import SemanticDecisionEpoch, SessionAutomaticPolicy

AutomaticPolicyDocument = SessionAutomaticPolicy | ReportedRuleAutomaticPolicyV1


@dataclass(frozen=True)
class SemanticEpochProducer:
    family: str
    source_schema: str
    environment: str
    read: Callable[[Session, CandidateDecision], SemanticDecisionEpoch] | None = None
    authorized_read: (
        Callable[[Session, CustomerPrincipal, CandidateDecision], SemanticDecisionEpoch] | None
    ) = None


@dataclass(frozen=True)
class SessionAutomationRuntime:
    selection: CandidateSelectionRuntime
    review: CandidateReviewRuntime
    policies: tuple[AutomaticPolicyDocument, ...]
    epoch_producers: tuple[SemanticEpochProducer, ...]
    clock: Callable[[], datetime]
    selection_factory: Callable[[ProviderMandateBinding], CandidateSelectionRuntime] | None = None

    def selected(self, binding: ProviderMandateBinding) -> CandidateSelectionRuntime:
        return (
            self.selection_factory(binding)
            if self.selection_factory is not None
            else self.selection
        )


def get_session_automation_runtime() -> SessionAutomationRuntime | None:
    return None
