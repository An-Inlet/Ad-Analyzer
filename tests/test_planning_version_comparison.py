from copy import deepcopy
from typing import Any

import pytest
from app.planning_documents.comparison import compare_versions
from app.planning_documents.documents import PlanVersion

from tests.test_planning_document_contracts import packet


def versions() -> tuple[PlanVersion, dict[str, Any]]:
    before = PlanVersion.model_validate(packet())
    after = before.model_dump(mode="json")
    after.update(version=2, parent_digest=before.digest())
    return before, after


def test_exact_field_changes_keep_previous_evidence_and_do_not_carry_decisions() -> None:
    before, after = versions()
    after["actions"][0]["rationale"] = "Corrected reported observations; verify selected event."
    after["evidence"][0]["source_revision"] = "v2"
    after["evidence"][0]["document_digest"] = "e" * 64
    result = compare_versions(before, PlanVersion.model_validate(after))
    by_path = {change.path: change for change in result.changes}
    key = before.actions[0].key
    assert by_path[("actions", key, "rationale")].before == before.actions[0].rationale
    assert by_path[("actions", key, "rationale")].after == after["actions"][0]["rationale"]
    assert ("evidence", "catalog", "source_revision") in by_path
    assert result.decisions_carried_over is False
    assert result.spending_authority == "none"
    assert result.advertising_writes_enabled is False
    assert result.omitted_changes == 0
    assert before == PlanVersion.model_validate(packet())


def test_list_content_and_null_presence_are_preserved() -> None:
    before, after = versions()
    after["inputs"]["product_offer"] = "<img src=x onerror=alert(1)>"
    after["actions"][0]["manual_steps"] = ["Second", "First"]
    result = compare_versions(before, PlanVersion.model_validate(after))
    by_path = {change.path: change for change in result.changes}
    offer = by_path[("inputs", "product_offer")]
    assert offer.before_present and offer.after_present and offer.before is None
    assert offer.after == after["inputs"]["product_offer"]
    assert by_path[("actions", before.actions[0].key, "manual_steps")].after == ["Second", "First"]


@pytest.mark.parametrize("mutation", ["plan", "workspace", "parent", "version", "unsafe"])
def test_foreign_non_successor_or_unsafe_document_is_rejected(mutation: str) -> None:
    before, after = versions()
    if mutation == "plan":
        after["inputs"]["plan_id"] = "e" * 32
    elif mutation == "workspace":
        # Deliberately unsafe copy must be reparsed, not accepted as a trusted model.
        current = PlanVersion.model_validate(after)
        bad_inputs = current.inputs.model_copy(update=dict(workspace_id=99))
        with pytest.raises(ValueError):
            compare_versions(before, current.model_copy(update=dict(inputs=bad_inputs)))
        return
    elif mutation == "parent":
        after["parent_digest"] = "f" * 64
    elif mutation == "version":
        after["version"] = 3
    else:
        current = PlanVersion.model_validate(after)
        with pytest.raises(ValueError):
            compare_versions(
                before, current.model_copy(update=dict(advertising_writes_enabled=True))
            )
        return
    with pytest.raises(ValueError):
        compare_versions(before, PlanVersion.model_validate(after))


def test_empty_content_change_does_not_invent_outcome_explanation() -> None:
    before, after = versions()
    result = compare_versions(before, PlanVersion.model_validate(deepcopy(after)))
    assert result.changes == ()
    assert result.semantics == "document_changes_not_causal_attribution"


def test_reordered_identity_collections_are_not_false_changes() -> None:
    data = packet()
    data["actions"].append({**data["actions"][0], "key": "second", "priority": 2})
    before = PlanVersion.model_validate(data)
    after = before.model_dump(mode="json")
    after.update(version=2, parent_digest=before.digest())
    after["actions"].reverse()
    assert compare_versions(before, PlanVersion.model_validate(after)).changes == ()


def test_change_limit_explicitly_reports_omissions() -> None:
    data = packet()
    template = data["actions"][0]
    data["actions"] = [{**template, "key": f"action_{i:03}", "priority": i + 1} for i in range(100)]
    before = PlanVersion.model_validate(data)
    after = before.model_dump(mode="json")
    after.update(version=2, parent_digest=before.digest())
    for action in after["actions"]:
        action.update(
            title="New",
            rationale="New rationale",
            manual_steps=["New step"],
            expected_effect="Still unknown",
            limitations=["New limitation"],
            measurement_criterion="New criterion",
        )
    result = compare_versions(before, PlanVersion.model_validate(after))
    assert len(result.changes) == 500
    assert result.omitted_changes == 100
    assert all(change.path[0] == "actions" for change in result.changes)
