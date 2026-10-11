"""V6 actual collection and original current receipt joins; no provider IO."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.catalog_receipts import resolve_saved_input_catalogs
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.documents import PlanVersion
from app.planning_documents.google_budget_owner_review import validate_google_budget_owner_review
from app.planning_documents.owner_review_plan_document import linked_owner_input_catalogs
from app.planning_documents.owner_review_policy import is_owner_review_policy
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.selected_policy_contract import assert_selected_ticket_policy

_DETAIL = "owner review differs from actual collected evidence"


def _catalog_bytes(catalogs: tuple[CatalogEvidence, ...]) -> tuple[str, ...]:
    return tuple(c.model_dump_json() for c in catalogs)


def _linked(
    ticket: GenerationTicket, candidate: PlanVersion, catalogs: tuple[CatalogEvidence, ...]
) -> tuple[CatalogEvidence, ...]:
    ticket = GenerationTicket.model_validate(ticket)
    candidate = PlanVersion.model_validate(candidate)
    if not is_owner_review_policy(candidate.policy_version, candidate.generator_version):
        raise ValueError("exact owner review document required")
    contract = assert_selected_ticket_policy(ticket.policy_version, ticket.policy_digest)
    if (
        not contract.requires_owner_review
        or ticket.policy_version != candidate.policy_version
        or ticket.inputs.digest() != candidate.inputs.digest()
        or candidate.google_budget_owner_review is None
        or candidate.google_budget_input_catalogs is None
    ):
        raise ValueError("exact owner generation ticket required")
    actual = linked_owner_input_catalogs(ticket.inputs, catalogs)
    if _catalog_bytes(actual) != _catalog_bytes(candidate.google_budget_input_catalogs):
        raise ValueError("complete actual linked catalogs required")
    # This invocation's full PlanVersion validation already checked the same
    # owner review when every argument below is byte-identical. Differences use
    # the original validator; this is neither an acceptance gate nor a cache.
    proof = candidate.selected_reporting_proof
    same_arguments = (
        proof is not None
        and ticket.inputs.model_dump_json() == candidate.inputs.model_dump_json()
        and type(ticket.privacy_revision) is int
        and ticket.privacy_revision == candidate.evidence[0].privacy_revision
        and tuple(source.model_dump_json() for source in ticket.sources)
        == tuple(account.source_fence.model_dump_json() for account in proof.accounts)
    )
    if not same_arguments:
        validate_google_budget_owner_review(
            inputs=ticket.inputs,
            actions=candidate.actions,
            proof=candidate.google_budget_owner_review,
            catalogs=actual,
            sources=ticket.sources,
            privacy_revision=ticket.privacy_revision,
        )
    return actual


def assert_owner_review_generation_bundle(
    *, ticket: GenerationTicket, candidate: PlanVersion, bundle: CreativePairedEvidenceV1
) -> None:
    """Pure complete binding after replay and actual target checks, before writes."""
    try:
        bundle.assert_ticket(ticket)
        _linked(ticket, candidate, bundle.reporting.selected.catalogs)
    except ValueError as error:
        raise HTTPException(409, _DETAIL) from error


def recheck_owner_review_input_receipts(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    candidate: PlanVersion,
    catalogs: tuple[CatalogEvidence, ...],
    now: datetime,
) -> None:
    """Caller owns SQL authority/final guards; resolve original current receipts once."""
    # Keep SQL/callback exceptions and existing typed receipt failures unchanged.
    resolved = resolve_saved_input_catalogs(db, principal=principal, ticket=ticket, now=now)
    try:
        actual = _linked(ticket, candidate, catalogs)
        if _catalog_bytes(resolved.catalogs) != _catalog_bytes(actual):
            raise ValueError("original linked receipt differs")
    except ValueError as error:
        raise HTTPException(409, _DETAIL) from error
