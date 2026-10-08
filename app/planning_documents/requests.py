"""Customer intent DTOs, never trusted evidence or complete plan documents."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.planning_documents.common import (
    Amount,
    Digest,
    Frozen,
    Id,
    Key,
    Positive,
    Text,
    Title,
    unique,
)
from app.planning_documents.context import ReportingWindow


class TargetSelector(Frozen):
    account_id: Positive
    canonical_entity_key: Digest
    selection_key: Digest


class AllocationIntent(Frozen):
    target: TargetSelector
    amount_micros: Amount


class ScenarioIntent(Frozen):
    key: Key
    title: Title
    allocations: tuple[AllocationIntent, ...] = Field(max_length=100)
    unallocated_micros: Amount


class CustomerInputs(Frozen):
    goal_id: Id
    goal_revision: Positive
    account_ids: tuple[Positive, ...] = Field(min_length=1, max_length=20)
    reporting_window: ReportingWindow
    comparison_window: ReportingWindow | None
    milestone: Text
    product_offer: Text | None
    constraints: tuple[Text, ...] = Field(max_length=30)
    assumptions: tuple[Text, ...] = Field(max_length=30)
    exclusions: tuple[TargetSelector, ...] = Field(max_length=100)
    fixed_allocations: tuple[AllocationIntent, ...] = Field(max_length=100)
    scenario_intents: tuple[ScenarioIntent, ...] = Field(max_length=8)
    maximum_creative_assets: int | None = Field(default=None, strict=True, ge=0, le=30)

    @model_validator(mode="after")
    def selected(self) -> "CustomerInputs":
        unique(self.account_ids, "selected account")
        targets = (
            *self.exclusions,
            *(a.target for a in self.fixed_allocations),
            *(a.target for s in self.scenario_intents for a in s.allocations),
        )
        if any(t.account_id not in self.account_ids for t in targets):
            raise ValueError("target account must be selected")
        return self


class CreatePlan(Frozen):
    inputs: CustomerInputs
    request_key: str = Field(strict=True, min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class EditPlan(CreatePlan):
    expected_input_revision: Positive
    expected_version: int = Field(strict=True, ge=0)


class GeneratePlan(Frozen):
    expected_input_revision: Positive
    expected_version: int = Field(strict=True, ge=0)
    request_key: str = Field(strict=True, min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class DecisionIntent(Frozen):
    expected_version: Positive
    expected_event_sequence: int = Field(strict=True, ge=0)
    document_digest: Digest
    action_key: Key
    action_digest: Digest
    decision: Literal["accepted_for_manual_application", "rejected", "deferred"]
    reason: Text
    supersedes_event_id: Id | None
    request_key: str = Field(strict=True, min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class AssertionIntent(Frozen):
    expected_version: Positive
    expected_event_sequence: int = Field(strict=True, ge=0)
    document_digest: Digest
    action_key: Key
    action_digest: Digest
    assertion: Literal["customer_reports_applied", "retracted"]
    reported_applied_at: AwareDatetime | None
    statement: Text
    supersedes_event_id: Id | None
    request_key: str = Field(strict=True, min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def coherent_assertion(self) -> "AssertionIntent":
        from datetime import UTC, datetime

        if self.assertion == "customer_reports_applied":
            if self.reported_applied_at is None or self.reported_applied_at > datetime.now(UTC):
                raise ValueError("nonfuture reported application time required")
        elif self.reported_applied_at is not None or self.supersedes_event_id is None:
            raise ValueError("retraction requires the prior assertion and no applied timestamp")
        return self
