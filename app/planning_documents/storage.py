"""Canonical planning row validation and bounded export, with no database side effects."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.planning_documents.common import MAX_DOCUMENT_BYTES, Frozen
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import CustomerDecision, ManualAssertion, ReadObservedStatus

PLANNING_TABLES = frozenset(
    {
        "planning_documents",
        "planning_input_revisions",
        "planning_document_versions",
        "planning_document_dependencies",
        "planning_document_events",
        "planning_document_requests",
    }
)
# Archive preflight conservatively estimates four UTF-8 bytes per stored character.
# One MiB decoded contract + bounded scalar/escaping overhead fits this planning-only cap.
MAX_PLANNING_ROW_BYTES = 5 * MAX_DOCUMENT_BYTES


def canonical(document: Frozen) -> str:
    checked = type(document).model_validate(document)
    value = json.dumps(
        checked.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    if len(value.encode()) > MAX_DOCUMENT_BYTES:
        raise ValueError("planning document exceeds bound")
    return value


def document_for_row(table: str, row: Mapping[str, Any]) -> Frozen:
    raw = row["canonical_json"]
    if not isinstance(raw, str) or len(raw.encode()) > MAX_DOCUMENT_BYTES:
        raise ValueError("planning canonical document exceeds bound")
    model: type[Frozen]
    if table == "planning_input_revisions":
        model = PlanInputRevision
    elif table == "planning_document_versions":
        model = PlanVersion
    elif table == "planning_document_events":
        event_models: dict[str, type[Frozen]] = {
            "decision": CustomerDecision,
            "assertion": ManualAssertion,
            "observation": ReadObservedStatus,
        }
        model = event_models[row["kind"]]
    else:
        raise ValueError("unknown planning document table")
    document = model.model_validate_json(raw)
    if canonical(document) != raw or document.digest() != row["digest"]:
        raise ValueError("planning canonical digest mismatch")
    expected: dict[str, Any]
    if isinstance(document, PlanInputRevision):
        expected = dict(
            workspace_id=document.workspace_id,
            plan_id=document.plan_id,
            revision=document.revision,
            goal_id=document.goal.goal_id,
            goal_revision=document.goal.revision,
            confirmed_preview_id=document.goal.confirmation_reference,
            definition_digest=document.goal.definition_digest,
            actor_id=document.created_by,
            created_at=document.created_at,
        )
    elif isinstance(document, PlanVersion):
        if any(ref.privacy_revision != row["privacy_revision"] for ref in document.evidence):
            raise ValueError("planning version privacy binding mismatch")
        expected = dict(
            workspace_id=document.inputs.workspace_id,
            plan_id=document.inputs.plan_id,
            version=document.version,
            input_revision=document.inputs.revision,
            parent_digest=document.parent_digest,
            generator_version=document.generator_version,
            policy_version=document.policy_version,
            actor_id=document.generated_by,
            generated_at=document.generated_at,
            valid_until=document.valid_until,
        )
    elif isinstance(document, (CustomerDecision, ManualAssertion, ReadObservedStatus)):
        expected = dict(
            workspace_id=document.workspace_id,
            plan_id=document.plan_id,
            version=document.version,
            event_id=document.event_id,
            action_key=document.action_key,
            action_digest=document.action_digest,
        )
        if isinstance(document, (CustomerDecision, ManualAssertion)):
            expected["actor_id"] = document.actor_id
            expected["recorded_at"] = document.recorded_at
        else:
            expected["recorded_at"] = document.observed_at
    else:
        raise ValueError("unsupported planning document")

    def normalized(value: Any) -> Any:
        return (
            value.replace(tzinfo=UTC)
            if isinstance(value, datetime) and value.tzinfo is None
            else value
        )

    if any(normalized(row[key]) != value for key, value in expected.items()):
        raise ValueError("planning row ownership/content mismatch")
    return document


def export_row(table: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from app.lifecycle.export_serializers import fields
    from app.lifecycle.inventory import scalar

    output = {key: scalar(row[key]) for key in fields(table) if key != "canonical_json"}
    if "canonical_json" in fields(table):
        output["document"] = document_for_row(table, row).model_dump(mode="json")
    if (
        len(json.dumps(output, ensure_ascii=False, allow_nan=False).encode())
        > MAX_PLANNING_ROW_BYTES
    ):
        raise ValueError("planning export row exceeds bound")
    return output
