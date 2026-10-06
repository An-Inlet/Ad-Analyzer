"""Customer observation intents and safe diagnostics; never spending authority."""

from datetime import timedelta
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel


class AccountDiagnosticIntentV1(StrictModel):
    account_id: int = Field(strict=True, gt=0)
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "AccountDiagnosticIntentV1":
        if not timedelta(0) < self.ends_at - self.starts_at <= timedelta(days=366):
            raise ValueError("diagnostic period exceeds bound")
        return self


class DiagnosticInventoryCountV1(StrictModel):
    kind: Literal["campaign", "campaign_budget", "account_budget", "billing_setup", "adset", "adgroup"]
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
