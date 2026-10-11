"""Selector-only foundation: no v4 capability or selected-evidence qualification."""

import hashlib
import json
from typing import Any

import pytest
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.documents import PlanVersion
from app.planning_documents.input_resolution import resolve
from app.planning_documents.policy_capabilities import reporting_capability
from app.planning_documents.requests import CreatePlan, CustomerInputs
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
    SelectedCaptureSelectorV1,
    reject_legacy_selected,
)
from pydantic import ValidationError

from tests.test_planning_document_contracts import packet
from tests.test_planning_documents_api import create_body

# Recorded from untouched 6b6c272 before adding the optional field. Includes nested
# Python serialization, model JSON bytes, canonical JSON, and original digest.
GOLDEN = {
    "plan": (
        "dec8af71f4a6642d3cefa84b6dd156e9eedb29eea3c96c61baac2d74f015b1bd",
        "13b41999f4f9ebec783f68bf1bf3d6fbd4507ce609748eb4ec906bb3d731f40f",
        "74242ff21ce3ad342c737fd6f53847d1b00dc253d0fe4643372584d6e50cb822",
        "5e54c4f1bfd8798bce8c38b6c070d38d76ed2a337a25a08217ea4c7a92d40042",
    ),
    "input": (
        "648a516296e87fb48e81503f24be82b1741d2921c245e76a9d9b5c4c38734a6b",
        "03e8c208432da64a6347b03ea8ba9eae78d3deaf00cabd4c88a2523b8f6e15a4",
        "ea013dabb8b48e4014ca97557ef1dc43d6b3ac39e566d7a53ef9cc459de16247",
        "5010a73ea8cb98febcd856300c757e9a6e7d36087db63b6f363b0d3cf21766c3",
    ),
    "request": (
        "dca0569fc76235f947b982fdeb8fbb2e6f7a6636d5c36a301f2fa1b6d06304c1",
        "7faeb4599637967f13b1a3c3069ac353a509bef073c7dc0219e1fb89e72aa936",
        "75b144d51d7a5a4d6a1c096f532da0dfe91795f66477165fe8c64278c50ecdf6",
        "b7ce14c9e80225038121301b02e08a090ccdb07b285140e9a60b51c2bc10488d",
    ),
}


def models() -> tuple[PlanVersion, PlanInputRevision, CreatePlan]:
    plan = PlanVersion.model_validate(packet())
    return plan, plan.inputs, CreatePlan.model_validate(create_body(plan.inputs))


def test_legacy_nested_bytes_and_digests_unchanged() -> None:
    for name, value in zip(GOLDEN, models(), strict=True):
        actual = (
            value.digest(),
            hashlib.sha256(repr(value.model_dump(mode="python")).encode()).hexdigest(),
            hashlib.sha256(value.model_dump_json().encode()).hexdigest(),
            hashlib.sha256(
                json.dumps(
                    value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
        )
        assert actual == GOLDEN[name]
        assert "selected_reporting" not in value.model_dump_json()
        assert type(value).model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize(
    "items", [(), (SelectedCaptureSelectorV1(account_id=1, capture_id="f" * 32),)]
)
def test_explicit_selector_preserved_nested_and_changes_commitments(items: Any) -> None:
    plan, inputs, request = models()
    changed = PlanInputRevision.model_validate(
        inputs.model_copy(update={"selected_reporting": items})
    )
    intent = CustomerInputs.model_validate(
        request.inputs.model_copy(update={"selected_reporting": items})
    )
    for value in (
        changed,
        intent,
        plan.model_copy(update={"inputs": changed}),
        request.model_copy(update={"inputs": intent}),
    ):
        assert '"selected_reporting":' in value.model_dump_json()
        assert type(value).model_validate_json(value.model_dump_json()) == value
    assert changed.digest() != inputs.digest()
    assert intent.digest() != request.inputs.digest()
    assert resolve(changed, intent, ()).selected_reporting == items
    with pytest.raises(ValueError, match="prepared selected"):
        resolve(inputs, intent, ())


@pytest.mark.parametrize("kind", ["foreign", "duplicate", "overflow", "bool", "unsafe"])
def test_invalid_selectors_rejected_even_unsafe_copy(kind: str) -> None:
    _, inputs, request = models()
    selector = SelectedCaptureSelectorV1(account_id=1, capture_id="f" * 32)
    items: Any = (selector,)
    if kind == "foreign":
        items = (selector.model_copy(update={"account_id": 2}),)
    elif kind == "duplicate":
        items = (selector, selector)
    elif kind == "overflow":
        items = (selector,) * 21
    elif kind == "bool":
        items = (selector.model_copy(update={"account_id": True}),)
    else:
        items = (selector.model_copy(update={"capture_id": "bad"}),)
    for value in (inputs, request.inputs):
        with pytest.raises(ValidationError):
            value.model_copy(update={"selected_reporting": items}).digest()


@pytest.mark.parametrize("version", [1, 2, 3])
def test_legacy_rejects_even_explicit_empty_and_v4_still_unavailable(version: int) -> None:
    with pytest.raises(ValueError, match="selected reporting"):
        reject_legacy_selected(
            (), f"inlet.descriptive-review.v{version}", f"inlet.descriptive-planning.v{version}"
        )
    reject_legacy_selected(
        None, f"inlet.descriptive-review.v{version}", f"inlet.descriptive-planning.v{version}"
    )
    with pytest.raises(ValueError, match="unknown"):
        reporting_capability(SELECTED_POLICY_VERSION, SELECTED_GENERATOR_VERSION)


def test_direct_legacy_composers_reject_selectors() -> None:
    from datetime import timedelta

    from app.planning_documents.composer import PlanCompositionUnavailable
    from app.planning_documents.window_composer import WindowPlanComposer

    from tests.test_planning_composer import compose, fixture
    from tests.test_window_evidence_contract import policy, ready

    inputs, bundle, legacy = fixture()
    with pytest.raises(PlanCompositionUnavailable, match="selected reporting"):
        compose(inputs.model_copy(update={"selected_reporting": ()}), bundle, legacy)
    ticket, windows = ready()
    ticket = ticket.model_copy(
        update={"inputs": ticket.inputs.model_copy(update={"selected_reporting": ()})}
    )
    with pytest.raises(PlanCompositionUnavailable, match="selected reporting"):
        WindowPlanComposer().compose(
            ticket=ticket,
            evidence=windows,
            policy=policy(),
            generated_at=windows.collected_at + timedelta(seconds=1),
        )
