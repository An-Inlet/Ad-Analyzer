"""Import-neutral UTC clock shared by customer runtime contracts."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
