"""Omitted legacy bytes and unsupported-generation boundaries remain exact."""

from typing import Any

import pytest
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.planning_documents.creative_plan_composer import CreativePlanComposer
from app.planning_documents.documents import PlanVersion
from app.planning_documents.google_budget_generation_guard import (
    validate_google_budget_input_policy,
)
from app.planning_documents.google_budget_input_resolution import resolve_google_daily_budget_inputs
from app.planning_documents.selected_composer import SelectedPlanComposer
from app.planning_documents.window_composer import WindowPlanComposer

from tests.test_creative_plan_composer import compose, ready
from tests.test_google_budget_input_bindings import setup
from tests.test_planning_composer import compose as legacy_compose
from tests.test_planning_composer import fixture as legacy_fixture
from tests.test_selected_planning_inputs import models


def test_none_omitted_and_empty_preserved_in_nested_inputs() -> None:
    plan, inputs, request = models()
    for model in (plan, inputs, request):
        assert "google_daily_budget_intents" not in model.model_dump_json()
    body = request.model_dump(mode="python")
    body["inputs"]["google_daily_budget_intents"] = ()
    changed = type(request).model_validate(body)
    assert changed.inputs.google_daily_budget_intents == ()
    assert '"google_daily_budget_intents":[]' in changed.model_dump_json()
    assert changed.digest() != request.digest()


@pytest.mark.parametrize(
    "boundary",
    [
        "legacy",
        "window",
        "window_internal",
        "selected",
        "selected_internal",
        "creative",
        "document",
    ],
)
def test_every_generation_boundary_refuses_explicit_empty(boundary: str) -> None:
    if boundary == "legacy":
        inputs, evidence, policy = legacy_fixture()
        inputs = inputs.model_copy(update={"google_daily_budget_intents": ()})
        with pytest.raises(ValueError, match="owner hypotheses"):
            legacy_compose(inputs, evidence, policy)
        return
    values = ready("meta")
    ticket, evidence, policy, now = values
    inputs = ticket.inputs.model_copy(update={"google_daily_budget_intents": ()})
    ticket = ticket.model_copy(update={"inputs": inputs})
    with pytest.raises(ValueError, match="owner hypotheses"):
        if boundary == "document":
            doc = compose(values)
            PlanVersion.model_validate(doc.model_copy(update={"inputs": inputs}))
        elif boundary == "creative":
            CreativePlanComposer().compose(
                ticket=ticket, evidence=evidence, policy=policy, generated_at=now
            )
        elif boundary == "selected":
            SelectedPlanComposer().compose(
                ticket=ticket, evidence=evidence.reporting, policy=policy, generated_at=now
            )
        elif boundary == "selected_internal":
            SelectedPlanComposer()._compose(ticket, evidence.reporting, policy, now)
        elif boundary == "window":
            WindowPlanComposer().compose(
                ticket=ticket, evidence=evidence.reporting, policy=policy, generated_at=now
            )
        else:
            WindowPlanComposer()._compose(ticket, evidence.reporting, policy, now)


@pytest.mark.parametrize("version", ["v1", "v2", "v3", "v4"])
def test_prior_policy_rejects_empty_owner_inputs(version: str) -> None:
    with pytest.raises(ValueError, match="private V5"):
        validate_google_budget_input_policy(
            (), f"inlet.descriptive-review.{version}", f"inlet.descriptive-planning.{version}"
        )
    validate_google_budget_input_policy(None, "old", "old")


@pytest.mark.parametrize(
    "field,value", [("advertising_writes_enabled", 0), ("platform", b"google_ads")]
)
def test_private_resolver_rejects_copied_raw_catalog_before_coercion(
    field: str, value: Any
) -> None:
    original = setup()
    cat = original["catalogs"][0]
    native = cat.catalog.native_observation.model_copy(update={field: value})
    corrupt = cat.model_copy(
        update={"catalog": cat.catalog.model_copy(update={"native_observation": native})}
    )
    principal = CustomerPrincipal(
        CustomerUser(id=original["inputs"].created_by),
        CustomerSession(digest="b" * 64, authenticated_at=123),
    )
    with pytest.raises(ValueError):
        resolve_google_daily_budget_inputs(
            inputs=original["inputs"],
            intents=(),
            catalogs=(corrupt,),
            sources=original["sources"],
            principal=principal,
            privacy_revision=original["privacy_revision"],
        )
