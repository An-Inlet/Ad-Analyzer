"""Owned immutable replacement ancestry, traversed under the workspace/ledger locks."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.publication.execution_contracts import ExposureEvidence
from app.publication.execution_models import (
    ProviderExecutionReview,
    ProviderExposureReservation,
    ProviderReservationReplacement,
)
from app.publication.replacement_contracts import RepeatOptimizationReview, ReplacementAuditDocument


def ancestors(
    db: Session, current: ProviderExposureReservation
) -> list[tuple[ProviderExposureReservation, ProviderReservationReplacement | None]]:
    """Oldest first; every incoming link is bound to its original immutable audit.

    The caller holds the workspace and current period ledger locks. This helper does
    not acquire them in reverse order or grant forward execution authority.
    """
    rows: list[tuple[ProviderExposureReservation, ProviderReservationReplacement | None]] = []
    seen: set[str] = set()
    row = current
    while True:
        if row.id in seen or len(seen) >= 32:
            raise HTTPException(409, "replacement ancestry unavailable")
        seen.add(row.id)
        current_exposure = ExposureEvidence.model_validate(current.evidence)
        row_exposure = ExposureEvidence.model_validate(row.evidence)
        if (
            row_exposure.account != current_exposure.account
            or row_exposure.currency != current_exposure.currency
            or row_exposure.period_start != current_exposure.period_start
            or row_exposure.period_end != current_exposure.period_end
            or row_exposure.target_set_digest != current_exposure.target_set_digest
            or row_exposure.proposed_owner_upper_micros != row.amount_micros
        ):
            raise HTTPException(409, "inherited reservation evidence changed")
        if (
            row.workspace_id != current.workspace_id
            or row.ledger_id != current.ledger_id
            or row.environment != current.environment
            or row.budget_owner_key != current.budget_owner_key
            or (row.id != current.id and row.state != "superseded")
        ):
            raise HTTPException(409, "replacement ancestry scope changed")
        link = db.scalar(
            select(ProviderReservationReplacement).where(
                ProviderReservationReplacement.successor_id == row.id,
                ProviderReservationReplacement.workspace_id == current.workspace_id,
            )
        )
        rows.append((row, link))
        if link is None:
            break
        audit = ReplacementAuditDocument.model_validate(link.document)
        exposure = ExposureEvidence.model_validate(row.evidence)
        review = db.get(ProviderExecutionReview, link.review_id)
        if review is None or review.workspace_id != row.workspace_id:
            raise HTTPException(409, "original replacement review unavailable")
        document = RepeatOptimizationReview.model_validate(review.document)
        if (
            document.digest() != review.digest
            or review.digest != audit.review_digest
            or document.predecessor != audit.snapshot
            or document.replacement != audit.evidence
        ):
            raise HTTPException(409, "original replacement review changed")
        if (
            audit.digest() != link.digest
            or audit.successor_id != row.id
            or audit.predecessor_id != link.predecessor_id
            or audit.successor_run_id != link.successor_run_id
            or audit.review_id != link.review_id
            or audit.snapshot.workspace_id != row.workspace_id
            or audit.snapshot.ledger_id != row.ledger_id
            or audit.snapshot.environment != row.environment
            or audit.snapshot.budget_owner_key != row.budget_owner_key
            or audit.evidence.portfolio != exposure
            or link.new_amount_micros != row.amount_micros
            or link.old_amount_micros != audit.snapshot.ancestry[-1].amount_micros
        ):
            raise HTTPException(409, "replacement audit lineage changed")
        predecessor = db.scalar(
            select(ProviderExposureReservation).where(
                ProviderExposureReservation.id == link.predecessor_id,
                ProviderExposureReservation.workspace_id == current.workspace_id,
            )
        )
        if predecessor is None:
            raise HTTPException(409, "original reservation unavailable")
        row = predecessor
    rows.reverse()
    # Each prior transfer must contain the complete earlier chain, not merely the
    # immediately previous reservation. This prevents dropped original obligations.
    for index, (_, link) in enumerate(rows):
        if link is not None:
            audit = ReplacementAuditDocument.model_validate(link.document)
            if [a.reservation_id for a in audit.snapshot.ancestry] != [
                ancestor.id for ancestor, _ in rows[:index]
            ]:
                raise HTTPException(409, "replacement audit omitted original ancestors")
            for recorded, (ancestor, incoming) in zip(
                audit.snapshot.ancestry, rows[:index], strict=True
            ):
                if (
                    recorded.amount_micros != ancestor.amount_micros
                    or recorded.evidence_digest
                    != ExposureEvidence.model_validate(ancestor.evidence).digest()
                    or recorded.replacement_audit_id != (incoming.id if incoming else None)
                    or recorded.replacement_audit_digest != (incoming.digest if incoming else None)
                ):
                    raise HTTPException(409, "original inherited evidence changed")
    return rows
