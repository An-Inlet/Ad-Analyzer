"""Descriptive configured policy; never permission to acquire or mutate ads."""

from typing import Literal

from pydantic import StrictBool, model_validator

from app.planning_documents.common import NoAuthority, Positive
from app.planning_documents.policy_capabilities import reporting_capability


class PlanningCapabilitiesV1(NoAuthority):
    schema_version: Literal["inlet.planning-capabilities.v1"] = "inlet.planning-capabilities.v1"
    workspace_id: Positive
    policy_version: str
    generator_version: str
    selected_reporting_available: StrictBool
    google_budget_observation: Literal["unavailable", "injected_fixture", "mock_http"] = (
        "unavailable"
    )

    @model_validator(mode="after")
    def configured(self) -> "PlanningCapabilitiesV1":
        if (self.google_budget_observation in ("injected_fixture", "mock_http")
                and self.policy_version != "inlet.descriptive-review.v6"):
            raise ValueError("fixture budget observation requires V6")
        capability = reporting_capability(self.policy_version, self.generator_version)
        if self.selected_reporting_available != (
            capability.mode
            in (
                "selected_requested_window",
                "creative_selected_requested_window",
                "owner_review_creative_selected_requested_window",
            )
        ):
            raise ValueError("configured planning capability mismatch")
        return self
