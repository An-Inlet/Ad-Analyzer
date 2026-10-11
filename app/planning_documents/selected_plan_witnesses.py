"""Reserved v4 local witnesses. No capability registration or service dispatch."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.retained_sources import (
    RetainedSourcesChanged,
    RetainedSourceWitness,
    _goal,
    _guard,
    _row,
    commerce_witness,
)
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
)
from app.planning_documents.selected_plan_history import validate_selected_historical_dependencies
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1
from app.planning_documents.selected_plan_retained import capture_selected_reporting_pin
from app.planning_documents.selected_policy_contract import selected_policy_contract
from app.shopify.security import utc


def capture_selected_retained_sources(
    db: Session, *, principal: CustomerPrincipal, document: PlanVersion, now: datetime
) -> tuple[RetainedSourceWitness, ...]:
    """Unchanged exact-v4 entrypoint; the shared subset is not complete v5 proof."""
    document = PlanVersion.model_validate(document)
    if (document.policy_version, document.generator_version) != (
        SELECTED_POLICY_VERSION,
        SELECTED_GENERATOR_VERSION,
    ):
        raise RetainedSourcesChanged("proof_unavailable")
    return capture_selected_reporting_sources(db, principal=principal, document=document, now=now)


def capture_selected_reporting_sources(
    db: Session, *, principal: CustomerPrincipal, document: PlanVersion, now: datetime
) -> tuple[RetainedSourceWitness, ...]:
    """Compare saved proof with actual SQL before locked persistence/current use.

    Caller owns original identity refresh/final age, workspace lock and transaction.
    A viewer may inspect currentness; this helper grants no write authority.
    """
    document = PlanVersion.model_validate(document)
    proof = document.selected_reporting_proof
    selected_policy_contract(document.policy_version, document.generator_version)
    if proof is None or document.inputs.selected_reporting is None:
        raise RetainedSourcesChanged("proof_unavailable")
    wid = document.inputs.workspace_id
    root = db.get_transaction()

    def guard() -> int:
        if (
            root is None
            or db.get_transaction() is not root
            or not root.is_active
            or db.in_nested_transaction()
            or db.new
            or db.dirty
            or db.deleted
        ):
            raise RetainedSourcesChanged("source_changed")
        _guard(db, principal, wid, principal.user.id)
        current = max(utc(now), database_utc_now(db))
        if not document.generated_at <= current < document.valid_until:
            raise RetainedSourcesChanged("source_changed")
        return workspace_export_revision(db, wid)

    privacy = guard()
    _goal(db, document)
    if any(
        ref.privacy_revision != privacy or ref.key.startswith("local:") for ref in document.evidence
    ):
        raise RetainedSourcesChanged("source_changed")
    proof.assert_inputs(document.inputs, privacy)
    selectors = {s.account_id: s for s in document.inputs.selected_reporting}

    def current_proof() -> SelectedRetainedProofV1:
        return SelectedRetainedProofV1(
            accounts=tuple(
                capture_selected_reporting_pin(
                    db, principal, account, privacy, selectors.get(account.account_id), now
                )
                for account in sorted(document.inputs.accounts, key=lambda a: a.account_id)
            )
        )

    if current_proof() != proof:
        raise RetainedSourcesChanged("source_changed")
    common: dict[str, Any] = dict(
        workspace_id=wid,
        plan_id=document.inputs.plan_id,
        version=document.version,
        observed_at=max(utc(now), database_utc_now(db)),
        expires_at=document.valid_until,
        privacy_revision=privacy,
    )
    values = [
        RetainedSourceWitness(
            **common,
            evidence_key=f"local:reporting:{account.source_fence.account.account_id}",
            account_id=account.source_fence.account.account_id,
            connection_id=account.source_fence.account.connection_id,
            store_id=None,
            kind="local_reporting_v3",
            source_binding_digest=account.source_fence.source_binding_digest,
            document_digest=account.state_digest(),
            source_revision=account.source_fence.source_revision,
        )
        for account in proof.accounts
    ]
    values.append(
        commerce_witness(db, principal=principal, document=document, common=common, now=now)
    )
    if current_proof() != proof or guard() != privacy:
        raise RetainedSourcesChanged("source_changed")
    return tuple(values)


def recheck_selected_retained_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    document: PlanVersion,
    dependencies: Sequence[PlanDependencyRow],
    now: datetime,
) -> None:
    """Require the exact saved set and revalidate every current SQL witness."""
    validate_selected_historical_dependencies(document, dependencies)
    saved = {row.evidence_key: _row(row) for row in dependencies}
    current = capture_selected_retained_sources(db, principal=principal, document=document, now=now)
    for witness in current:
        actual = witness.model_dump()
        original = saved[witness.evidence_key].copy()
        if original.pop("observed_at") > max(utc(now), database_utc_now(db)):
            raise RetainedSourcesChanged("proof_unavailable")
        actual.pop("observed_at")
        if actual != original:
            raise RetainedSourcesChanged("source_changed")
