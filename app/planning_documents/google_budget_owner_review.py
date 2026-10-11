"""Pure input-bound investigation; no native setting, period cap or policy activation."""

import json

from app.planning_documents.actions import ManualAction
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.common import MAX_ACTIONS, MAX_DOCUMENT_BYTES, unique
from app.planning_documents.context import PlanInputRevision, TargetRef
from app.planning_documents.google_budget_input_bindings import (
    validate_google_daily_budget_input_bindings,
)
from app.planning_documents.google_budget_owner_contracts import _originals
from app.planning_documents.google_budget_owner_review_contracts import (
    GoogleBudgetOwnerReviewProofV1,
    GoogleBudgetOwnerReviewV1,
    owner_review_action_key,
)
from app.planning_documents.source_contracts import SourceFence

REVIEW_MESSAGE = (
    "Customer daily hypothesis; period spending impact and provider edit validity "
    "are not assessed. "
    "Do not apply this value from this plan."
)


def _proof(
    inputs: PlanInputRevision,
    catalogs: tuple[CatalogEvidence, ...],
    sources: tuple[SourceFence, ...],
    privacy_revision: int,
) -> tuple[PlanInputRevision, GoogleBudgetOwnerReviewProofV1]:
    # Do not parse away copied raw primitives before the shared strict boundary.
    if inputs.google_daily_budget_intents is None:
        raise ValueError("explicit owner input tuple required")
    witnesses = validate_google_daily_budget_input_bindings(
        inputs=inputs,
        intents=inputs.google_daily_budget_intents,
        catalogs=catalogs,
        sources=sources,
        privacy_revision=privacy_revision,
    )
    inputs = PlanInputRevision.model_validate(inputs)
    assert inputs.google_daily_budget_intents is not None
    return inputs, GoogleBudgetOwnerReviewProofV1(
        input_digest=inputs.digest(),
        reviews=tuple(
            GoogleBudgetOwnerReviewV1(
                action_key=owner_review_action_key(witness), intent=intent, witness=witness
            )
            for intent, witness in zip(inputs.google_daily_budget_intents, witnesses, strict=True)
        ),
    )


def _action(
    inputs: PlanInputRevision, review: GoogleBudgetOwnerReviewV1, priority: int
) -> ManualAction:
    witness, intent = review.witness, review.intent
    scenario = next(s for s in inputs.scenario_intents if s.key == intent.scenario_key)
    reference = witness.catalog_evidence.reference
    return ManualAction(
        key=review.action_key,
        priority=priority,
        kind="investigate",
        target=witness.representative,
        proposed_fields=(),
        conflicts=(),
        measurement_criterion=(
            "Establish period exposure and native edit validity before considering a change."
        ),
        title="Investigate customer shared-budget hypothesis",
        rationale=REVIEW_MESSAGE,
        evidence_keys=(reference.key,),
        assumption_keys=(),
        prerequisites=(),
        manual_steps=(
            (
                f"Review the full shared owner and all {len(witness.affected_campaigns)} "
                "affected campaigns in the attached witness; do not edit members individually."
            ),
            (
                f"Observed native amount: {witness.current_amount_micros} {witness.currency} "
                f"micros per day. Customer hypothesis: {intent.requested_amount_micros} "
                f"{intent.currency} micros per day."
            ),
            (
                f"Named independent alternative: {scenario.title} ({scenario.key}). "
                "Its period allocation is not a conversion of this daily hypothesis."
            ),
            (
                f"Original observation: {reference.observed_at.isoformat()}; "
                f"receipt expiry: {reference.expires_at.isoformat()}. "
                "This is not a fresh provider check."
            ),
            REVIEW_MESSAGE,
        ),
        expected_effect="Unavailable: no spending, delivery, or causal effect is inferred.",
        limitations=(
            "Daily amount no greater than the observed amount does not establish "
            "period ceiling compatibility.",
            "Zero is not evidence of a valid native budget, pause, stopped delivery, "
            "or zero spend.",
            "Provider inventory may have changed outside the retained observation.",
        ),
        native_budget=None,
    )


def _bounded(actions: tuple[ManualAction, ...], proof: GoogleBudgetOwnerReviewProofV1) -> None:
    if len(actions) > MAX_ACTIONS:
        raise ValueError("complete owner review exceeds action bound")
    value = dict(
        actions=[a.model_dump(mode="json") for a in actions], proof=proof.model_dump(mode="json")
    )
    if (
        len(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode())
        > MAX_DOCUMENT_BYTES
    ):
        raise ValueError("complete owner review exceeds document byte bound")


def compose_google_budget_owner_reviews(
    *,
    inputs: PlanInputRevision,
    catalogs: tuple[CatalogEvidence, ...],
    sources: tuple[SourceFence, ...],
    privacy_revision: int,
    first_priority: int,
) -> tuple[tuple[ManualAction, ...], GoogleBudgetOwnerReviewProofV1]:
    if type(first_priority) is not int or not 1 <= first_priority <= MAX_ACTIONS:
        raise ValueError("bounded strict first priority required")
    inputs, proof = _proof(inputs, catalogs, sources, privacy_revision)
    if first_priority + len(proof.reviews) - 1 > MAX_ACTIONS:
        raise ValueError("complete owner review exceeds action priority bound")
    actions = tuple(
        _action(inputs, review, first_priority + i) for i, review in enumerate(proof.reviews)
    )
    _bounded(actions, proof)
    return actions, proof


def validate_google_budget_owner_review(
    *,
    inputs: PlanInputRevision,
    actions: tuple[ManualAction, ...],
    proof: GoogleBudgetOwnerReviewProofV1,
    catalogs: tuple[CatalogEvidence, ...],
    sources: tuple[SourceFence, ...],
    privacy_revision: int,
) -> None:
    if type(actions) is not tuple or len(actions) > MAX_ACTIONS:
        raise ValueError("bounded action tuple required")
    _originals(actions)
    actions = tuple(ManualAction.model_validate(a) for a in actions)
    proof = GoogleBudgetOwnerReviewProofV1.model_validate(proof)
    inputs, expected = _proof(inputs, catalogs, sources, privacy_revision)
    if proof.model_dump_json() != expected.model_dump_json():
        raise ValueError("owner review differs from actual input/catalog evidence")
    unique(tuple(a.key for a in actions), "action key")
    unique(tuple(a.priority for a in actions), "action priority")
    if any(a.priority > MAX_ACTIONS for a in actions):
        raise ValueError("action priority exceeds bound")
    by_key = {a.key: a for a in actions}
    priorities = []
    for review in proof.reviews:
        action = by_key.get(review.action_key)
        if (
            action is None
            or action.model_dump_json()
            != _action(inputs, review, action.priority).model_dump_json()
        ):
            raise ValueError("exact investigation action required")
        priorities.append(action.priority)
        witness = review.witness
        members = {
            (t.provider_reference.advertiser_id, t.provider_reference.entity_id)
            for t in witness.affected_campaigns
        }
        for other in actions:
            target = other.target
            if (
                not isinstance(target, TargetRef)
                or target.account != witness.representative.account
            ):
                continue
            native = target.provider_reference
            affected = (
                target.budget_owner_key == witness.owner_key
                or (native.advertiser_id, native.entity_id) in members
                or (native.advertiser_id, native.parent_campaign_id) in members
            )
            if affected and (
                other.kind in {"budget_review", "status_review"}
                or other.native_budget is not None
                or other.proposed_fields
            ):
                raise ValueError("conflicting native proposal for investigated owner")
    if priorities and priorities != list(range(priorities[0], priorities[0] + len(priorities))):
        raise ValueError("ordered owner priorities required")
    if any(
        a.key.startswith("owner-review:") and a.key not in {r.action_key for r in proof.reviews}
        for a in actions
    ):
        raise ValueError("unbound owner review action")
    _bounded(actions, proof)
