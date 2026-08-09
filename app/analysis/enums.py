from enum import StrEnum


class AnalysisCadence(StrEnum):
    """Supported deterministic analysis schedules."""

    POST_SYNC = "post_sync"
    NIGHTLY = "nightly"
    WEEKLY = "weekly"


class AnalysisRunStatus(StrEnum):
    """Lifecycle states for an auditable local analysis run."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

