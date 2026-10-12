"""Distinct historical fixture observations and server-proven source invalidations."""

from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from app.planning_documents.common import Digest, Id, Positive
from app.planning_documents.events import VersionBinding
from app.planning_documents.google_budget_hypothesis_comparison import (
    GoogleBudgetHypothesisComparisonV1,
)
from app.planning_documents.google_budget_owner_contracts import _instant, _originals
from app.planning_documents.google_budget_read import PROFILE, GoogleBudgetReadProofV1
from app.planning_documents.google_budget_read_projection import budget_read_witness
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount


class BudgetReadIntent(VersionBinding):
    expected_event_sequence: int = Field(strict=True, ge=0)
    request_key: str = Field(strict=True, min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    profile_digest: Digest = PROFILE

    @model_validator(mode="after")
    def profile(self) -> "BudgetReadIntent":
        if self.profile_digest != PROFILE:
            raise ValueError("exact budget acquisition profile required")
        return self

    def binding(self) -> VersionBinding:
        return VersionBinding.model_validate(
            {k: getattr(self, k) for k in VersionBinding.model_fields}
        )


class BudgetInvalidationIntent(BudgetReadIntent):
    observation_event_id: Id
    observation_digest: Digest
    observation_sequence: Positive


class BudgetHistoricalEvent(VersionBinding):
    event_id: Id
    actor_id: Id
    recorded_at: AwareDatetime
    provenance: Literal["injected_fixture"] = "injected_fixture"
    current_reliance: Literal["not_assessed"] = "not_assessed"
    implementation: Literal["not_assessed"] = "not_assessed"

    @model_validator(mode="before")
    @classmethod
    def originals(cls, value: Any) -> Any:
        _originals(value)
        return value

    @field_validator("recorded_at", mode="before")
    @classmethod
    def instant(cls, value: Any) -> Any:
        return _instant(value)

    @model_serializer(mode="wrap")
    def checked(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result: dict[str, Any] = handler(type(self).model_validate(self))
        return result

    def binding(self) -> VersionBinding:
        return VersionBinding.model_validate(
            {k: getattr(self, k) for k in VersionBinding.model_fields}
        )


class GoogleBudgetObservationV1(BudgetHistoricalEvent):
    schema_version: Literal["inlet.google-budget-observation.v1"] = (
        "inlet.google-budget-observation.v1"
    )
    comparison: GoogleBudgetHypothesisComparisonV1
    proof: GoogleBudgetReadProofV1
    finding: Literal["matches_hypothesis", "differs_from_hypothesis"]

    @model_validator(mode="after")
    def exact(self) -> "GoogleBudgetObservationV1":
        comparison, ticket = self.comparison, self.proof.ticket
        if comparison.fresh is None:
            raise ValueError("budget observation needs acquired setting")
        if (
            comparison.binding != self.binding()
            or ticket.binding != self.binding()
            or ticket.privacy_revision != comparison.privacy_revision
            or ticket.source_digest() != comparison.source_binding_digest
            or ticket.reporting_window != comparison.document.inputs.reporting_window
            or self.recorded_at != comparison.compared_at
            or self.finding != comparison.status
            or budget_read_witness(self.proof, comparison.fresh.owner_key) != comparison.fresh
        ):
            raise ValueError("budget observation exact proof/comparison binding required")
        return self


class GoogleBudgetInvalidationV1(BudgetHistoricalEvent):
    schema_version: Literal["inlet.google-budget-invalidation.v1"] = (
        "inlet.google-budget-invalidation.v1"
    )
    observation_event_id: Id
    observation_digest: Digest
    observation_sequence: Positive
    reason: Literal["source_generation_changed"] = "source_generation_changed"
    observation_recorded_at: AwareDatetime
    original_source_digest: Digest
    current_account: ExecutionAccount
    current_source_digest: Digest
    privacy_revision: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def exact(self) -> "GoogleBudgetInvalidationV1":
        if (
            self.event_id == self.observation_event_id
            or self.recorded_at < self.observation_recorded_at
            or self.current_account.workspace_id != self.workspace_id
            or self.current_account.account.platform != "google_ads"
            or self.original_source_digest == self.current_source_digest
            or fingerprint("inlet.planning-source.v1", self.current_account.model_dump(mode="json"))
            != self.current_source_digest
        ):
            raise ValueError("exact changed source invalidation required")
        return self

    @field_validator("observation_recorded_at", mode="before")
    @classmethod
    def observation_instant(cls, value: Any) -> Any:
        return _instant(value)


BudgetEvent = GoogleBudgetObservationV1 | GoogleBudgetInvalidationV1
