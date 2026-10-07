"""Preview-specific exact-review provenance; never qualified-learning evidence."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol

from sqlalchemy.orm import Session

from app.initial_planning.contracts import Frozen
from app.initial_planning.runtime import InitialPlanningRuntime
from app.publication.customer_optimization_contracts import CustomerOptimizationRuntime
from app.publication.provider_contracts import Digest, Id

if TYPE_CHECKING:
    from app.publication.execution_models import ProviderExecutionReview
    from app.publication.replacement_contracts import OptimizationReview


class InitialPreviewReviewIntent(Frozen):
    expected_preview_digest: Digest


class InitialPreviewReviewPrepared(Frozen):
    schema_version: Literal["inlet.initial-preview-review-prepared.v1"] = (
        "inlet.initial-preview-review-prepared.v1"
    )
    preview_id: Id
    preview_digest: Digest
    review_id: Id
    review_digest: Digest
    plan_digest: Digest
    status: Literal["review_required"] = "review_required"
    spending_authority: Literal["none"] = "none"


@dataclass(frozen=True)
class InitialPreviewReviewRuntime:
    planning: InitialPlanningRuntime
    optimization: CustomerOptimizationRuntime


class InitialPreviewReviewGuard(Protocol):
    def __call__(
        self, db: Session, wid: int, review_id: str, actor: str, clock: Callable[[], datetime], /
    ) -> None: ...


class InitialPreviewReviewWriter(Protocol):
    def __call__(
        self, db: Session, row: "ProviderExecutionReview", document: "OptimizationReview", /
    ) -> None: ...
