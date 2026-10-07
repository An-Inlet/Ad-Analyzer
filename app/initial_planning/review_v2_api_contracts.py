"""Bounded v2 execution choices; availability is not financial qualification."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, model_validator

from app.initial_planning.contracts import Frozen
from app.initial_planning.review_v2_contracts import (
    InitialPreviewExecutionIntentV1,
    InitialPreviewExecutionPreparedV1,
)
from app.publication.provider_contracts import Digest, Id

if TYPE_CHECKING:
    from app.customers.access import CustomerPrincipal
    from app.customers.identity import IdentityProvider
    from app.initial_planning.runtime import InitialPlanningRuntime
    from app.publication.customer_optimization_contracts import CustomerOptimizationRuntime


class InitialPreviewExecutionOptionV1(Frozen):
    mandate_id: Id
    mandate_revision: int = Field(strict=True, ge=1)
    policy_digest: Digest
    account_label: str = Field(min_length=1, max_length=160)
    target_label: str = Field(min_length=1, max_length=160)
    currency: Literal["USD"]
    time_zone: str = Field(min_length=1, max_length=64)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    total_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    per_plan_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    positive_change_cap_micros: int = Field(strict=True, ge=0, le=10**15)

    @model_validator(mode="after")
    def bounded(self) -> "InitialPreviewExecutionOptionV1":
        ZoneInfo(self.time_zone)
        if (
            self.starts_at >= self.ends_at
            or self.per_plan_cap_micros > self.total_cap_micros
            or self.positive_change_cap_micros > self.total_cap_micros
            or any(
                value % 10000
                for value in (
                    self.total_cap_micros,
                    self.per_plan_cap_micros,
                    self.positive_change_cap_micros,
                )
            )
        ):
            raise ValueError("invalid execution mandate option")
        return self


class InitialPreviewExecutionOptionsV1(Frozen):
    schema_version: Literal["inlet.initial-preview-execution-options.v1"] = (
        "inlet.initial-preview-execution-options.v1"
    )
    preview_id: Id
    preview_digest: Digest
    options: tuple[InitialPreviewExecutionOptionV1, ...] = Field(max_length=50)
    truncated: bool
    status: Literal["available", "unavailable"]
    unavailable_reason: (
        Literal[
            "execution_runtime_unavailable",
            "separate_execution_consent_required",
            "matching_execution_mandate_unavailable",
        ]
        | None
    )
    financial_qualification: Literal["not_checked"] = "not_checked"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def exact_availability(self) -> "InitialPreviewExecutionOptionsV1":
        identities = [(item.mandate_id, item.mandate_revision) for item in self.options]
        if (
            len(set(identities)) != len(identities)
            or (self.status == "available") != bool(self.options)
            or (self.status == "unavailable") != (self.unavailable_reason is not None)
        ):
            raise ValueError("invalid execution choice availability")
        return self


@dataclass(frozen=True)
class InitialPreviewExecutionRuntime:
    planning: "InitialPlanningRuntime"
    optimization: "CustomerOptimizationRuntime | None"


class PreviewExecutionOptionsReader(Protocol):
    def __call__(
        self,
        runtime: InitialPreviewExecutionRuntime,
        principal: "CustomerPrincipal",
        identity_provider: "IdentityProvider",
        workspace_id: int,
        preview_id: str,
    ) -> InitialPreviewExecutionOptionsV1: ...


class PreviewExecutionPreparer(Protocol):
    def __call__(
        self,
        runtime: InitialPreviewExecutionRuntime,
        principal: "CustomerPrincipal",
        identity_provider: "IdentityProvider",
        workspace_id: int,
        preview_id: str,
        intent: InitialPreviewExecutionIntentV1,
    ) -> InitialPreviewExecutionPreparedV1: ...
