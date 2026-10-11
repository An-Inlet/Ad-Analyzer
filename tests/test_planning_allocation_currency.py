"""Exact catalog joins and unsafe-copy refusal at the shared currency boundary."""

import pytest
from app.planning_documents.allocation_currency import check_allocations
from app.planning_documents.composer import targets
from fastapi import HTTPException
from pydantic import ValidationError

from tests.test_planning_composer import fixture


def test_duplicate_catalog_is_not_last_write_wins() -> None:
    inputs, bundle, _ = fixture()
    with pytest.raises(HTTPException) as caught:
        check_allocations(inputs, (bundle.catalogs[0], bundle.catalogs[0]))
    assert caught.value.status_code == 409


def test_complete_target_identity_not_just_selection_tuple() -> None:
    _, source, _ = fixture()
    target = next(t for t in targets(source.catalogs[0]) if t.kind == "campaign")
    forged = target.model_copy(update={"catalog_evidence_key": "other-catalog"})
    inputs, bundle, _ = fixture(fixed_allocations=({"target": forged, "amount_micros": 0},))
    with pytest.raises(HTTPException) as caught:
        check_allocations(inputs, bundle.catalogs)
    assert caught.value.status_code == 409


def test_unsafe_input_copy_is_revalidated() -> None:
    inputs, bundle, _ = fixture()
    bad = inputs.model_copy(update={"total_ceiling_micros": -1})
    with pytest.raises(ValidationError):
        check_allocations(bad, bundle.catalogs)


def test_exact_zero_same_currency_allocation_is_allowed() -> None:
    _, source, _ = fixture()
    target = next(t for t in targets(source.catalogs[0]) if t.kind == "campaign")
    inputs, bundle, _ = fixture(fixed_allocations=({"target": target, "amount_micros": 0},))
    check_allocations(inputs, bundle.catalogs)
