"""Immutable planning artifact; runtime source resolution remains a separate boundary."""

from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from app.planning_documents.actions import BudgetScenario, CreativeBrief, ManualAction, NativeBudget
from app.planning_documents.common import (
    MAX_ACTIONS,
    MAX_BRIEFS,
    MAX_DOCUMENT_BYTES,
    MAX_EVIDENCE,
    MAX_SCENARIOS,
    Digest,
    Id,
    NoAuthority,
    Positive,
    Text,
    unique,
)
from app.planning_documents.context import AccountTarget, EvidenceRef, PlanInputRevision, TargetRef
from app.planning_documents.fields import ProposedField
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
    reject_legacy_selected,
)
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1


class PlanVersion(NoAuthority):
    schema_version: Literal["inlet.plan-version.v1"] = "inlet.plan-version.v1"
    inputs: PlanInputRevision
    version: Positive
    parent_digest: Digest | None
    generator_version: Text
    policy_version: Text
    readiness: Literal["reviewable", "needs_input"]
    section_limitations: tuple[Text, ...] = Field(max_length=30)
    generated_by: Id
    generated_at: AwareDatetime
    valid_until: AwareDatetime
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=MAX_EVIDENCE)
    actions: tuple[ManualAction, ...] = Field(max_length=MAX_ACTIONS)
    scenarios: tuple[BudgetScenario, ...] = Field(min_length=1, max_length=MAX_SCENARIOS)
    briefs: tuple[CreativeBrief, ...] = Field(max_length=MAX_BRIEFS)
    summary: Text
    limitations: tuple[Text, ...] = Field(min_length=1, max_length=30)
    quality_status: Literal["not_expert_qualified"] = "not_expert_qualified"
    selected_reporting_proof: SelectedRetainedProofV1 | None = None

    @model_serializer(mode="wrap")
    def serialize_selected_proof(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result: dict[str, Any] = handler(self)
        if self.selected_reporting_proof is None:
            result.pop("selected_reporting_proof", None)
        return result

    @model_validator(mode="after")
    def coherent(self) -> "PlanVersion":
        reject_legacy_selected(
            self.inputs.selected_reporting, self.policy_version, self.generator_version
        )
        selected_policy = (self.policy_version, self.generator_version) == (
            SELECTED_POLICY_VERSION,
            SELECTED_GENERATOR_VERSION,
        )
        if selected_policy:
            if self.selected_reporting_proof is None:
                raise ValueError("selected planning requires retained proof")
            privacy = self.evidence[0].privacy_revision
            if any(item.privacy_revision != privacy for item in self.evidence):
                raise ValueError("selected evidence privacy mismatch")
            self.selected_reporting_proof.assert_inputs(self.inputs, privacy)
        elif self.selected_reporting_proof is not None:
            raise ValueError("selected retained proof requires the exact v4 policy pair")
        if (self.version == 1) != (self.parent_digest is None):
            raise ValueError("version ancestry required")
        if not self.inputs.created_at <= self.generated_at < self.valid_until:
            raise ValueError("ordered document validity required")
        for values, label in (
            (tuple(e.key for e in self.evidence), "evidence"),
            (tuple(a.key for a in self.actions), "action"),
            (tuple(a.priority for a in self.actions), "priority"),
            (tuple(s.key for s in self.scenarios), "scenario"),
            (tuple(b.key for b in self.briefs), "brief"),
        ):
            unique(values, label)
        evidence = {e.key: e for e in self.evidence}
        accounts = {a.account_id: a for a in self.inputs.accounts}
        assumptions = {a.key for a in self.inputs.assumptions}
        actions = {a.key: a for a in self.actions}
        for e in self.evidence:
            if (
                e.workspace_id != self.inputs.workspace_id
                or (e.account is not None and accounts.get(e.account.account_id) != e.account)
                or e.observed_at > self.generated_at
                or e.expires_at < self.valid_until
            ):
                raise ValueError("evidence ownership/freshness mismatch")

        native_identities: dict[tuple[int, str, str, str], str] = {}
        canonical_references: dict[str, tuple[str, str, str, str | None]] = {}

        def target(value: TargetRef | AccountTarget) -> None:
            if isinstance(value, AccountTarget):
                if accounts.get(value.account.account_id) != value.account:
                    raise ValueError("foreign account target")
                return
            ref = value.provider_reference
            identity = (value.account.account_id, ref.advertiser_id, value.kind, ref.entity_id)
            reference = (ref.platform, ref.advertiser_id, ref.entity_id, ref.parent_campaign_id)
            if (
                native_identities.setdefault(identity, value.canonical_entity_key)
                != value.canonical_entity_key
            ):
                raise ValueError("provider identity cannot alias multiple canonical keys")
            if canonical_references.setdefault(value.canonical_entity_key, reference) != reference:
                raise ValueError("canonical target has inconsistent provider reference")
            catalog = evidence.get(value.catalog_evidence_key)
            if (
                accounts.get(value.account.account_id) != value.account
                or value.canonical_entity_key in self.inputs.excluded_entity_keys
                or catalog is None
                or catalog.kind != "native_catalog"
                or catalog.account != value.account
                or catalog.coverage == "unavailable"
            ):
                raise ValueError("target must bind available owned catalog evidence")

        def refs(keys: tuple[str, ...], assumption_keys: tuple[str, ...] = ()) -> None:
            if not set(keys) <= evidence.keys() or not set(assumption_keys) <= assumptions:
                raise ValueError("unknown evidence or assumption reference")

        def native_fact(evidence_key: str, value: TargetRef) -> None:
            item = evidence[evidence_key]
            if (
                evidence_key != value.catalog_evidence_key
                or item.kind != "native_catalog"
                or item.account != value.account
                or item.coverage == "unavailable"
            ):
                raise ValueError(
                    "typed native fact requires exact available target catalog evidence"
                )

        proposed_settings: dict[tuple[int, str, str], str] = {}

        def setting(key: tuple[int, str, str], value: str) -> None:
            if proposed_settings.setdefault(key, value) != value:
                raise ValueError("contradictory proposals for the same native setting")

        for action in self.actions:
            target(action.target)
            refs(action.evidence_keys, action.assumption_keys)
            if isinstance(action.target, TargetRef):
                for proposal in action.proposed_fields:
                    if isinstance(proposal, ProposedField):
                        native_fact(proposal.evidence_key, action.target)
                        setting(
                            (
                                action.target.account.account_id,
                                action.target.canonical_entity_key,
                                proposal.proposed.field,
                            ),
                            proposal.proposed.digest(),
                        )
                if isinstance(action.native_budget, NativeBudget):
                    native = action.native_budget
                    native_fact(native.evidence_key, action.target)
                    # Unit/cadence and current value are part of the comparison;
                    # incompatible baselines cannot masquerade as equal proposals.
                    setting(
                        (action.target.account.account_id, native.owner_key, "native_budget"),
                        repr(
                            (
                                native.unit,
                                native.currency,
                                native.cadence,
                                native.current_amount,
                                native.proposed_amount,
                            )
                        ),
                    )
            refs(action.evidence_keys, action.assumption_keys)
            if (
                isinstance(action.native_budget, NativeBudget)
                and action.native_budget.currency != self.inputs.budget_period.currency
            ):
                raise ValueError("native currency cannot imply an unqualified FX conversion")
            if not set(action.conflicts) <= actions.keys() or action.key in action.conflicts:
                raise ValueError("invalid conflict reference")
            if set(action.conflicts) & set(action.prerequisites):
                raise ValueError("conflicting prerequisite")
            if any(action.key not in actions[key].conflicts for key in action.conflicts):
                raise ValueError("conflicts must be reciprocal")
            if not set(action.prerequisites) <= actions.keys():
                raise ValueError("unknown prerequisite")
        # Bounded DAG walk rejects circular instructions without recursive expansion.
        pending = {key: set(action.prerequisites) for key, action in actions.items()}
        while pending:
            ready = {key for key, dependencies in pending.items() if not dependencies}
            if not ready:
                raise ValueError("cyclic action prerequisites")
            pending = {key: deps - ready for key, deps in pending.items() if key not in ready}
        intents = {i.key: i for i in self.inputs.scenario_intents}
        supplied_keys = tuple(
            s.customer_intent_key for s in self.scenarios if s.customer_intent_key is not None
        )
        unique(supplied_keys, "customer scenario output")
        if set(supplied_keys) != set(intents):
            raise ValueError("every customer alternative must be represented exactly once")
        for scenario in self.scenarios:
            if scenario.customer_intent_key is not None:
                intent = intents[scenario.customer_intent_key]
                proposed = {(a.target.digest(), a.amount_micros) for a in scenario.allocations}
                requested = {(a.target.digest(), a.amount_micros) for a in intent.allocations}
                if (
                    proposed != requested
                    or scenario.unallocated_micros != intent.unallocated_micros
                ):
                    raise ValueError("customer hypothetical allocations changed")
            if (
                scenario.period != self.inputs.budget_period
                or scenario.ceiling_micros != self.inputs.total_ceiling_micros
            ):
                raise ValueError("scenario must bind exact confirmed budget")
            for fixed in self.inputs.fixed_allocations:
                matched = [a for a in scenario.allocations if a.target == fixed.target]
                if len(matched) != 1 or matched[0].amount_micros != fixed.amount_micros:
                    raise ValueError("each alternative must preserve fixed allocations")
            for allocation in scenario.allocations:
                target(allocation.target)
                refs(allocation.evidence_keys)
        capacity = self.inputs.maximum_creative_assets
        if capacity is not None and sum(len(b.required_assets) for b in self.briefs) > capacity:
            raise ValueError("creative asset requests exceed customer capacity")
        for brief in self.briefs:
            target(brief.target)
            refs(brief.claim_evidence_keys, brief.assumption_keys)
            brief_action = actions.get(brief.action_key)
            if (
                brief_action is None
                or brief_action.kind != "creative_review"
                or brief_action.target != brief.target
            ):
                raise ValueError("brief must bind exact creative action target")
        if len(self.model_dump_json().encode()) > MAX_DOCUMENT_BYTES:
            raise ValueError("plan exceeds operational document size")
        return self
