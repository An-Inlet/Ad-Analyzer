"""SQL-only private image recheck; no runtime wiring or independent authority."""

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.entitlements import paid_work
from app.campaign_review.models import MediaObject
from app.customers.access import CustomerPrincipal, guard_customer_mutation
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents.authority import OWNER_ROLES
from app.planning_documents.creative_image_collection import (
    CollectedCreativeBasisV1,
    PlanningImageRowPinV1,
)
from app.planning_documents.creative_retained_proof import (
    CreativeRetainedProofV1,
    creative_image_row_identity_digest,
    creative_proof_from_collection,
)
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.repository import check_goal
from app.shopify.security import utc


def changed() -> HTTPException:
    return HTTPException(409, "creative image source changed")


def recheck_collected_creative(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    collection: CollectedCreativeBasisV1,
    now: datetime,
    authorize: Callable[[Session, int, str], None],
) -> CreativeRetainedProofV1:
    """Caller owns original authority and root transaction; never commit or do IO."""
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise changed()
    now = now.astimezone(UTC)
    try:
        ticket = GenerationTicket.model_validate(ticket)
        collection = CollectedCreativeBasisV1.model_validate(collection)
        collection.assert_ticket(ticket)
    except ValueError:
        raise changed() from None
    if (principal.user.id, principal.session.digest) != (ticket.actor_id, ticket.session_digest):
        raise HTTPException(401, "original customer session required")
    root = db.get_transaction()
    if (
        root is None
        or not root.is_active
        or db.in_nested_transaction()
        or db.new
        or db.dirty
        or db.deleted
    ):
        raise changed()
    connection = db.connection()
    transaction = connection.get_transaction()
    if transaction is None:
        raise changed()

    def clean() -> None:
        if (
            db.get_transaction() is not root
            or not root.is_active
            or connection.closed
            or db.connection() is not connection
            or connection.get_transaction() is not transaction
            or not transaction.is_active
            or db.in_nested_transaction()
            or connection.in_nested_transaction()
            or db.new
            or db.dirty
            or db.deleted
        ):
            raise changed()

    def sample() -> datetime:
        clean()
        result = max(now, utc(database_utc_now(db)))
        clean()
        if (
            utc(ticket.prepared_at) > result
            or utc(ticket.inputs.created_at) > result
            or any(utc(row.witness.observed_at) > result for row in collection.rows)
        ):
            raise changed()
        return result

    def guard() -> None:
        clean()
        authorize(db, ticket.inputs.workspace_id, ticket.actor_id)
        clean()
        guard_customer_mutation(
            db, principal, ticket.inputs.workspace_id, allowed_roles=OWNER_ROLES
        )
        clean()
        paid_work(db, ticket.inputs.workspace_id, sample())
        clean()
        check_goal(db, ticket.inputs, sample())
        clean()
        if workspace_export_revision(db, ticket.inputs.workspace_id) != ticket.privacy_revision:
            raise changed()
        sample()
        authorize(db, ticket.inputs.workspace_id, ticket.actor_id)
        clean()
        sample()

    # Reject dirty state before any possible autoflush, including inside callbacks.
    with db.no_autoflush:
        guard()
        for pin in collection.rows:
            clean()
            row = db.scalar(
                select(MediaObject)
                .where(
                    MediaObject.workspace_id == ticket.inputs.workspace_id,
                    MediaObject.id == pin.witness.media_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            clean()
            if row is None:
                raise changed()
            try:
                current = PlanningImageRowPinV1.model_validate(
                    dict(
                        created_by=row.created_by,
                        witness=dict(
                            workspace_id=row.workspace_id,
                            media_id=row.id,
                            sha256=row.sha256,
                            size=row.size,
                            mime=row.mime,
                            width=row.width,
                            height=row.height,
                            created_at=utc(row.created_at),
                            observed_at=pin.witness.observed_at,
                            privacy_revision=ticket.privacy_revision,
                        ),
                    )
                )
                if creative_image_row_identity_digest(
                    current
                ) != creative_image_row_identity_digest(pin):
                    raise changed()
            except ValidationError:
                raise changed() from None
        guard()
        try:
            proof = creative_proof_from_collection(collection, ticket)
        except ValueError:
            raise changed() from None
        clean()
        authorize(db, ticket.inputs.workspace_id, ticket.actor_id)
        clean()
        sample()
        return proof
