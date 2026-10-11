"""Historical v4/v5 integrity only; callers retain current viewer/lifecycle authority.

No current source, selection head, session, or observation TTL is consulted here.
Opaque original aggregate/map commitments are bound, not reconstructed as facts.
This port does not register v4 or activate archive delivery.
"""

from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaign_performance.selected_contracts import selected_capture_digest
from app.campaign_performance.selected_storage import historical_capture
from app.planning_documents.common import MAX_ACCOUNTS, MAX_EVIDENCE
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow, PlanVersionRow
from app.planning_documents.retained_sources import RetainedSourceWitness, _row
from app.planning_documents.selected_plan_contracts import SelectedPlanPinV1
from app.planning_documents.selected_policy_contract import selected_policy_contract
from app.planning_documents.selected_traffic_reader import validate_historical_raw_range_traffic
from app.planning_documents.storage import document_for_row
from app.shopify.security import utc


def validate_selected_historical_pin(db: Session, pin: SelectedPlanPinV1) -> None:
    """Validate the original retained graph, without requiring it to remain current."""
    pin = SelectedPlanPinV1.model_validate(pin)
    capture = historical_capture(
        db, pin.account.workspace_id, pin.account.account_id, pin.capture_id
    )
    request = capture.request
    if (
        request.aggregate != pin.aggregate
        or request.selection.selection_id != pin.selection_id
        or request.selection_digest != pin.selection_digest
        or request.capture_id != pin.capture_id
        or capture.request_digest != pin.request_digest
        or selected_capture_digest(capture) != pin.capture_digest
    ):
        raise ValueError("selected historical capture commitment mismatch")


def validate_selected_historical_dependencies(
    document: PlanVersion, dependencies: Sequence[PlanDependencyRow]
) -> tuple[SelectedPlanPinV1, ...]:
    """Validate the complete saved dependency set; returned pins still need SQL checks."""
    document = PlanVersion.model_validate(document)
    contract = selected_policy_contract(document.policy_version, document.generator_version)
    proof = document.selected_reporting_proof
    if proof is None or len(dependencies) > MAX_EVIDENCE + MAX_ACCOUNTS + 1 + int(
        contract.requires_creative
    ):
        raise ValueError("selected historical proof required")
    rows = {row.evidence_key: _row(row) for row in dependencies}
    if len(rows) != len(dependencies):
        raise ValueError("duplicate historical dependency")
    if contract.requires_creative:
        from app.planning_documents.creative_history import _validate_creative_local_dependency

        _validate_creative_local_dependency(document, dependencies)
        rows.pop("local:creative:basis")
    common: dict[str, Any] = dict(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=document.version,
    )
    for ref in document.evidence:
        expected = dict(
            **common,
            evidence_key=ref.key,
            account_id=ref.account.account_id if ref.account else None,
            connection_id=ref.account.connection_id if ref.account else None,
            store_id=document.inputs.goal.definition.store_id
            if ref.kind == "shopify_measurement"
            else None,
            kind=ref.kind,
            source_binding_digest=ref.source_binding_digest,
            document_digest=ref.document_digest,
            source_revision=ref.source_revision,
            observed_at=utc(ref.observed_at),
            expires_at=utc(ref.expires_at),
            privacy_revision=ref.privacy_revision,
        )
        if ref.key.startswith("local:") or rows.pop(ref.key, None) != expected:
            raise ValueError("historical evidence dependency mismatch")
    privacy = document.evidence[0].privacy_revision
    proof.assert_inputs(document.inputs, privacy)
    for account in proof.accounts:
        fence = account.source_fence
        key = f"local:reporting:{fence.account.account_id}"
        raw = rows.pop(key, None)
        if raw is None:
            raise ValueError("historical selected dependency missing")
        # The witness's observation time is assigned by the original locked save.
        expected = dict(
            **common,
            evidence_key=key,
            account_id=fence.account.account_id,
            connection_id=fence.account.connection_id,
            store_id=None,
            kind="local_reporting_v3",
            source_binding_digest=fence.source_binding_digest,
            document_digest=account.state_digest(),
            source_revision=fence.source_revision,
            observed_at=raw["observed_at"],
            expires_at=utc(document.valid_until),
            privacy_revision=privacy,
        )
        if (
            raw != expected
            or not document.generated_at <= raw["observed_at"] < document.valid_until
        ):
            raise ValueError("historical selected dependency mismatch")
    key = f"local:commerce:{document.inputs.goal.definition.store_id}"
    raw = rows.pop(key, None)
    if raw is None or rows:
        raise ValueError("complete historical local dependencies required")
    commerce = RetainedSourceWitness.model_validate(raw)
    if (
        commerce.kind != "local_commerce_v1"
        or any(raw[name] != value for name, value in common.items())
        or commerce.evidence_key != key
        or commerce.store_id != document.inputs.goal.definition.store_id
        or commerce.privacy_revision != privacy
        or commerce.expires_at != document.valid_until
        or not document.generated_at <= commerce.observed_at < document.valid_until
    ):
        raise ValueError("historical commerce dependency mismatch")
    return tuple(item.capture_pin for item in proof.accounts if item.capture_pin is not None)


def _validate_selected_plan_history(db: Session, document: PlanVersion) -> None:
    """Read complete retained SQL under caller-owned viewer/lifecycle transaction."""
    document = PlanVersion.model_validate(document)
    transaction = db.get_transaction()
    if (
        transaction is None
        or not transaction.is_active
        or db.in_nested_transaction()
        or db.new
        or db.dirty
        or db.deleted
    ):
        raise ValueError("clean historical read transaction required")
    row = (
        db.execute(
            select(PlanVersionRow.__table__).where(
                PlanVersionRow.workspace_id == document.inputs.workspace_id,
                PlanVersionRow.plan_id == document.inputs.plan_id,
                PlanVersionRow.version == document.version,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or document_for_row("planning_document_versions", dict(row)) != document:
        raise ValueError("exact retained selected plan required")
    contract = selected_policy_contract(document.policy_version, document.generator_version)
    dependencies = tuple(
        db.scalars(
            select(PlanDependencyRow)
            .where(
                PlanDependencyRow.workspace_id == document.inputs.workspace_id,
                PlanDependencyRow.plan_id == document.inputs.plan_id,
                PlanDependencyRow.version == document.version,
            )
            .limit(MAX_EVIDENCE + MAX_ACCOUNTS + 2 + int(contract.requires_creative))
            .execution_options(populate_existing=True)
        )
    )
    for pin in validate_selected_historical_dependencies(document, dependencies):
        validate_selected_historical_pin(db, pin)
    proof = document.selected_reporting_proof
    assert proof is not None  # Exact row and full dependency validation above requires it.
    for account in proof.accounts:
        if account.traffic_pin is not None:
            try:
                validate_historical_raw_range_traffic(db, expected_pin=account.traffic_pin)
            except HTTPException as error:
                if error.status_code != 409:
                    raise
                raise ValueError("historical traffic integrity unavailable") from None
    if db.get_transaction() is not transaction or not transaction.is_active:
        raise ValueError("historical read transaction changed")


def validate_selected_plan_history(db: Session, document: PlanVersion) -> None:
    document = PlanVersion.model_validate(document)
    contract = selected_policy_contract(document.policy_version, document.generator_version)
    if contract.requires_owner_review:
        from app.planning_documents.google_budget_owner_retained import (
            validate_owner_review_plan_history,
        )

        validate_owner_review_plan_history(db, document)
    else:
        _validate_selected_plan_history(db, document)
