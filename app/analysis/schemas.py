from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.enums import AnalysisCadence, AnalysisRunStatus


class AnalysisRunResponse(BaseModel):
    """Aggregate-only operator response; no raw analytics or CRM identifiers."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    account_id: int | None
    source_job_run_id: int | None
    cadence: AnalysisCadence
    status: AnalysisRunStatus
    schedule_policy_version: str
    scheduled_for: datetime
    metric_date_from: date
    metric_date_to: date
    outcome_date_from: date
    outcome_date_to: date
    started_at: datetime
    finished_at: datetime | None
    accounts_analyzed: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    high_severity_findings_count: int = Field(ge=0)
    outcome_analysis_ready: bool
    outcome_campaign_count: int = Field(ge=0)
    attributed_journey_count: int = Field(ge=0)
    unattributed_journey_count: int = Field(ge=0)
    blocking_reasons: list[str]
    error_code: str | None
