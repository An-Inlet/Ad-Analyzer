"""Server-compiled exact optimization plans; immutable data does not grant authority."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal, Protocol

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy.orm import Session

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_authorization import ExecutionAuthorizer, owner_authorizer
from app.publication.execution_contracts import (
    Environment,
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.optimization_contracts import (
    GoogleBudgetSetV1,
    GoogleCurrentState,
    MetaBudgetSetV1,
    MetaCurrentState,
    MoneyContext,
    OptimizationContext,
    OptimizationIntent,
    OptimizationRequest,
    OptimizationState,
    OptimizationTarget,
    OptimizationTransport,
    TikTokBudgetSetV1,
    TikTokCurrentState,
)
from app.publication.provider_contracts import Digest, Id

OperationKind = Literal[
    "google_budget_set_v1",
    "google_status_set_v1",
    "meta_budget_set_v1",
    "meta_status_set_v1",
    "tiktok_budget_set_v1",
    "tiktok_status_set_v1",
]


class OptimizationQualification(StrictModel):
    environment: Environment
    scope: ExecutionAccount
    target: OptimizationTarget
    money: MoneyContext
    qualification_id: Id
    qualification_revision: int = Field(strict=True, ge=1)
    profile: str = Field(min_length=1, max_length=80)
    allowed_operations: list[OperationKind] = Field(min_length=1, max_length=6)
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    evidence_digest: Digest
    unresolved: list[str] = Field(max_length=32)

    @model_validator(mode="after")
    def bounded(self) -> "OptimizationQualification":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("bounded optimization qualification lifetime required")
        if len(set(self.allowed_operations)) != len(self.allowed_operations):
            raise ValueError("unique qualified operations required")
        return self


def positive_delta(intent: OptimizationIntent, before: OptimizationState) -> int:
    action = intent.action
    amount: int | None
    if isinstance(action, GoogleBudgetSetV1) and isinstance(before, GoogleCurrentState):
        amount = before.budget_amount_micros
    elif isinstance(action, MetaBudgetSetV1) and isinstance(before, MetaCurrentState):
        amount = (
            before.daily_budget_micros
            if action.budget_field == "daily_budget"
            else before.lifetime_budget_micros
        )
    elif isinstance(action, TikTokBudgetSetV1) and isinstance(before, TikTokCurrentState):
        amount = before.budget_micros
    elif isinstance(action, (GoogleBudgetSetV1, MetaBudgetSetV1, TikTokBudgetSetV1)):
        raise ValueError("budget operation requires matching original provider state")
    else:
        return 0
    if amount is None or amount <= 0 or action.amount_micros == amount:
        raise ValueError("existing positive budget and changed exact amount required")
    return max(0, action.amount_micros - amount)


class OptimizationPlan(StrictModel):
    schema_version: Literal["inlet.optimization-plan.v1"] = "inlet.optimization-plan.v1"
    intent: OptimizationIntent
    before: OptimizationState
    qualification: OptimizationQualification
    exposure: ExposureEvidence
    positive_change_micros: int = Field(strict=True, ge=0, le=10**15)
    provider_compare_and_swap: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def bound(self) -> "OptimizationPlan":
        i, s, q, e = self.intent, self.before, self.qualification, self.exposure
        if (
            q.environment != i.mandate.environment
            or q.scope != i.scope
            or q.target != i.target
            or q.money != s.money
            or q.qualification_id != i.qualification_id
            or q.qualification_revision != i.qualification_revision
            or q.unresolved
            or i.action.kind not in q.allowed_operations
            or e.qualification_id != q.qualification_id
            or self.positive_change_micros != positive_delta(i, s)
        ):
            raise ValueError("server qualification and exact budget delta must bind plan")
        # Reuse the transport request's exact scope/intent/state/topology/money binding
        # validator. These validation-only IDs are never persisted or dispatched.
        self.request("0" * 32, "0" * 32, "0" * 32, s.observed_at)
        return self

    def request(
        self, run_id: str, attempt_id: str, fence: str, now: datetime
    ) -> OptimizationRequest:
        return OptimizationRequest(
            intent=self.intent,
            intent_digest=self.intent.digest(),
            before=self.before,
            exposure=self.exposure,
            action_id=run_id,
            attempt_id=attempt_id,
            fence=fence,
            dispatched_at=now,
        )

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class OptimizationExecutionReview(StrictModel):
    schema_version: Literal["inlet.execution-optimization-review.v1"] = (
        "inlet.execution-optimization-review.v1"
    )
    purpose: Literal["existing_campaign_optimize"] = "existing_campaign_optimize"
    plan: OptimizationPlan

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class OptimizationQualificationReader(Protocol):
    def __call__(
        self,
        db: Session,
        binding: ProviderMandateBinding,
        scope: ExecutionAccount,
        target: OptimizationTarget,
        now: datetime,
        /,
    ) -> OptimizationQualification: ...


class OptimizationExposureReader(Protocol):
    def __call__(
        self,
        db: Session,
        intent: OptimizationIntent,
        before: OptimizationState,
        qualification: OptimizationQualification,
        now: datetime,
        /,
    ) -> ExposureEvidence: ...


if TYPE_CHECKING:
    from app.publication.replacement_contracts import ReplacementReader


@dataclass(frozen=True)
class OptimizationRuntime:
    environment: Environment
    qualification_reader: OptimizationQualificationReader
    exposure_reader: OptimizationExposureReader
    context: Callable[[ExecutionAccount], OptimizationContext]
    google: OptimizationTransport | None = None
    meta: OptimizationTransport | None = None
    tiktok: OptimizationTransport | None = None
    live_enabled: bool = False
    authorize: ExecutionAuthorizer = owner_authorizer
    replacement_reader: "ReplacementReader | None" = None

    def transport(self, scope: ExecutionAccount) -> OptimizationTransport:
        adapter = {"google_ads": self.google, "meta_ads": self.meta, "tiktok_ads": self.tiktok}.get(
            scope.account.platform
        )
        if adapter is None:
            raise HTTPException(409, "qualified optimization adapter unavailable")
        return adapter


class OptimizationClaim(StrictModel):
    workspace_id: int = Field(strict=True, gt=0)
    run_id: Id
    attempt_id: Id
    environment: Environment
    request: OptimizationRequest


def get_optimization_runtime() -> OptimizationRuntime | None:
    return None
