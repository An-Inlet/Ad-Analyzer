"""Reserved creative inputs never change legacy bytes or activate generation."""

from datetime import timedelta
from typing import Any

import pytest
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.creative_basis import (
    CreativeInputV1,
    CustomerListPriceV1,
    CustomerProductV1,
)
from app.planning_documents.creative_inputs import validate_creative_policy
from app.planning_documents.input_resolution import resolve
from app.planning_documents.policy_capabilities import reporting_capability
from app.planning_documents.requests import CreatePlan, CustomerInputs
from pydantic import ValidationError

from tests.test_selected_planning_inputs import models


@pytest.mark.parametrize("empty", [False, True])
def test_typed_input_is_retained_and_committed(empty: bool) -> None:
    _, old, request = models()
    creative = CreativeInputV1(
        product=None if empty else CustomerProductV1(name="Reusable travel mug")
    )
    inputs = PlanInputRevision.model_validate(old.model_copy(update={"creative": creative}))
    intent = CustomerInputs.model_validate(request.inputs.model_copy(update={"creative": creative}))
    assert inputs.digest() != old.digest() and intent.digest() != request.inputs.digest()
    assert '"creative":' in inputs.model_dump_json()
    assert resolve(inputs, intent, ()).creative == creative
    with pytest.raises(ValueError, match="prepared creative"):
        resolve(old, intent, ())
    for obj in (inputs, intent, CreatePlan(inputs=intent, request_key=request.request_key)):
        assert type(obj).model_validate_json(obj.model_dump_json()) == obj


def test_explicit_null_preserves_nested_bytes_and_digests() -> None:
    plan, inputs, request = models()
    changed = PlanInputRevision.model_validate(inputs.model_copy(update={"creative": None}))
    nested = plan.model_copy(update={"inputs": changed})
    intent = request.inputs.model_copy(update={"creative": None})
    updated = request.model_copy(update={"inputs": intent})
    for old, new in ((inputs, changed), (plan, nested), (request, updated)):
        assert old.model_dump(mode="python") == new.model_dump(mode="python")
        assert old.model_dump_json() == new.model_dump_json()
        assert old.digest() == new.digest()
        assert '"creative":' not in new.model_dump_json()


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_legacy_document_and_gate_reject_even_empty(version: int) -> None:
    plan, inputs, _ = models()
    creative = CreativeInputV1()
    policy, generator = (
        f"inlet.descriptive-review.v{version}",
        f"inlet.descriptive-planning.v{version}",
    )
    with pytest.raises(ValueError, match="typed creative"):
        validate_creative_policy(creative, policy, generator)
    validate_creative_policy(None, policy, generator)
    poisoned = plan.model_copy(
        update={
            "inputs": inputs.model_copy(update={"creative": creative}),
            "policy_version": policy,
            "generator_version": generator,
        }
    )
    with pytest.raises(ValidationError, match="typed creative"):
        poisoned.digest()


@pytest.mark.parametrize("bad", ["currency", "copied_name", "copied_price"])
def test_direct_and_copied_inputs_revalidate(bad: str) -> None:
    _, inputs, request = models()
    product = CustomerProductV1(name="Mug")
    if bad == "currency":
        product = product.model_copy(
            update={"list_price": CustomerListPriceV1(micros=25, currency="EUR")}
        )
    elif bad == "copied_name":
        product = product.model_copy(update={"name": False})
    else:
        product = product.model_copy(
            update={
                "list_price": CustomerListPriceV1(micros=25, currency="USD").model_copy(
                    update={"micros": True}
                )
            }
        )
    creative = CreativeInputV1().model_copy(update={"product": product})
    with pytest.raises(ValidationError):
        inputs.model_copy(update={"creative": creative}).digest()
    if bad != "currency":
        with pytest.raises(ValidationError):
            request.inputs.model_copy(update={"creative": creative}).digest()


def test_exact_v5_reservation_is_not_capability_registration() -> None:
    pair = ("inlet.descriptive-review.v5", "inlet.descriptive-planning.v5")
    validate_creative_policy(CreativeInputV1(), *pair)
    with pytest.raises(ValueError, match="explicit typed"):
        validate_creative_policy(None, *pair)
    for invalid in ((pair[0], "inlet.descriptive-planning.v4"), ("unknown", pair[1])):
        with pytest.raises(ValueError):
            validate_creative_policy(CreativeInputV1(), *invalid)
    assert reporting_capability(*pair).mode == "creative_selected_requested_window"


def test_reserved_v5_cannot_parse_an_unproved_creative_document() -> None:
    plan, inputs, _ = models()
    reserved = plan.model_copy(
        update={
            "inputs": inputs.model_copy(update={"creative": CreativeInputV1()}),
            "policy_version": "inlet.descriptive-review.v5",
            "generator_version": "inlet.descriptive-planning.v5",
        }
    )
    with pytest.raises(
        ValidationError, match="complete creative document proof and composition required"
    ):
        reserved.digest()


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_every_legacy_composer_refuses_typed_inputs(version: int) -> None:
    from app.planning_documents.composer import PlanCompositionUnavailable
    from app.planning_documents.selected_composer import SelectedPlanComposer
    from app.planning_documents.window_composer import WindowPlanComposer

    from tests.test_planning_composer import compose, fixture
    from tests.test_selected_paired_composer import ready as selected_ready
    from tests.test_window_evidence_contract import policy, ready

    creative = CreativeInputV1()
    with pytest.raises(PlanCompositionUnavailable, match="typed creative"):
        if version <= 2:
            inputs, bundle, _ = fixture()
            compose(inputs.model_copy(update={"creative": creative}), bundle, policy(version))
        else:
            ticket: Any
            evidence: Any
            if version == 3:
                ticket, evidence = ready()
            else:
                ticket, evidence, _ = selected_ready()
            ticket = ticket.model_copy(
                update={"inputs": ticket.inputs.model_copy(update={"creative": creative})}
            )
            composer: Any = WindowPlanComposer() if version == 3 else SelectedPlanComposer()
            collected = evidence.collected_at if version == 3 else evidence.selected.collected_at
            composer.compose(
                ticket=ticket,
                evidence=evidence,
                policy=policy(version),
                generated_at=collected + timedelta(seconds=1),
            )
