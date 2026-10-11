"""Allocation currency follows exact owned catalog evidence, never inferred FX."""

from fastapi import HTTPException

from app.planning_documents.composer import targets
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.ports import CatalogEvidence


def check_allocations(inputs: PlanInputRevision, catalogs: tuple[CatalogEvidence, ...]) -> None:
    inputs = PlanInputRevision.model_validate(inputs)
    available = {}
    for value in catalogs:
        catalog = CatalogEvidence.model_validate(value)
        for target in targets(catalog):
            key = (target.account.account_id, target.canonical_entity_key, target.selection_key)
            if key in available:
                raise HTTPException(
                    409, "Selected target catalog is ambiguous. Read the current catalog again."
                )
            available[key] = (target, catalog.catalog.native_observation.currency)
    allocations = list(inputs.fixed_allocations)
    allocations.extend(a for scenario in inputs.scenario_intents for a in scenario.allocations)
    for allocation in allocations:
        target = allocation.target
        key = (target.account.account_id, target.canonical_entity_key, target.selection_key)
        entry = available.get(key)
        if entry is None or entry[0] != target or target.account not in inputs.accounts:
            raise HTTPException(
                409, "Selected target changed. Read the current catalog and select again."
            )
        if entry[1] != inputs.budget_period.currency:
            raise HTTPException(422, "Planning allocations must use the confirmed goal currency.")
