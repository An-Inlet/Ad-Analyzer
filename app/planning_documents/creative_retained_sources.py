"""Genuine v5 retained currentness orchestration; no generation capability."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents.creative_history import creative_local_witness
from app.planning_documents.creative_inputs import (
    CREATIVE_GENERATOR_VERSION,
    CREATIVE_POLICY_VERSION,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.retained_sources import (
    RetainedSourcesChanged,
    RetainedSourceWitness,
    _goal,
    _guard,
    _row,
)
from app.planning_documents.selected_plan_history import validate_selected_historical_dependencies
from app.planning_documents.selected_plan_witnesses import capture_selected_reporting_sources
from app.shopify.security import utc


class _Context:
    def __init__(
        self, db: Session, principal: CustomerPrincipal, document: PlanVersion, now: datetime
    ) -> None:
        self.document = PlanVersion.model_validate(document)
        if (
            (document.policy_version, document.generator_version)
            != (
                CREATIVE_POLICY_VERSION,
                CREATIVE_GENERATOR_VERSION,
            )
            or type(now) is not datetime
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise RetainedSourcesChanged("proof_unavailable")
        self.db, self.principal, self.now = db, principal, now.astimezone(UTC)
        self.root = db.get_transaction()
        if (
            self.root is None
            or not self.root.is_active
            or db.in_nested_transaction()
            or db.new
            or db.dirty
            or db.deleted
        ):
            raise RetainedSourcesChanged("source_changed")
        self.connection = db.connection()
        self.transaction = self.connection.get_transaction()
        self.clean()

    def clean(self) -> None:
        if (
            self.root is None
            or self.db.get_transaction() is not self.root
            or not self.root.is_active
            or self.connection.closed
            or self.db.connection() is not self.connection
            or self.transaction is None
            or not self.transaction.is_active
            or self.connection.get_transaction() is not self.transaction
            or self.db.in_nested_transaction()
            or self.connection.in_nested_transaction()
            or self.db.new
            or self.db.dirty
            or self.db.deleted
        ):
            raise RetainedSourcesChanged("source_changed")

    def clock(self) -> datetime:
        self.clean()
        now = max(self.now, utc(database_utc_now(self.db)))
        self.clean()  # DB-time sampling may itself wait/change the transaction.
        if not utc(self.document.generated_at) <= now < utc(self.document.valid_until):
            raise RetainedSourcesChanged("source_changed")
        return now

    def guard(self) -> None:
        self.clean()
        document = self.document
        _guard(self.db, self.principal, document.inputs.workspace_id, self.principal.user.id)
        self.clean()
        _goal(self.db, document)
        self.clean()
        privacy = workspace_export_revision(self.db, document.inputs.workspace_id)
        self.clean()
        if any(ref.privacy_revision != privacy for ref in document.evidence):
            raise RetainedSourcesChanged("source_changed")
        self.clock()
        _guard(self.db, self.principal, document.inputs.workspace_id, self.principal.user.id)
        self.clean()
        self.clock()


def capture_creative_retained_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    document: PlanVersion,
    now: datetime,
) -> tuple[RetainedSourceWitness, ...]:
    # Imported only after its separately reviewed frozen implementation is available.
    from app.planning_documents.creative_currentness import capture_creative_retained_source

    context = _Context(db, principal, document, now)
    document = context.document
    with db.no_autoflush:
        context.guard()
        reporting = capture_selected_reporting_sources(
            db, principal=principal, document=document, now=context.clock()
        )
        context.clean()
        creative = capture_creative_retained_source(
            db, principal=principal, document=document, now=context.clock()
        )
        context.clean()
        result = tuple(RetainedSourceWitness.model_validate(w) for w in (*reporting, creative))
        keys = {f"local:reporting:{a.account_id}" for a in document.inputs.accounts}
        keys.update(
            {f"local:commerce:{document.inputs.goal.definition.store_id}", "local:creative:basis"}
        )
        if len(result) != len(keys) or {w.evidence_key for w in result} != keys:
            raise RetainedSourcesChanged("proof_unavailable")
        if creative != creative_local_witness(document):
            raise RetainedSourcesChanged("source_changed")
        for witness in result:
            if (
                witness.workspace_id != document.inputs.workspace_id
                or witness.plan_id != document.inputs.plan_id
                or witness.version != document.version
                or witness.privacy_revision != document.evidence[0].privacy_revision
                or utc(witness.expires_at) != utc(document.valid_until)
            ):
                raise RetainedSourcesChanged("source_changed")
        context.guard()
        return result


def recheck_creative_retained_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    document: PlanVersion,
    dependencies: Sequence[PlanDependencyRow],
    now: datetime,
) -> None:
    context = _Context(db, principal, document, now)
    document = context.document
    validate_selected_historical_dependencies(document, dependencies)
    context.clean()
    saved = {row.evidence_key: _row(row) for row in dependencies}
    with db.no_autoflush:
        current = capture_creative_retained_sources(
            db, principal=principal, document=document, now=context.clock()
        )
        context.clean()
        for witness in current:
            actual = witness.model_dump()
            original = saved[witness.evidence_key].copy()
            actual["observed_at"] = utc(actual["observed_at"])
            actual["expires_at"] = utc(actual["expires_at"])
            if witness.kind != "local_creative_basis_v1":
                observed = original.pop("observed_at")
                if not utc(document.generated_at) <= observed <= context.clock():
                    raise RetainedSourcesChanged("proof_unavailable")
                actual.pop("observed_at")
            if actual != original:
                raise RetainedSourcesChanged("source_changed")
        context.guard()
