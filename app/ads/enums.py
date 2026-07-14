from enum import StrEnum


class AdvertisingPlatform(StrEnum):
    """Supported read-only advertising data platforms."""

    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"


class JobRunStatus(StrEnum):
    """Lifecycle states for local read-only ingestion jobs."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
