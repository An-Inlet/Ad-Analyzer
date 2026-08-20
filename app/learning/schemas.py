from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.learning.decision import (
    DECISION_LEARNING_EFFECT,
    DECISION_LEARNING_POLICY_VERSION,
    DecisionLearningProfile,
    DecisionLearningSnapshot,
)
from app.learning.report import (
    WeeklyLearningActivity,
    WeeklyLearningChanges,
    WeeklyLearningReport,
    WeeklyLearningSafety,
    WeeklyLearningSuggestion,
    WeeklyLearningWindow,
)


class DecisionLearningProfileResponse(BaseModel):
    recommendation_type: str
    scope_type: str
    review_action: str
    decision_count: int
    approved_count: int
    rejected_count: int
    acceptance_rate: Decimal
    smoothed_acceptance_rate: Decimal
    evidence_state: str
    last_decision_at: datetime

    @classmethod
    def from_profile(
        cls,
        profile: DecisionLearningProfile,
    ) -> "DecisionLearningProfileResponse":
        return cls(
            recommendation_type=profile.recommendation_type,
            scope_type=profile.scope_type,
            review_action=profile.review_action,
            decision_count=profile.decision_count,
            approved_count=profile.approved_count,
            rejected_count=profile.rejected_count,
            acceptance_rate=profile.acceptance_rate,
            smoothed_acceptance_rate=profile.smoothed_acceptance_rate,
            evidence_state=profile.evidence_state,
            last_decision_at=profile.last_decision_at,
        )


class DecisionLearningSnapshotResponse(BaseModel):
    workspace_id: int
    policy_version: str
    decision_count: int
    approved_count: int
    rejected_count: int
    reason_text_used: bool
    generation_effect: str
    profiles: list[DecisionLearningProfileResponse]

    @classmethod
    def from_snapshot(
        cls,
        snapshot: DecisionLearningSnapshot,
    ) -> "DecisionLearningSnapshotResponse":
        return cls(
            workspace_id=snapshot.workspace_id,
            policy_version=DECISION_LEARNING_POLICY_VERSION,
            decision_count=snapshot.decision_count,
            approved_count=snapshot.approved_count,
            rejected_count=snapshot.rejected_count,
            reason_text_used=False,
            generation_effect=DECISION_LEARNING_EFFECT,
            profiles=[
                DecisionLearningProfileResponse.from_profile(profile)
                for profile in snapshot.profiles
            ],
        )


class WeeklyLearningWindowResponse(BaseModel):
    date_from: date
    date_to: date

    @classmethod
    def from_window(cls, window: WeeklyLearningWindow) -> "WeeklyLearningWindowResponse":
        return cls(date_from=window.date_from, date_to=window.date_to)


class WeeklyLearningActivityResponse(BaseModel):
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

    @classmethod
    def from_activity(
        cls,
        activity: WeeklyLearningActivity,
    ) -> "WeeklyLearningActivityResponse":
        return cls(
            analysis_run_count=activity.analysis_run_count,
            findings_count=activity.findings_count,
            high_severity_findings_count=activity.high_severity_findings_count,
            proposals_generated_count=activity.proposals_generated_count,
            proposals_deduplicated_count=activity.proposals_deduplicated_count,
            decision_count=activity.decision_count,
            approved_count=activity.approved_count,
            rejected_count=activity.rejected_count,
            findings_per_run=activity.findings_per_run,
            acceptance_rate=activity.acceptance_rate,
        )


class WeeklyLearningChangesResponse(BaseModel):
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

    @classmethod
    def from_changes(cls, changes: WeeklyLearningChanges) -> "WeeklyLearningChangesResponse":
        return cls(**changes.__dict__)


class WeeklyLearningSuggestionResponse(BaseModel):
    code: str
    priority: str
    title: str
    evidence: str
    suggested_improvement: str
    automatic_change: bool

    @classmethod
    def from_suggestion(
        cls,
        suggestion: WeeklyLearningSuggestion,
    ) -> "WeeklyLearningSuggestionResponse":
        return cls(**suggestion.__dict__)


class WeeklyLearningSafetyResponse(BaseModel):
    local_data_only: bool
    actor_identity_used: bool
    reason_text_used: bool
    search_term_text_used: bool
    external_service_called: bool
    automatic_change_applied: bool

    @classmethod
    def from_safety(cls, safety: WeeklyLearningSafety) -> "WeeklyLearningSafetyResponse":
        return cls(**safety.__dict__)


class WeeklyLearningReportResponse(BaseModel):
    workspace_id: int
    policy_version: str
    report_key: str
    reporting_as_of: date
    summary_state: str
    evidence_state: str
    current_period: WeeklyLearningWindowResponse
    comparison_period: WeeklyLearningWindowResponse
    current: WeeklyLearningActivityResponse
    previous: WeeklyLearningActivityResponse
    changes: WeeklyLearningChangesResponse
    decision_learning: DecisionLearningSnapshotResponse
    suggestions: list[WeeklyLearningSuggestionResponse]
    safety: WeeklyLearningSafetyResponse

    @classmethod
    def from_report(cls, report: WeeklyLearningReport) -> "WeeklyLearningReportResponse":
        return cls(
            workspace_id=report.workspace_id,
            policy_version=report.policy_version,
            report_key=report.report_key,
            reporting_as_of=report.reporting_as_of,
            summary_state=report.summary_state,
            evidence_state=report.evidence_state,
            current_period=WeeklyLearningWindowResponse.from_window(report.current_period),
            comparison_period=WeeklyLearningWindowResponse.from_window(report.comparison_period),
            current=WeeklyLearningActivityResponse.from_activity(report.current),
            previous=WeeklyLearningActivityResponse.from_activity(report.previous),
            changes=WeeklyLearningChangesResponse.from_changes(report.changes),
            decision_learning=DecisionLearningSnapshotResponse.from_snapshot(
                report.decision_learning
            ),
            suggestions=[
                WeeklyLearningSuggestionResponse.from_suggestion(item)
                for item in report.suggestions
            ],
            safety=WeeklyLearningSafetyResponse.from_safety(report.safety),
        )
