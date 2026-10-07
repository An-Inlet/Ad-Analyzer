"""Immutable required deployment policy; no inferred numeric product settings."""

from typing import Literal

from pydantic import Field, model_validator

from app.initial_planning.contracts import Frozen, InitialPlanningConfiguration
from app.meta.security import API_VERSION
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Id
from app.reported_feedback.contracts import ReportedFeedbackPolicyV1, ReportedWindowPolicyV1


class NativeBudgetReadPolicyV1(Frozen):
    http_timeout_seconds: int = Field(strict=True, ge=1, le=60)
    total_deadline_seconds: int = Field(strict=True, ge=1, le=120)
    maximum_pages: int = Field(strict=True, ge=1, le=10)
    maximum_targets: int = Field(strict=True, ge=1, le=200)
    observation_lifetime_seconds: int = Field(strict=True, ge=1, le=300)
    credential_minimum_remaining_seconds: int = Field(strict=True, ge=1, le=3600)

    @model_validator(mode="after")
    def bounded(self) -> "NativeBudgetReadPolicyV1":
        if (
            self.http_timeout_seconds > self.total_deadline_seconds
            or self.credential_minimum_remaining_seconds < self.total_deadline_seconds
        ):
            raise ValueError("incoherent native read deadlines")
        return self


class PlanningReportingProfileV1(Frozen):
    schema_version: Literal["inlet.planning-reporting-profile.v1"] = (
        "inlet.planning-reporting-profile.v1"
    )
    profile_id: Id
    revision: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    initial: InitialPlanningConfiguration
    windows: ReportedWindowPolicyV1
    feedback: ReportedFeedbackPolicyV1 | None
    native_read: NativeBudgetReadPolicyV1

    @model_validator(mode="after")
    def coherent(self) -> "PlanningReportingProfileV1":
        if (
            self.initial.environment != self.environment
            or self.windows.environment != self.environment
            or self.initial.supported_event != self.windows.selected_event
            or self.windows.query_version != f"meta.{API_VERSION}.campaign-day.v1"
            or (
                self.feedback is not None
                and (
                    self.feedback.environment != self.environment
                    or self.feedback.comparison_policy_digest != self.windows.digest()
                    or self.feedback.minimum_distinct_original_attempts != 1
                )
            )
        ):
            raise ValueError("incoherent planning reporting profile")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))
