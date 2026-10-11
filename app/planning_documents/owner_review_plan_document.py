"""Complete original linked catalog/document joins; no runtime or SQL authority."""

from app.planning_documents.actions import ManualAction
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.context import EvidenceRef, PlanInputRevision
from app.planning_documents.google_budget_input_bindings import _targets
from app.planning_documents.google_budget_owner_contracts import _originals
from app.planning_documents.google_budget_owner_review import validate_google_budget_owner_review
from app.planning_documents.google_budget_owner_review_contracts import (
    GoogleBudgetOwnerReviewProofV1,
)
from app.planning_documents.source_contracts import SourceFence


def linked_owner_input_catalogs(
    inputs: PlanInputRevision, catalogs: tuple[CatalogEvidence, ...]
) -> tuple[CatalogEvidence, ...]:
    """Select the complete ordinary input-linked set from an actual bounded catalog tuple."""
    if type(catalogs) is not tuple or len(catalogs) > 20:
        raise ValueError("bounded catalog tuple required")
    _originals(catalogs)
    inputs = PlanInputRevision.model_validate(inputs)
    catalogs = tuple(CatalogEvidence.model_validate(c) for c in catalogs)
    accounts = set(inputs.accounts)
    seen = set()
    by_key = {}
    for catalog in catalogs:
        account = catalog.reference.account
        if account not in accounts or account in seen:
            raise ValueError("unique full owned catalog account required")
        seen.add(account)
        for target in _targets(catalog):
            if target.canonical_entity_key in by_key:
                raise ValueError("ambiguous input catalog target")
            by_key[target.canonical_entity_key] = target
    chosen = [a.target for a in inputs.fixed_allocations] + [
        a.target for s in inputs.scenario_intents for a in s.allocations
    ]
    for key in inputs.excluded_entity_keys:
        if key not in by_key:
            raise ValueError("missing excluded target catalog")
        chosen.append(by_key[key])
    for target in chosen:
        actual = by_key.get(target.canonical_entity_key)
        if actual is None or actual.model_dump_json() != target.model_dump_json():
            raise ValueError("exact full input target catalog required")
    used = {t.account for t in chosen}
    return tuple(
        sorted(
            (c for c in catalogs if c.reference.account in used),
            key=lambda c: c.reference.account.account_id if c.reference.account else -1,
        )
    )


def validate_owner_review_document(
    *,
    inputs: PlanInputRevision,
    actions: tuple[ManualAction, ...],
    proof: GoogleBudgetOwnerReviewProofV1,
    catalogs: tuple[CatalogEvidence, ...],
    sources: tuple[SourceFence, ...],
    evidence: tuple[EvidenceRef, ...],
    privacy_revision: int,
) -> None:
    expected = linked_owner_input_catalogs(inputs, catalogs)
    if tuple(c.model_dump_json() for c in expected) != tuple(c.model_dump_json() for c in catalogs):
        raise ValueError("exact ordered complete linked catalog set required")
    for catalog in catalogs:
        matches = [ref for ref in evidence if ref.key == catalog.reference.key]
        if len(matches) != 1 or matches[0].model_dump_json() != catalog.reference.model_dump_json():
            raise ValueError("linked catalog must bind exact document evidence")
    validate_google_budget_owner_review(
        inputs=inputs,
        actions=actions,
        proof=proof,
        catalogs=catalogs,
        sources=sources,
        privacy_revision=privacy_revision,
    )
