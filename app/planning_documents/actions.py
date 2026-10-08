"""Manual recommendations and alternative allocations, never execution instructions."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.planning_documents.common import (
    Amount,
    Digest,
    Frozen,
    Key,
    NoAuthority,
    Positive,
    SignedAmount,
    Text,
    Title,
    unique,
)
from app.planning_documents.context import AccountTarget, BudgetPeriod, TargetRef
from app.planning_documents.fields import FieldProposal, ProposedField


class NativeBudget(Frozen):
    """An explicit native amount; unknown unit/owner cannot enter this type."""

    owner_key: Digest
    evidence_key: Key
    unit: Literal["micros", "minor_units"]
    currency: Annotated[str, Field(strict=True, pattern=r"^[A-Z]{3}$")]
    cadence: Literal["daily", "lifetime"]
    current_amount: Amount
    proposed_amount: Amount
    delta: SignedAmount

    @model_validator(mode="after")
    def arithmetic(self) -> "NativeBudget":
        if self.delta != self.proposed_amount - self.current_amount:
            raise ValueError("native delta must reconcile in declared units")
        return self


class UnavailableBudget(Frozen):
    reason: Text
    current_amount: None = None
    proposed_amount: None = None
    owner_key: None = None
    unit: None = None


class ManualAction(NoAuthority):
    key: Key
    priority: Positive
    kind: Literal[
        "budget_review",
        "status_review",
        "targeting_review",
        "landing_page_review",
        "bidding_review",
        "creative_review",
        "investigate",
        "retain",
    ]
    target: TargetRef | AccountTarget
    proposed_fields: tuple[FieldProposal, ...] = Field(max_length=20)
    conflicts: tuple[Key, ...] = Field(max_length=20)
    measurement_criterion: Text
    title: Title
    rationale: Text
    evidence_keys: tuple[Key, ...] = Field(min_length=1, max_length=20)
    assumption_keys: tuple[Key, ...] = Field(max_length=20)
    prerequisites: tuple[Key, ...] = Field(max_length=20)
    manual_steps: tuple[Text, ...] = Field(min_length=1, max_length=20)
    expected_effect: Text
    limitations: tuple[Text, ...] = Field(min_length=1, max_length=20)
    native_budget: NativeBudget | UnavailableBudget | None

    @model_validator(mode="after")
    def coherent(self) -> "ManualAction":
        for values in (self.evidence_keys, self.assumption_keys, self.prerequisites):
            unique(values, "action reference")
        if self.key in self.prerequisites:
            raise ValueError("self dependency")
        if self.kind == "budget_review" and self.native_budget is None:
            raise ValueError("budget review must state availability")
        if self.kind != "budget_review" and self.native_budget is not None:
            raise ValueError("budget values require budget review")
        unique(tuple(p.key for p in self.proposed_fields), "proposed field")
        unique(
            tuple(
                p.current.field if isinstance(p, ProposedField) else p.field
                for p in self.proposed_fields
            ),
            "proposed field name",
        )
        unique(self.conflicts, "conflict")
        if isinstance(self.target, AccountTarget) and self.kind not in {
            "creative_review",
            "investigate",
        }:
            raise ValueError("account scope permits only creative/prerequisite planning")
        allowed = {
            "status_review": {"delivery_status"},
            "targeting_review": {"country_targets"},
            "landing_page_review": {"landing_page"},
            "bidding_review": {"bidding"},
            "budget_review": {"native_budget"},
        }
        if self.kind in allowed and self.kind != "budget_review" and not self.proposed_fields:
            raise ValueError("explicit field availability required")
        for proposal in self.proposed_fields:
            field = (
                proposal.current.field if isinstance(proposal, ProposedField) else proposal.field
            )
            if field not in allowed.get(self.kind, set()):
                raise ValueError("proposed field incompatible with action kind")
            if (
                isinstance(proposal, ProposedField)
                and proposal.evidence_key not in self.evidence_keys
            ):
                raise ValueError("proposed field evidence required")
        if isinstance(self.native_budget, NativeBudget):
            if not isinstance(self.target, TargetRef):
                raise ValueError("native budget requires entity target")
            if self.target.budget_owner_key != self.native_budget.owner_key:
                raise ValueError("exact native budget owner required")
            if self.native_budget.evidence_key not in self.evidence_keys:
                raise ValueError("native budget evidence required")
        return self


class Allocation(Frozen):
    key: Key
    target: TargetRef
    amount_micros: Amount
    rationale: Text
    evidence_keys: tuple[Key, ...] = Field(min_length=1, max_length=20)


class BudgetScenario(NoAuthority):
    provenance: Literal["generated", "customer_supplied_hypothesis"] = "generated"
    customer_intent_key: Key | None = None
    key: Key
    title: Title
    period: BudgetPeriod
    ceiling_micros: Amount
    allocations: tuple[Allocation, ...] = Field(max_length=100)
    unallocated_micros: Amount
    assumptions: tuple[Text, ...] = Field(max_length=20)
    semantics: Literal["independent_alternative"] = "independent_alternative"
    native_conversion: Literal["not_assessed"] = "not_assessed"
    forecast: None = None

    @model_validator(mode="after")
    def reconciled(self) -> "BudgetScenario":
        if (self.provenance == "customer_supplied_hypothesis") != (
            self.customer_intent_key is not None
        ):
            raise ValueError("exact customer scenario provenance required")
        if (
            sum(a.amount_micros for a in self.allocations) + self.unallocated_micros
            != self.ceiling_micros
        ):
            raise ValueError("scenario must reconcile independently to ceiling")
        unique(tuple(a.key for a in self.allocations), "allocation")
        unique(tuple(a.target.canonical_entity_key for a in self.allocations), "allocation target")
        owners = tuple(
            (a.target.account.account_id, a.target.budget_owner_key)
            for a in self.allocations
            if a.target.budget_owner_key is not None
        )
        unique(owners, "shared budget owner allocation")
        return self


class CreativeBrief(NoAuthority):
    key: Key
    action_key: Key
    target: TargetRef | AccountTarget
    product_facts: tuple[Text, ...] = Field(max_length=20)
    hypotheses: tuple[Text, ...] = Field(max_length=20)
    placement: Text
    format: Text
    asset_gaps: tuple[Text, ...] = Field(max_length=20)
    landing_page_constraints: tuple[Text, ...] = Field(min_length=1, max_length=20)
    objective: Text
    audience: Text
    offer: Text
    claim_evidence_keys: tuple[Key, ...] = Field(min_length=1, max_length=20)
    assumption_keys: tuple[Key, ...] = Field(max_length=20)
    hooks: tuple[Text, ...] = Field(min_length=1, max_length=10)
    copy_directions: tuple[Text, ...] = Field(min_length=1, max_length=10)
    visual_directions: tuple[Text, ...] = Field(min_length=1, max_length=10)
    required_assets: tuple[Text, ...] = Field(min_length=1, max_length=20)
    customer_review_checklist: tuple[Text, ...] = Field(min_length=1, max_length=20)
    measurement_plan: Text
    asset_publication: Literal["unavailable"] = "unavailable"
