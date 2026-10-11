"""Immutable linked historical evidence; caller owns original authorization/transaction."""

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.catalog_receipts import (
    CatalogReceiptUnavailable,
    _validated_retained_input_receipts,
)
from app.planning_documents.common import Frozen
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.google_budget_owner_contracts import _originals
from app.planning_documents.source_contracts import SourceFence

if TYPE_CHECKING:
    from app.customers.access import CustomerPrincipal
    from app.planning_documents.documents import PlanVersion
    from app.planning_documents.models import PlanDependencyRow
    from app.planning_documents.retained_sources import RetainedSourceWitness


class RetainedOwnerInputEvidence(Frozen):
    catalogs: tuple[CatalogEvidence, ...] = Field(max_length=20)
    sources: tuple[SourceFence, ...] = Field(max_length=20)

    @model_validator(mode="before")
    @classmethod
    def original_values(cls, value: Any) -> Any:
        _originals(value)
        return value

    @model_validator(mode="after")
    def exact(self) -> "RetainedOwnerInputEvidence":
        accounts = tuple(c.reference.account for c in self.catalogs)
        if any(account is None for account in accounts):
            raise ValueError("owned linked catalogs required")
        keys = tuple(account.account_id for account in accounts if account is not None)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("unique ordered owned linked catalogs required")
        if tuple(s.account.account_id for s in self.sources) != keys:
            raise ValueError("exact linked source set required")
        privacy = {s.privacy_revision for s in self.sources}
        if len(privacy) > 1:
            raise ValueError("mixed original privacy epochs")
        for catalog, source in zip(self.catalogs, self.sources, strict=True):
            ref = catalog.reference
            if (
                ref.account,
                ref.source_binding_digest,
                ref.source_revision,
                ref.privacy_revision,
            ) != (
                source.account,
                source.source_binding_digest,
                source.source_revision,
                source.privacy_revision,
            ) or source.source_revision != source.account.connection_version:
                raise ValueError("retained catalog/source mismatch")
        return self


def load_retained_owner_input_evidence(
    db: Session,
    inputs: PlanInputRevision,
) -> RetainedOwnerInputEvidence:
    """SQL-only historical validation; no provider IO or current paid/TTL lookup.

    The caller must already authorize the owned historical read. This internal port
    confers no access rights and retains no mutable SQL objects in its return value.
    Clean-state checks apply at boundaries; they do not detect an already completed
    flush. Caller-owned authorization and final acceptance checks remain required.
    """
    inputs = PlanInputRevision.model_validate(inputs)
    if inputs.google_daily_budget_intents is None:
        raise CatalogReceiptUnavailable("integrity_unavailable")
    root = db.get_transaction()
    if (
        root is None
        or not root.is_active
        or db.in_nested_transaction()
        or db.new
        or db.dirty
        or db.deleted
    ):
        raise CatalogReceiptUnavailable("integrity_unavailable")
    connection = db.connection()
    transaction = connection.get_transaction()

    def guard() -> None:
        if (
            db.get_transaction() is not root
            or not root.is_active
            or db.in_nested_transaction()
            or db.new
            or db.dirty
            or db.deleted
            or connection.closed
            or db.connection() is not connection
            or transaction is None
            or not transaction.is_active
            or connection.get_transaction() is not transaction
            or connection.in_nested_transaction()
        ):
            raise CatalogReceiptUnavailable("integrity_unavailable")

    with db.no_autoflush:
        guard()
        loaded = _validated_retained_input_receipts(db, inputs)
        guard()
        values = []
        for row, catalog in sorted(loaded, key=lambda item: item[0].account_id):
            account = catalog.reference.account
            if account is None:
                raise CatalogReceiptUnavailable("integrity_unavailable")
            source = SourceFence(
                account=account,
                source_binding_digest=row.source_binding_digest,
                source_revision=row.source_revision,
                privacy_revision=row.privacy_revision,
            )
            # Rehydrate scalar value graphs, never leak loaded rows or session references.
            values.append((catalog.model_dump(mode="python"), source.model_dump(mode="python")))
        result = RetainedOwnerInputEvidence.model_validate(
            dict(
                catalogs=tuple(c for c, _ in values),
                sources=tuple(s for _, s in values),
            )
        )
        guard()
        return result


def _owner_document(document: "PlanVersion") -> "PlanVersion":
    from app.planning_documents.documents import PlanVersion
    from app.planning_documents.owner_review_policy import is_owner_review_policy

    value = PlanVersion.model_validate(document)
    if not is_owner_review_policy(value.policy_version, value.generator_version):
        raise ValueError("exact owner review document required")
    return value


def _owner_evidence(db: Session, document: "PlanVersion") -> RetainedOwnerInputEvidence:
    from app.planning_documents.google_budget_owner_review import (
        validate_retained_google_budget_owner_review,
    )

    try:
        value = load_retained_owner_input_evidence(db, document.inputs)
    except CatalogReceiptUnavailable:
        raise ValueError("original owner input evidence unavailable") from None
    if document.google_budget_input_catalogs is None or (
        tuple(c.model_dump_json() for c in value.catalogs)
        != tuple(c.model_dump_json() for c in document.google_budget_input_catalogs)
    ):
        raise ValueError("original owner input catalogs differ")
    if document.google_budget_owner_review is None:
        raise ValueError("original owner proof missing")
    validate_retained_google_budget_owner_review(
        inputs=document.inputs,
        actions=document.actions,
        proof=document.google_budget_owner_review,
        catalogs=value.catalogs,
        sources=value.sources,
    )
    return value


def capture_owner_review_retained_sources(
    db: Session,
    *,
    principal: "CustomerPrincipal",
    document: "PlanVersion",
    now: "datetime",
) -> tuple["RetainedSourceWitness", ...]:
    from app.planning_documents.creative_retained_sources import (
        _capture_creative_retained_sources,
        _Context,
    )
    from app.planning_documents.owner_review_policy import (
        OWNER_REVIEW_GENERATOR_VERSION,
        OWNER_REVIEW_POLICY_VERSION,
    )

    context = _Context(
        db,
        principal,
        document,
        now,
        required_pair=(OWNER_REVIEW_POLICY_VERSION, OWNER_REVIEW_GENERATOR_VERSION),
    )
    document = context.document
    with db.no_autoflush:
        context.guard()
        original = _owner_evidence(db, document)
        context.guard()
        result = _capture_creative_retained_sources(
            db, principal=principal, document=document, now=context.clock()
        )
        context.guard()
        if _owner_evidence(db, document).model_dump_json() != original.model_dump_json():
            raise ValueError("owner evidence changed during current read")
        context.guard()
        return result


def recheck_owner_review_retained_sources(
    db: Session,
    *,
    principal: "CustomerPrincipal",
    document: "PlanVersion",
    dependencies: "Sequence[PlanDependencyRow]",
    now: "datetime",
) -> None:
    from app.planning_documents.creative_retained_sources import (
        _Context,
        _recheck_creative_retained_sources,
    )
    from app.planning_documents.owner_review_policy import (
        OWNER_REVIEW_GENERATOR_VERSION,
        OWNER_REVIEW_POLICY_VERSION,
    )
    from app.planning_documents.selected_plan_history import (
        validate_selected_historical_dependencies,
    )

    context = _Context(
        db,
        principal,
        document,
        now,
        required_pair=(OWNER_REVIEW_POLICY_VERSION, OWNER_REVIEW_GENERATOR_VERSION),
    )
    document = context.document
    validate_selected_historical_dependencies(document, dependencies)
    context.clean()
    with db.no_autoflush:
        context.guard()
        original = _owner_evidence(db, document)
        context.guard()
        _recheck_creative_retained_sources(
            db,
            principal=principal,
            document=document,
            dependencies=dependencies,
            now=context.clock(),
        )
        context.guard()
        if _owner_evidence(db, document).model_dump_json() != original.model_dump_json():
            raise ValueError("owner evidence changed during current read")
        context.guard()


def validate_owner_review_plan_history(db: Session, document: "PlanVersion") -> None:
    from app.planning_documents.selected_plan_history import _validate_selected_plan_history

    document = _owner_document(document)
    root = db.get_transaction()
    if root is None or not root.is_active:
        raise ValueError("historical transaction required")
    connection = db.connection()
    transaction = connection.get_transaction()

    def guard() -> None:
        if (
            db.get_transaction() is not root
            or not root.is_active
            or db.in_nested_transaction()
            or db.new
            or db.dirty
            or db.deleted
            or connection.closed
            or db.connection() is not connection
            or transaction is None
            or not transaction.is_active
            or connection.get_transaction() is not transaction
            or connection.in_nested_transaction()
        ):
            raise ValueError("historical transaction changed")

    with db.no_autoflush:
        guard()
        _validate_selected_plan_history(db, document)
        guard()
        _owner_evidence(db, document)
        guard()
