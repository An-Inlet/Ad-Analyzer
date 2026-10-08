"""Customer planning read projections; implementation never folds independent event axes."""

from typing import Literal

from pydantic import AwareDatetime, Field

from app.planning_documents.common import Frozen, Id, NoAuthority, Positive, Text
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import CustomerDecision, ManualAssertion, ReadObservedStatus


class PlanSummary(NoAuthority):
    plan_id: Id
    input_revision: Positive
    version: int = Field(strict=True, ge=0)
    event_sequence: int = Field(strict=True, ge=0)
    created_at: AwareDatetime


class PlanReadResult(PlanSummary):
    inputs: PlanInputRevision
    document: PlanVersion | None
    freshness: Literal[
        "not_generated", "current", "expired", "source_changed", "goal_changed", "input_changed"
    ]
    reasons: tuple[Text, ...] = Field(max_length=20)


class EventResult(NoAuthority):
    event_sequence: Positive
    event: CustomerDecision | ManualAssertion | ReadObservedStatus


class PlanPage(Frozen):
    items: tuple[PlanSummary, ...] = Field(max_length=100)
    next_cursor: str | None = Field(max_length=256)
