"""Stable mutation receipts expose derived review hashes, never mutable head state."""

import pytest
from app.planning_documents.documents import PlanVersion
from app.planning_documents.responses import InputResult, VersionResult
from pydantic import ValidationError

from tests.test_planning_document_contracts import packet


def test_stable_results_and_server_derived_review_hashes() -> None:
    document = PlanVersion.model_validate(packet())
    result = VersionResult(
        plan_id=document.inputs.plan_id, version=document.version, document=document
    )
    body = result.model_dump(mode="json")
    assert body["document_digest"] == document.digest()
    assert body["action_digests"] == {a.key: a.digest() for a in document.actions}
    assert "freshness" not in body and "event_sequence" not in body
    assert body["advertising_writes_enabled"] is False
    assert body["spending_authority"] == "none"
    inputs = InputResult(
        plan_id=document.inputs.plan_id,
        input_revision=document.inputs.revision,
        inputs=document.inputs,
    )
    assert "version" not in inputs.model_dump()
    with pytest.raises(ValidationError):
        VersionResult.model_validate({**body, "document_digest": "a" * 64})
    with pytest.raises(ValidationError):
        VersionResult(plan_id="f" * 32, version=document.version, document=document)
    with pytest.raises(ValidationError):
        InputResult(plan_id=document.inputs.plan_id, input_revision=2, inputs=document.inputs)


def test_digest_projection_revalidates_unsafe_nested_copy() -> None:
    document = PlanVersion.model_validate(packet())
    result = VersionResult(
        plan_id=document.inputs.plan_id, version=document.version, document=document
    ).model_copy(update={"document": document.model_copy(update={"spending_authority": "enabled"})})
    with pytest.raises(ValidationError):
        _ = result.document_digest
    with pytest.raises(ValidationError):
        _ = result.action_digests
