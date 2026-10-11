"""Exact loaded original rows join opaque commitments; no current authority inference."""

from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.catalog_receipt_models import CatalogReceiptRow
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.google_budget_input_bindings import (
    validate_google_daily_budget_input_bindings,
)
from app.planning_documents.google_budget_owner_contracts import GoogleDailyBudgetOwnerWitnessV1
from app.planning_documents.google_budget_owner_selection import original_owner_selection_id
from app.planning_documents.source_contracts import SourceFence


def _commitments(
    inputs: PlanInputRevision,
    loaded: list[tuple[CatalogReceiptRow, CatalogEvidence]],
    sources: tuple[SourceFence, ...],
    witnesses: tuple[GoogleDailyBudgetOwnerWitnessV1, ...],
) -> None:
    intents = inputs.google_daily_budget_intents
    assert intents is not None
    rows = {row.account_id: row for row, _ in loaded}
    fences = {s.account.account_id: s for s in sources}
    if len(rows) != len(loaded) or len(fences) != len(sources):
        raise ValueError("duplicate original owner receipt")
    for intent, witness in zip(intents, witnesses, strict=True):
        if intent.account_id not in rows or intent.account_id not in fences:
            raise ValueError("missing original owner receipt")
        row, source = rows[intent.account_id], fences[intent.account_id]
        if row.actor_id != inputs.created_by or row.workspace_id != inputs.workspace_id:
            raise ValueError("original receipt actor differs")
        expected = original_owner_selection_id(
            actor_id=row.actor_id,
            session_digest=row.session_digest,
            authenticated_at=row.authenticated_at,
            source=source,
            witness=witness,
        )
        if expected != intent.owner_selection_id:
            raise ValueError("original owner commitment differs")


def validate_current_owner_receipts(
    inputs: PlanInputRevision,
    loaded: list[tuple[CatalogReceiptRow, CatalogEvidence]],
    sources: tuple[SourceFence, ...],
    privacy_revision: int,
) -> None:
    if inputs.google_daily_budget_intents is None:
        return
    witnesses = validate_google_daily_budget_input_bindings(
        inputs=inputs,
        intents=inputs.google_daily_budget_intents,
        catalogs=tuple(c for _, c in loaded),
        sources=sources,
        privacy_revision=privacy_revision,
    )
    _commitments(inputs, loaded, sources, witnesses)


def validate_historical_owner_receipts(
    inputs: PlanInputRevision, loaded: list[tuple[CatalogReceiptRow, CatalogEvidence]]
) -> None:
    if inputs.google_daily_budget_intents is None:
        return
    from app.planning_documents.google_budget_input_bindings import (
        validate_retained_google_daily_budget_input_bindings,
    )

    sources = []
    for row, catalog in loaded:
        account = catalog.reference.account
        if account is None:
            raise ValueError("original owned catalog required")
        sources.append(
            SourceFence(
                account=account,
                source_binding_digest=row.source_binding_digest,
                source_revision=row.source_revision,
                privacy_revision=row.privacy_revision,
            )
        )
    fences = tuple(sources)
    witnesses = validate_retained_google_daily_budget_input_bindings(
        inputs=inputs,
        intents=inputs.google_daily_budget_intents,
        catalogs=tuple(c for _, c in loaded),
        sources=fences,
    )
    _commitments(inputs, loaded, fences, witnesses)
