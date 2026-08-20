from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import Recommendation, RecommendationAudit
from app.analysis.enums import AnalysisRunStatus
from app.analysis.models import AnalysisRun
from app.learning.decision import DecisionLearningService, DecisionLearningSnapshot

WEEKLY_LEARNING_REPORT_POLICY_VERSION = "v1"

WeeklyLearningSummaryState = Literal["attention", "evidence_limited", "stable"]
WeeklyLearningEvidenceState = Literal["no_history", "limited", "established"]
WeeklyLearningSuggestionPriority = Literal["attention", "review", "monitor"]

_DECISION_ACTIONS = frozenset({"approved", "rejected"})
_RATE_QUANTUM = Decimal("0.0001")
_LOW_ACCEPTANCE_RATE = Decimal("0.4000")
_ACCEPTANCE_DECLINE = Decimal("-0.2000")
_FINDING_DENSITY_INCREASE = Decimal("0.2500")
_HIGH_DEDUPLICATION_RATE = Decimal("0.7500")


@dataclass(frozen=True)
class WeeklyLearningWindow:
    date_from: date
    date_to: date

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.date_from, time.min, tzinfo=UTC)

    @property
    def end_exclusive(self) -> datetime:
        return datetime.combine(self.date_to + timedelta(days=1), time.min, tzinfo=UTC)


@dataclass(frozen=True)
class WeeklyLearningActivity:
    analysis_run_count: int
    findings_count: int
    high_severity_findings_count: int
    proposals_generated_count: int
    proposals_deduplicated_count: int
    decision_count: int
    approved_count: int
    rejected_count: int
    acceptance_rate: Decimal | None

    @property
    def findings_per_run(self) -> Decimal | None:
        if self.analysis_run_count == 0:
            return None
        return _rate(self.findings_count, self.analysis_run_count)


@dataclass(frozen=True)
class WeeklyLearningChanges:
    analysis_run_count: int
    findings_count: int
    high_severity_findings_count: int
    proposals_generated_count: int
    proposals_deduplicated_count: int
    decision_count: int
    approved_count: int
    rejected_count: int
    findings_per_run: Decimal | None
    acceptance_rate: Decimal | None


@dataclass(frozen=True)
class WeeklyLearningSuggestion:
    code: str
    priority: WeeklyLearningSuggestionPriority
    title: str
    evidence: str
    suggested_improvement: str
    automatic_change: bool = False


@dataclass(frozen=True)
class WeeklyLearningSafety:
    local_data_only: bool = True
    actor_identity_used: bool = False
    reason_text_used: bool = False
    search_term_text_used: bool = False
    external_service_called: bool = False
    automatic_change_applied: bool = False


@dataclass(frozen=True)
class WeeklyLearningReport:
    workspace_id: int
    policy_version: str
    report_key: str
    reporting_as_of: date
    summary_state: WeeklyLearningSummaryState
    evidence_state: WeeklyLearningEvidenceState
    current_period: WeeklyLearningWindow
    comparison_period: WeeklyLearningWindow
    current: WeeklyLearningActivity
    previous: WeeklyLearningActivity
    changes: WeeklyLearningChanges
    decision_learning: DecisionLearningSnapshot
    suggestions: tuple[WeeklyLearningSuggestion, ...]
    safety: WeeklyLearningSafety


@dataclass(frozen=True)
class _DecisionEvent:
    recommendation_id: int
    action: str
    decided_at: datetime


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _rate(numerator: int, denominator: int) -> Decimal:
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        _RATE_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _change(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None or previous is None:
        return None
    return (current - previous).quantize(_RATE_QUANTUM, rounding=ROUND_HALF_UP)


def _percent(value: Decimal) -> str:
    percent = (value * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{percent}%"


def _report_windows(reporting_as_of: date) -> tuple[WeeklyLearningWindow, WeeklyLearningWindow]:
    current_week_start = reporting_as_of - timedelta(days=reporting_as_of.weekday())
    current_end = current_week_start - timedelta(days=1)
    current = WeeklyLearningWindow(
        date_from=current_end - timedelta(days=6),
        date_to=current_end,
    )
    comparison_end = current.date_from - timedelta(days=1)
    comparison = WeeklyLearningWindow(
        date_from=comparison_end - timedelta(days=6),
        date_to=comparison_end,
    )
    return current, comparison


def _in_window(value: datetime, window: WeeklyLearningWindow) -> bool:
    resolved = _as_utc(value)
    return window.start_at <= resolved < window.end_exclusive


class WeeklyLearningReportService:
    """Build a deterministic, read-only comparison from local aggregate evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def build(
        self,
        workspace_id: int,
        *,
        as_of: date | datetime | None = None,
    ) -> WeeklyLearningReport:
        reporting_as_of = self._reporting_date(as_of)
        current_period, comparison_period = _report_windows(reporting_as_of)
        analysis_runs = self._analysis_runs(
            workspace_id,
            comparison_period.start_at,
            current_period.end_exclusive,
        )
        generated_at = self._generated_proposals(
            workspace_id,
            comparison_period.start_at,
            current_period.end_exclusive,
        )
        decisions = self._first_decisions(
            workspace_id,
            through=current_period.end_exclusive,
        )
        current = self._activity(current_period, analysis_runs, generated_at, decisions)
        previous = self._activity(comparison_period, analysis_runs, generated_at, decisions)
        changes = WeeklyLearningChanges(
            analysis_run_count=current.analysis_run_count - previous.analysis_run_count,
            findings_count=current.findings_count - previous.findings_count,
            high_severity_findings_count=(
                current.high_severity_findings_count - previous.high_severity_findings_count
            ),
            proposals_generated_count=(
                current.proposals_generated_count - previous.proposals_generated_count
            ),
            proposals_deduplicated_count=(
                current.proposals_deduplicated_count - previous.proposals_deduplicated_count
            ),
            decision_count=current.decision_count - previous.decision_count,
            approved_count=current.approved_count - previous.approved_count,
            rejected_count=current.rejected_count - previous.rejected_count,
            findings_per_run=_change(current.findings_per_run, previous.findings_per_run),
            acceptance_rate=_change(current.acceptance_rate, previous.acceptance_rate),
        )
        learning = DecisionLearningService(self.session).snapshot(
            workspace_id,
            through=current_period.end_exclusive,
        )
        evidence_state = self._evidence_state(learning)
        suggestions = self._suggestions(
            current=current,
            previous=previous,
            changes=changes,
            learning=learning,
        )
        summary_state: WeeklyLearningSummaryState
        if any(item.priority == "attention" for item in suggestions):
            summary_state = "attention"
        elif evidence_state != "established":
            summary_state = "evidence_limited"
        else:
            summary_state = "stable"
        return WeeklyLearningReport(
            workspace_id=workspace_id,
            policy_version=WEEKLY_LEARNING_REPORT_POLICY_VERSION,
            report_key=f"weekly-learning:{current_period.date_to.isoformat()}",
            reporting_as_of=reporting_as_of,
            summary_state=summary_state,
            evidence_state=evidence_state,
            current_period=current_period,
            comparison_period=comparison_period,
            current=current,
            previous=previous,
            changes=changes,
            decision_learning=learning,
            suggestions=suggestions,
            safety=WeeklyLearningSafety(),
        )

    @staticmethod
    def _reporting_date(as_of: date | datetime | None) -> date:
        if as_of is None:
            return datetime.now(UTC).date()
        if isinstance(as_of, datetime):
            return _as_utc(as_of).date()
        return as_of

    def _analysis_runs(
        self,
        workspace_id: int,
        start_at: datetime,
        end_exclusive: datetime,
    ) -> tuple[AnalysisRun, ...]:
        rows = self.session.scalars(
            select(AnalysisRun)
            .where(
                AnalysisRun.workspace_id == workspace_id,
                AnalysisRun.status == AnalysisRunStatus.SUCCEEDED,
                AnalysisRun.scheduled_for >= start_at,
                AnalysisRun.scheduled_for < end_exclusive,
            )
            .order_by(AnalysisRun.scheduled_for.asc(), AnalysisRun.id.asc())
        ).all()
        return tuple(rows)

    def _generated_proposals(
        self,
        workspace_id: int,
        start_at: datetime,
        end_exclusive: datetime,
    ) -> tuple[datetime, ...]:
        rows = self.session.scalars(
            select(Recommendation.generated_at)
            .where(
                Recommendation.workspace_id == workspace_id,
                Recommendation.generated_at >= start_at,
                Recommendation.generated_at < end_exclusive,
            )
            .order_by(Recommendation.generated_at.asc(), Recommendation.id.asc())
        ).all()
        return tuple(rows)

    def _first_decisions(
        self,
        workspace_id: int,
        *,
        through: datetime,
    ) -> tuple[_DecisionEvent, ...]:
        rows = (
            self.session.execute(
                select(
                    Recommendation.id,
                    RecommendationAudit.action,
                    RecommendationAudit.created_at,
                )
                .join(
                    RecommendationAudit,
                    RecommendationAudit.recommendation_id == Recommendation.id,
                )
                .where(
                    Recommendation.workspace_id == workspace_id,
                    RecommendationAudit.action.in_(_DECISION_ACTIONS),
                    RecommendationAudit.created_at < through,
                )
                .order_by(RecommendationAudit.created_at.asc(), RecommendationAudit.id.asc())
            )
            .tuples()
            .all()
        )
        events: list[_DecisionEvent] = []
        decided_recommendations: set[int] = set()
        for recommendation_id, action, decided_at in rows:
            if recommendation_id in decided_recommendations:
                continue
            decided_recommendations.add(recommendation_id)
            events.append(
                _DecisionEvent(
                    recommendation_id=recommendation_id,
                    action=action,
                    decided_at=decided_at,
                )
            )
        return tuple(events)

    @staticmethod
    def _activity(
        window: WeeklyLearningWindow,
        analysis_runs: tuple[AnalysisRun, ...],
        generated_at: tuple[datetime, ...],
        decisions: tuple[_DecisionEvent, ...],
    ) -> WeeklyLearningActivity:
        period_runs = tuple(row for row in analysis_runs if _in_window(row.scheduled_for, window))
        period_decisions = tuple(
            event for event in decisions if _in_window(event.decided_at, window)
        )
        approved_count = sum(event.action == "approved" for event in period_decisions)
        rejected_count = sum(event.action == "rejected" for event in period_decisions)
        decision_count = approved_count + rejected_count
        return WeeklyLearningActivity(
            analysis_run_count=len(period_runs),
            findings_count=sum(row.findings_count for row in period_runs),
            high_severity_findings_count=sum(
                row.high_severity_findings_count for row in period_runs
            ),
            proposals_generated_count=sum(_in_window(value, window) for value in generated_at),
            proposals_deduplicated_count=sum(
                row.recommendations_deduplicated_count for row in period_runs
            ),
            decision_count=decision_count,
            approved_count=approved_count,
            rejected_count=rejected_count,
            acceptance_rate=(_rate(approved_count, decision_count) if decision_count > 0 else None),
        )

    @staticmethod
    def _evidence_state(learning: DecisionLearningSnapshot) -> WeeklyLearningEvidenceState:
        if learning.decision_count == 0:
            return "no_history"
        if any(profile.evidence_state == "established" for profile in learning.profiles):
            return "established"
        return "limited"

    @staticmethod
    def _suggestions(
        *,
        current: WeeklyLearningActivity,
        previous: WeeklyLearningActivity,
        changes: WeeklyLearningChanges,
        learning: DecisionLearningSnapshot,
    ) -> tuple[WeeklyLearningSuggestion, ...]:
        suggestions: list[WeeklyLearningSuggestion] = []
        if current.analysis_run_count == 0:
            suggestions.append(
                WeeklyLearningSuggestion(
                    code="restore_analysis_coverage",
                    priority="attention",
                    title="Restore weekly analysis evidence",
                    evidence="No successful local analysis runs were recorded in the report week.",
                    suggested_improvement=(
                        "Verify the cadence scheduler and synchronized-data readiness before "
                        "changing analyzer rules."
                    ),
                )
            )

        established_profiles = tuple(
            profile for profile in learning.profiles if profile.evidence_state == "established"
        )
        if learning.decision_count == 0:
            suggestions.append(
                WeeklyLearningSuggestion(
                    code="collect_operator_decisions",
                    priority="monitor",
                    title="Collect decision evidence",
                    evidence="No approve/reject decisions were available through the report week.",
                    suggested_improvement=(
                        "Keep learning neutral and collect operator decisions before proposing "
                        "changes to analyzer behavior."
                    ),
                )
            )
        elif not established_profiles:
            suggestions.append(
                WeeklyLearningSuggestion(
                    code="build_profile_evidence",
                    priority="monitor",
                    title="Build evidence for each signal",
                    evidence=(
                        f"{learning.decision_count} total decisions are available, but no "
                        "signal/scope/action profile has five decisions yet."
                    ),
                    suggested_improvement=(
                        "Continue structured review until at least one profile reaches established "
                        "evidence; do not infer threshold changes from limited samples."
                    ),
                )
            )

        low_acceptance_profiles = sorted(
            (
                profile
                for profile in established_profiles
                if profile.acceptance_rate <= _LOW_ACCEPTANCE_RATE
            ),
            key=lambda profile: (
                profile.acceptance_rate,
                -profile.decision_count,
                profile.recommendation_type,
                profile.scope_type,
                profile.review_action,
            ),
        )
        for profile in low_acceptance_profiles[:3]:
            suggestions.append(
                WeeklyLearningSuggestion(
                    code="review_low_acceptance_profile",
                    priority="attention",
                    title="Review a low-acceptance analyzer profile",
                    evidence=(
                        f"{profile.recommendation_type} / {profile.scope_type} / "
                        f"{profile.review_action}: {profile.approved_count} of "
                        f"{profile.decision_count} approved ({_percent(profile.acceptance_rate)})."
                    ),
                    suggested_improvement=(
                        "Review the deterministic rule's precision, rationale, and supporting "
                        "metrics in a separately approved change; never alter thresholds "
                        "automatically."
                    ),
                )
            )

        current_acceptance = current.acceptance_rate
        previous_acceptance = previous.acceptance_rate
        if (
            current.decision_count >= 3
            and previous.decision_count >= 3
            and current_acceptance is not None
            and previous_acceptance is not None
            and changes.acceptance_rate is not None
            and changes.acceptance_rate <= _ACCEPTANCE_DECLINE
        ):
            suggestions.append(
                WeeklyLearningSuggestion(
                    code="investigate_acceptance_decline",
                    priority="attention",
                    title="Investigate the weekly acceptance decline",
                    evidence=(
                        f"Weekly acceptance moved from {_percent(previous_acceptance)} to "
                        f"{_percent(current_acceptance)}."
                    ),
                    suggested_improvement=(
                        "Compare rejected signal profiles and improve explanations or diagnostic "
                        "coverage before considering any rule change."
                    ),
                )
            )

        if (
            current.findings_per_run is not None
            and previous.findings_per_run is not None
            and previous.findings_per_run > 0
            and changes.findings_per_run is not None
            and changes.findings_per_run / previous.findings_per_run >= _FINDING_DENSITY_INCREASE
        ):
            suggestions.append(
                WeeklyLearningSuggestion(
                    code="investigate_rising_finding_density",
                    priority="review",
                    title="Add context around rising finding density",
                    evidence=(
                        f"Findings per successful run rose from {previous.findings_per_run} to "
                        f"{current.findings_per_run}."
                    ),
                    suggested_improvement=(
                        "Inspect which deterministic signals recur and add deeper, privacy-safe "
                        "diagnostics before adding new recommendation types."
                    ),
                )
            )

        evaluated_proposals = (
            current.proposals_generated_count + current.proposals_deduplicated_count
        )
        if (
            evaluated_proposals >= 4
            and current.proposals_deduplicated_count >= 4
            and _rate(current.proposals_deduplicated_count, evaluated_proposals)
            >= _HIGH_DEDUPLICATION_RATE
        ):
            suggestions.append(
                WeeklyLearningSuggestion(
                    code="improve_recurring_signal_context",
                    priority="review",
                    title="Improve recurring-signal context",
                    evidence=(
                        f"{current.proposals_deduplicated_count} of {evaluated_proposals} proposal "
                        "evaluations were safely deduplicated."
                    ),
                    suggested_improvement=(
                        "Consider trend context for recurring signals instead of creating more "
                        "equivalent proposals."
                    ),
                )
            )

        if not suggestions:
            suggestions.append(
                WeeklyLearningSuggestion(
                    code="maintain_and_monitor",
                    priority="monitor",
                    title="Maintain the current deterministic policy",
                    evidence=(
                        "The completed-week comparison produced no bounded attention or review "
                        "trigger."
                    ),
                    suggested_improvement=(
                        "Continue collecting decisions and reassess after the next completed UTC "
                        "week."
                    ),
                )
            )
        return tuple(suggestions)
