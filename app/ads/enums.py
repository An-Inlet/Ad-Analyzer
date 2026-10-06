from enum import StrEnum


class AdvertisingPlatform(StrEnum):
    """Supported read-only advertising data platforms."""

    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"
    TIKTOK_ADS = "tiktok_ads"


class MetricEntityType(StrEnum):
    """Supported local metric grains for deterministic analysis."""

    CAMPAIGN = "campaign"
    AD_GROUP = "ad_group"
    AD_SET = "ad_set"
    AD = "ad"
    KEYWORD = "keyword"
    SEARCH_TERM = "search_term"


class JobRunStatus(StrEnum):
    """Lifecycle states for local read-only ingestion jobs."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RecommendationStatus(StrEnum):
    """Human-controlled recommendation lifecycle states."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED_DRY_RUN = "executed_dry_run"


class ExecutionStatus(StrEnum):
    """Controlled execution lifecycle states."""

    PLANNED = "planned"
    DRY_RUN_SUCCEEDED = "dry_run_succeeded"
    DRY_RUN_FAILED = "dry_run_failed"
    BLOCKED = "blocked"
