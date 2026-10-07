"""Server-owned target discovery and bounded customer optimization intent."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.customer_runtime import utc_now
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import OptimizationState
from app.publication.optimization_execution_contracts import OptimizationRuntime
from app.publication.provider_contracts import Digest, Id

if TYPE_CHECKING:
    from app.initial_planning.runtime import InitialPlanningRuntime
    from app.production_runtime.optimization_assembly import ConfiguredOptimization


class TargetQuery(StrictModel):
    goal_id: Id
    goal_revision: int = Field(strict=True, ge=1)
    account_id: int = Field(strict=True, gt=0)


class TargetRequest(StrictModel):
    goal_id: Id
    goal_revision: int = Field(strict=True, ge=1)
    goal_digest: Digest
    scope: ExecutionAccount


class TargetOption(StrictModel):
    label: str = Field(min_length=1, max_length=160)
    parent_label: str = Field(min_length=1, max_length=160)
    state: OptimizationState

    def identifier(self, request: TargetRequest) -> str:
        return fingerprint(
            "inlet.customer-optimization-option.v1",
            {
                "request": request.model_dump(mode="json"),
                "label": self.label,
                "parent_label": self.parent_label,
                "state": self.state.digest(),
            },
        )


class TargetCatalog(StrictModel):
    request: TargetRequest
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    options: list[TargetOption] = Field(max_length=50)
    complete: Literal[True]

    @model_validator(mode="after")
    def bounded(self) -> "TargetCatalog":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("catalog lifetime exceeds bound")
        identifiers = [o.identifier(self.request) for o in self.options]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate catalog choice")
        if any(
            o.state.scope != self.request.scope
            or not o.state.complete
            or o.state.unsupported_features
            or not self.observed_at - timedelta(minutes=5)
            <= o.state.observed_at
            <= self.observed_at
            for o in self.options
        ):
            raise ValueError("catalog state differs from complete owned request")
        if len(json.dumps(self.model_dump(mode="json")).encode()) > 65536:
            raise ValueError("catalog exceeds byte bound")
        return self


class TargetReader(Protocol):
    def __call__(self, request: TargetRequest, now: datetime, /) -> TargetCatalog: ...


@dataclass(frozen=True)
class CustomerOptimizationRuntime:
    execution: OptimizationRuntime
    catalog: TargetReader | None = None
    clock: Callable[[], datetime] = utc_now
    initial_planning: "InitialPlanningRuntime | None" = None
    configured: "ConfiguredOptimization | None" = None


def get_customer_optimization_runtime() -> CustomerOptimizationRuntime | None:
    return None


class TargetChoice(TargetQuery):
    option_id: Digest


class OptimizationLimits(StrictModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    total_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    per_plan_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    positive_change_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    action_limit: int = Field(strict=True, ge=1, le=1000)
    cooldown_seconds: int = Field(strict=True, ge=0, le=86400)
    aggressiveness_percent: Literal[5, 10, 20]

    @model_validator(mode="after")
    def bounded(self) -> "OptimizationLimits":
        if (
            not 0 < (self.ends_at - self.starts_at).total_seconds() <= 366 * 86400
            or self.per_plan_cap_micros > self.total_cap_micros
            or self.positive_change_cap_micros > self.total_cap_micros
        ):
            raise ValueError("invalid fixed-period policy limits")
        return self


class OptimizationPolicyIntent(StrictModel):
    choice: TargetChoice
    limits: OptimizationLimits


class OptimizationPolicyEdit(OptimizationPolicyIntent):
    expected_revision: int = Field(strict=True, ge=1)


class BudgetIntent(StrictModel):
    kind: Literal["set_budget"]
    amount_micros: int = Field(strict=True, gt=0, le=10**15)


class PauseIntent(StrictModel):
    kind: Literal["pause"]


class InitialOptimizationIntent(StrictModel):
    choice: TargetChoice
    mandate_id: Id
    mandate_revision: int = Field(strict=True, ge=1)
    action: Annotated[BudgetIntent | PauseIntent, Field(discriminator="kind")]


class RepeatOptimizationIntent(InitialOptimizationIntent):
    predecessor_id: Id
