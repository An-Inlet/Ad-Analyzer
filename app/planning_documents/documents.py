"""Immutable planning artifact; runtime source resolution remains a separate boundary."""

from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    model_serializer,
    model_validator,
)

from app.planning_documents.actions import BudgetScenario, CreativeBrief, ManualAction, NativeBudget
from app.planning_documents.catalog_evidence import CatalogEvidence
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
from app.planning_documents.constraint_interpretation import ConstraintInterpretationV1
from app.planning_documents.constraint_policy import is_constraint_policy
from app.planning_documents.context import AccountTarget, EvidenceRef, PlanInputRevision, TargetRef
from app.planning_documents.creative_inputs import (
    CREATIVE_GENERATOR_VERSION,
    CREATIVE_POLICY_VERSION,
    validate_creative_policy,
)
from app.planning_documents.creative_plan_document import (
    creative_instant,
    validate_creative_document,
)
from app.planning_documents.creative_production_contracts import CreativeCompositionV1
from app.planning_documents.creative_retained_proof import CreativeRetainedProofV1
from app.planning_documents.empty_catalog_validation import validate_empty_catalog_proposals
from app.planning_documents.fields import ProposedField
from app.planning_documents.google_budget_generation_guard import reject_google_budget_generation
from app.planning_documents.google_budget_owner_contracts import _originals
from app.planning_documents.google_budget_owner_review_contracts import (
    GoogleBudgetOwnerReviewProofV1,
)
from app.planning_documents.owner_review_plan_document import validate_owner_review_document
from app.planning_documents.owner_review_policy import is_owner_review_policy
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
    reject_legacy_selected,
)
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1


class PlanVersion(NoAuthority):
    schema_version: Literal[
        "inlet.plan-version.v1",
        "inlet.plan-version.v2",
        "inlet.plan-version.v3",
        "inlet.plan-version.v4",
    ] = "inlet.plan-version.v1"
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

    constraint_interpretation: ConstraintInterpretationV1 | None = None
    creative_proof: CreativeRetainedProofV1 | None = None
    creative_composition: CreativeCompositionV1 | None = None

    google_budget_owner_review: GoogleBudgetOwnerReviewProofV1 | None = None
    google_budget_input_catalogs: tuple[CatalogEvidence, ...] | None = Field(
        default=None, max_length=20
    )

    @model_validator(mode="before")
    @classmethod
    def creative_instants(cls, value: Any) -> Any:
        # Normalize only the new v5 path, before nested EvidenceRef's legacy
        # wall-clock comparisons. Existing policy serialization is untouched.
        if isinstance(value, cls):
            raw = dict(value.__dict__)
        elif isinstance(value, dict):
            raw = dict(value)
        else:
            return value
        if (
            (raw.get("policy_version"), raw.get("generator_version"))
            != (
                CREATIVE_POLICY_VERSION,
                CREATIVE_GENERATOR_VERSION,
            )
            and not is_owner_review_policy(raw.get("policy_version"), raw.get("generator_version"))
            and not is_constraint_policy(raw.get("policy_version"), raw.get("generator_version"))
        ):
            return value
        if is_owner_review_policy(raw.get("policy_version"), raw.get("generator_version")):
            _originals(raw.get("google_budget_input_catalogs"))
        for key in ("generated_at", "valid_until"):
            if key in raw:
                raw[key] = creative_instant(raw[key])
        if isinstance(raw.get("evidence"), (list, tuple)):
            refs = []
            for ref in raw["evidence"]:
                if not isinstance(ref, (EvidenceRef, dict)):
                    refs.append(ref)
                    continue
                item = ref.model_dump() if isinstance(ref, EvidenceRef) else dict(ref)
                for key in ("observation_started_at", "observed_at", "expires_at"):
                    if key in item:
                        item[key] = creative_instant(item[key])
                refs.append(item)
            raw["evidence"] = tuple(refs)
        return raw

    @model_serializer(mode="wrap")
    def serialize_selected_proof(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        checked = self
        if (
            self.constraint_interpretation is not None
            or self.policy_version == "inlet.descriptive-review.v7"
            or self.generator_version == "inlet.descriptive-planning.v7"
            or self.policy_version == "inlet.descriptive-review.v6"
            or self.generator_version == "inlet.descriptive-planning.v6"
            or self.google_budget_owner_review is not None
            or self.google_budget_input_catalogs is not None
            or self.inputs.google_daily_budget_intents is not None
        ):
            checked = type(self).model_validate(self)
        result: dict[str, Any] = handler(checked)
        if self.constraint_interpretation is None:
            result.pop("constraint_interpretation", None)
        if self.selected_reporting_proof is None:
            result.pop("selected_reporting_proof", None)
        if self.creative_proof is None:
            result.pop("creative_proof", None)
        if self.creative_composition is None:
            result.pop("creative_composition", None)
        if self.google_budget_owner_review is None:
            result.pop("google_budget_owner_review", None)
        if self.google_budget_input_catalogs is None:
            result.pop("google_budget_input_catalogs", None)
        return result

    @model_validator(mode="after")
    def coherent(self) -> "PlanVersion":
        captures = (
            tuple(
                proof.capture_pin
                for proof in self.selected_reporting_proof.accounts
                if proof.capture_pin is not None
            )
            if self.selected_reporting_proof is not None
            else ()
        )
        has_settings = any(
            pin.observation_provenance is not None
            and pin.observation_provenance.settings is not None
            for pin in captures
        )
        constraint_policy = is_constraint_policy(self.policy_version, self.generator_version)
        if (self.schema_version == "inlet.plan-version.v4") != constraint_policy:
            raise ValueError("constraint policy requires plan-version.v4 reader floor")
        if constraint_policy:
            from app.planning_documents.constraint_document import validate_constraint_document

            validate_constraint_document(self)
        elif (
            self.constraint_interpretation is not None
            or self.policy_version == "inlet.descriptive-review.v7"
            or self.generator_version == "inlet.descriptive-planning.v7"
        ):
            raise ValueError("constraint interpretation requires exact v7 policy")
        if (
            not constraint_policy
            and (self.schema_version == "inlet.plan-version.v3") != has_settings
        ):
            raise ValueError("request/effective settings require plan-version.v3")
        if constraint_policy:
            from app.planning_documents.constraint_document import (
                assert_constraint_capture_provenance,
            )

            assert_constraint_capture_provenance(captures)
        if self.schema_version in {"inlet.plan-version.v2", "inlet.plan-version.v3"}:
            captures = (
                tuple(
                    item.capture_pin
                    for item in self.selected_reporting_proof.accounts
                    if item.capture_pin is not None
                )
                if self.selected_reporting_proof is not None
                else ()
            )
            if not captures or any(pin.observation_provenance is None for pin in captures):
                raise ValueError("v2/v3 requires typed provenance for every selected capture")
        # V1 is retained unchanged, including the interim unreleased enriched format.
        # New enriched v1 is refused by the canonical repository write boundary.
        owner_policy = is_owner_review_policy(self.policy_version, self.generator_version)
        if not owner_policy and (
            self.policy_version == "inlet.descriptive-review.v6"
            or self.generator_version == "inlet.descriptive-planning.v6"
        ):
            raise ValueError("reserved owner review identifiers require the exact v6 pair")
        if owner_policy:
            if (
                self.inputs.google_daily_budget_intents is None
                or self.google_budget_owner_review is None
                or self.google_budget_input_catalogs is None
            ):
                raise ValueError("complete explicit owner review document required")
        else:
            reject_google_budget_generation(self.inputs.google_daily_budget_intents)
            if (
                self.google_budget_owner_review is not None
                or self.google_budget_input_catalogs is not None
            ):
                raise ValueError("owner review document requires exact v6 policy")
        validate_creative_policy(self.inputs.creative, self.policy_version, self.generator_version)
        creative_policy = (
            (self.policy_version, self.generator_version)
            == (
                CREATIVE_POLICY_VERSION,
                CREATIVE_GENERATOR_VERSION,
            )
            or owner_policy
            or constraint_policy
        )
        if creative_policy:
            if self.creative_proof is None or self.creative_composition is None:
                raise ValueError("complete creative document proof and composition required")
            validate_creative_document(
                inputs=self.inputs,
                proof=self.creative_proof,
                composition=self.creative_composition,
                evidence=self.evidence,
                actions=self.actions,
                briefs=self.briefs,
                valid_until=self.valid_until,
            )
        elif (
            self.creative_proof is not None
            or self.creative_composition is not None
            or any(ref.kind == "creative_basis" for ref in self.evidence)
        ):
            raise ValueError("creative document evidence requires exact v5 policy")
        reject_legacy_selected(
            self.inputs.selected_reporting, self.policy_version, self.generator_version
        )
        selected_policy = (self.policy_version, self.generator_version) == (
            SELECTED_POLICY_VERSION,
            SELECTED_GENERATOR_VERSION,
        )
        if selected_policy or creative_policy:
            if self.selected_reporting_proof is None:
                raise ValueError("selected planning requires retained proof")
            privacy = self.evidence[0].privacy_revision
            if any(item.privacy_revision != privacy for item in self.evidence):
                raise ValueError("selected evidence privacy mismatch")
            self.selected_reporting_proof.assert_inputs(self.inputs, privacy)
        elif self.selected_reporting_proof is not None:
            raise ValueError("selected retained proof requires the exact v4 policy pair")
        if creative_policy:
            assert self.creative_composition is not None
            assert self.selected_reporting_proof is not None
            validate_empty_catalog_proposals(
                inputs=self.inputs,
                proposals=self.creative_composition.proposals,
                actions=self.actions,
                evidence=self.evidence,
                sources=tuple(p.source_fence for p in self.selected_reporting_proof.accounts),
                generated_at=self.generated_at,
                valid_until=self.valid_until,
                privacy_revision=self.evidence[0].privacy_revision,
            )
        if owner_policy:
            assert self.google_budget_owner_review is not None
            assert self.google_budget_input_catalogs is not None
            assert self.selected_reporting_proof is not None
            validate_owner_review_document(
                inputs=self.inputs,
                actions=self.actions,
                proof=self.google_budget_owner_review,
                catalogs=self.google_budget_input_catalogs,
                evidence=self.evidence,
                sources=tuple(p.source_fence for p in self.selected_reporting_proof.accounts),
                privacy_revision=self.evidence[0].privacy_revision,
            )
        if (self.version == 1) != (self.parent_digest is None):
            raise ValueError("version ancestry required")
        created = (
            creative_instant(self.inputs.created_at) if creative_policy else self.inputs.created_at
        )
        if not created <= self.generated_at < self.valid_until:
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
        if owner_policy or constraint_policy:
            # Serialize already validated child values, not this document's checked
            # serializer: invoking it here would recursively validate this node.
            omitted = {
                "constraint_interpretation",
                "selected_reporting_proof",
                "creative_proof",
                "creative_composition",
                "google_budget_owner_review",
                "google_budget_input_catalogs",
            }
            payload = {
                key: getattr(self, key)
                for key in type(self).model_fields
                if key not in omitted or getattr(self, key) is not None
            }
            size = len(TypeAdapter(dict[str, Any]).dump_json(payload))
        else:
            size = len(self.model_dump_json().encode())
        if size > MAX_DOCUMENT_BYTES:
            raise ValueError("plan exceeds operational document size")
        return self
