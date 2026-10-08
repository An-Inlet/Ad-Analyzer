"""Customer planning read projections; implementation never folds independent event axes."""

from typing import Literal

from pydantic import AwareDatetime, Field, computed_field, model_validator

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


class DocumentProjection(NoAuthority):
    document: PlanVersion | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def document_digest(self) -> str | None:
        return self.document.digest() if self.document is not None else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def action_digests(self) -> dict[str, str]:
        if self.document is None:
            return {}
        document = PlanVersion.model_validate(self.document)
        return {action.key: action.digest() for action in document.actions}


class PlanReadResult(PlanSummary, DocumentProjection):
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


class InputResult(NoAuthority):
    plan_id: Id
    input_revision: Positive
    inputs: PlanInputRevision

    @model_validator(mode="after")
    def exact_input(self) -> "InputResult":
        if self.plan_id != self.inputs.plan_id or self.input_revision != self.inputs.revision:
            raise ValueError("input result binding changed")
        return self


class VersionResult(DocumentProjection):
    plan_id: Id
    version: Positive
    document: PlanVersion

    @model_validator(mode="after")
    def exact_version(self) -> "VersionResult":
        if self.plan_id != self.document.inputs.plan_id or self.version != self.document.version:
            raise ValueError("version result binding changed")
        return self


class VersionPage(NoAuthority):
    items: tuple[VersionResult, ...] = Field(max_length=100)
    next_cursor: str | None = Field(max_length=256)


class EventPage(NoAuthority):
    items: tuple[EventResult, ...] = Field(max_length=100)
    next_cursor: str | None = Field(max_length=256)
