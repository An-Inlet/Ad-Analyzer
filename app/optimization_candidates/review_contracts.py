"""Candidate-generated reviews still require a genuine separate customer approval."""

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from pydantic import Field
from sqlalchemy.orm import Session

from app.goals.schemas import StrictModel
from app.publication.provider_contracts import Digest, Id

if TYPE_CHECKING:
    from app.publication.execution_models import ProviderExecutionReview
    from app.publication.replacement_contracts import OptimizationReview


class CandidateReviewIntent(StrictModel):
    result_id: Id
    expected_decision_digest: Digest


class CandidateReviewPrepared(StrictModel):
    review_id: Id
    review_digest: Digest
    plan_digest: Digest
    status: str = Field(default="review_required", pattern="^review_required$")


class CandidateReviewGuard(Protocol):
    def __call__(
        self, db: Session, wid: int, review_id: str, actor: str, clock: Callable[[], datetime], /
    ) -> None: ...


class CandidateReviewWriter(Protocol):
    def __call__(
        self, db: Session, row: "ProviderExecutionReview", document: "OptimizationReview", /
    ) -> None: ...
