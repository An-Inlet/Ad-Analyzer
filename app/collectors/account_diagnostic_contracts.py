"""Customer observation intents and safe diagnostics; never spending authority."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel


def validate_observation_period(starts_at: datetime, ends_at: datetime) -> None:
    """Leave conversion room for any account timezone and exclusive end dates."""
    try:
        lower = datetime.min.replace(tzinfo=UTC) + timedelta(days=1)
        upper = datetime.max.replace(tzinfo=UTC) - timedelta(days=1)
        if not all(lower <= value.astimezone(UTC) <= upper for value in (starts_at, ends_at)):
            raise ValueError("diagnostic period cannot be represented in account timezones")
    except (OverflowError, ValueError):
        raise ValueError("diagnostic period cannot be represented in account timezones") from None
    if not timedelta(0) < ends_at - starts_at <= timedelta(days=366):
        raise ValueError("diagnostic period exceeds bound")


class AccountDiagnosticIntentV1(StrictModel):
    account_id: int = Field(strict=True, gt=0)
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "AccountDiagnosticIntentV1":
        validate_observation_period(self.starts_at, self.ends_at)
        return self


class DiagnosticInventoryCountV1(StrictModel):
    kind: Literal[
        "campaign", "campaign_budget", "account_budget", "billing_setup", "adset", "adgroup"
    ]
    count: int = Field(strict=True, ge=0, le=200)


class DiagnosticReasonV1(StrictModel):
    code: str = Field(pattern=r"^[a-z_]{1,100}$")
    message: str = Field(min_length=1, max_length=240)


class AccountDiagnosticViewV1(StrictModel):
    schema_version: Literal["inlet.customer-account-diagnostics.v1"] = (
        "inlet.customer-account-diagnostics.v1"
    )
    account_id: int = Field(strict=True, gt=0)
    account_name: str = Field(min_length=1, max_length=160)
    platform: Literal["google_ads", "meta_ads", "tiktok_ads"]
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    inventory_counts: list[DiagnosticInventoryCountV1] = Field(max_length=4)
    read_complete: bool
    cap_semantics: Literal["unqualified"] = "unqualified"
    optimization_available: Literal[False] = False
    reporting_watermark: None = None
    unreported_upper_micros: None = None
    unchanged_future_upper_micros: None = None
    proposed_owner_upper_micros: None = None
    reasons: list[DiagnosticReasonV1] = Field(min_length=1, max_length=20)
