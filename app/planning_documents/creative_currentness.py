"""Viewer-scoped image metadata currentness; no byte or provider-freshness claim."""

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaign_review.models import MediaObject
from app.customers.access import CustomerPrincipal
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents.creative_image_collection import PlanningImageRowPinV1
from app.planning_documents.creative_inputs import (
    CREATIVE_GENERATOR_VERSION,
    CREATIVE_POLICY_VERSION,
)
from app.planning_documents.creative_retained_proof import creative_image_row_identity_digest
from app.planning_documents.documents import PlanVersion
from app.planning_documents.retained_sources import (
    RetainedSourcesChanged,
    RetainedSourceWitness,
    _goal,
    _guard,
)
from app.shopify.security import utc


def _capture_creative_retained_source(
    db: Session,
    *,
    principal: CustomerPrincipal,
    document: PlanVersion,
    now: datetime,
) -> RetainedSourceWitness:
    """Caller owns fresh viewer fact/final authority and workspace-first transaction."""
    from app.planning_documents.creative_history import _creative_local_witness
    from app.planning_documents.selected_policy_contract import selected_policy_contract

    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise RetainedSourcesChanged("source_changed")
    now = now.astimezone(UTC)
    try:
        document = PlanVersion.model_validate(document)
    except ValidationError:
        raise RetainedSourcesChanged("proof_unavailable") from None
    proof = document.creative_proof
    if (
        not selected_policy_contract(
            document.policy_version, document.generator_version
        ).requires_creative
        or proof is None
    ):
        raise RetainedSourcesChanged("proof_unavailable")
    root = db.get_transaction()
    if (
        root is None
        or not root.is_active
        or db.in_nested_transaction()
        or db.new
        or db.dirty
        or db.deleted
    ):
        raise RetainedSourcesChanged("source_changed")
    connection = db.connection()
    transaction = connection.get_transaction()
    if transaction is None:
        raise RetainedSourcesChanged("source_changed")
    wid = document.inputs.workspace_id

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
            raise RetainedSourcesChanged("source_changed")

    def sample() -> None:
        clean()
        current = max(now, utc(database_utc_now(db)))
        clean()
        if not utc(document.generated_at) <= current < utc(document.valid_until):
            raise RetainedSourcesChanged("source_changed")

    def guard() -> None:
        clean()
        _guard(db, principal, wid, principal.user.id)
        clean()
        _goal(db, document)
        clean()
        if workspace_export_revision(db, wid) != proof.basis.privacy_revision:
            raise RetainedSourcesChanged("source_changed")
        sample()
        _guard(db, principal, wid, principal.user.id)
        clean()
        sample()

    with db.no_autoflush:
        guard()
        for image, commitment in zip(proof.basis.images, proof.images, strict=True):
            clean()
            row = db.scalar(
                select(MediaObject)
                .where(MediaObject.workspace_id == wid, MediaObject.id == image.media_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            clean()
            if row is None:
                raise RetainedSourcesChanged("source_changed")
            try:
                pin = PlanningImageRowPinV1(
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
                        observed_at=image.observed_at,
                        privacy_revision=proof.basis.privacy_revision,
                    ),
                )
                digest = creative_image_row_identity_digest(pin)
            except ValidationError:
                raise RetainedSourcesChanged("source_changed") from None
            if digest != commitment.row_identity_digest:
                raise RetainedSourcesChanged("source_changed")
        guard()
        witness = _creative_local_witness(document)
        clean()
        _guard(db, principal, wid, principal.user.id)
        clean()
        sample()
        return witness


def capture_creative_retained_source(
    db: Session, *, principal: CustomerPrincipal, document: PlanVersion, now: datetime
) -> RetainedSourceWitness:
    try:
        document = PlanVersion.model_validate(document)
    except ValueError:
        raise RetainedSourcesChanged("proof_unavailable") from None
    if (document.policy_version, document.generator_version) != (
        CREATIVE_POLICY_VERSION,
        CREATIVE_GENERATOR_VERSION,
    ):
        raise RetainedSourcesChanged("proof_unavailable")
    return _capture_creative_retained_source(db, principal=principal, document=document, now=now)
