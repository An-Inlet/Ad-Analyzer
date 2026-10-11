"""Pure extracted save phases; no authority, SQL, timing or API qualification."""

from typing import Any

import pytest
from app.planning_documents import repository
from fastapi import HTTPException
from pydantic import ValidationError

from tests.owner_review_v6_fixture import ready as owner_ready
from tests.test_creative_plan_composer import compose, ready
from tests.test_owner_review_v6_pure import compose as owner_compose


@pytest.mark.parametrize("version", [5, 6])
def test_pure_phases_preserve_complete_document(version: int) -> None:
    values = owner_ready() if version == 6 else ready()
    ticket, bundle, _, _ = values
    candidate = owner_compose(values) if version == 6 else compose(values)
    before = candidate.model_dump_json(), candidate.digest()
    checked_ticket, checked_candidate, capability = repository._generation_entry(
        ticket, bundle, candidate
    )
    repository._generation_actual_bindings(checked_ticket, bundle, checked_candidate)
    repository._generation_owner_binding(checked_ticket, bundle, checked_candidate, capability)
    assert (checked_candidate.model_dump_json(), checked_candidate.digest()) == before
    assert checked_ticket == ticket


def test_entry_preserves_raw_validation_error() -> None:
    values = owner_ready()
    ticket, bundle, _, _ = values
    candidate = owner_compose(values)
    with pytest.raises(ValidationError):
        repository._generation_entry(
            ticket.model_copy(update={"expected_version": True}), bundle, candidate
        )


def test_entry_preserves_capability_error_cause() -> None:
    values = owner_ready()
    ticket, bundle, _, _ = values
    with pytest.raises(HTTPException) as error:
        repository._generation_entry(
            ticket.model_copy(update={"policy_digest": "0" * 64}), bundle, owner_compose(values)
        )
    assert error.value.status_code == 409
    assert error.value.detail == "unknown planning policy or generator"
    assert isinstance(error.value.__cause__, ValueError)


def test_actual_binding_preserves_selected_proof_refusal() -> None:
    values = owner_ready()
    ticket, bundle, _, _ = values
    candidate = owner_compose(values).model_copy(update={"selected_reporting_proof": None})
    with pytest.raises(HTTPException) as error:
        repository._generation_actual_bindings(ticket, bundle, candidate)
    assert error.value.status_code == 409
    assert error.value.detail == "candidate selected proof differs from actual read bundle"


@pytest.mark.parametrize("status", [409, 422])
def test_allocation_domain_exception_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    values = owner_ready()
    ticket, bundle, _, _ = values
    candidate = owner_compose(values)
    failure = HTTPException(
        status,
        "Planning allocations must use the confirmed goal currency."
        if status == 422
        else "Selected target changed. Read the current catalog and select again.",
    )
    calls = []

    def reject(*args: Any) -> None:
        calls.append(args)
        raise failure

    monkeypatch.setattr(repository, "check_allocations", reject)
    with pytest.raises(HTTPException) as error:
        repository._generation_actual_bindings(ticket, bundle, candidate)
    assert error.value is failure
    assert len(calls) == 1
    assert calls[0] == (ticket.inputs, bundle.reporting.selected.catalogs)


def test_owner_check_preserves_unexpected_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    values = owner_ready()
    ticket, bundle, _, _ = values
    candidate = owner_compose(values)
    _, _, capability = repository._generation_entry(ticket, bundle, candidate)
    failure = RuntimeError("test-only unexpected callback failure")
    calls = []

    def reject(**kwargs: Any) -> None:
        calls.append(kwargs)
        raise failure

    monkeypatch.setattr(repository, "assert_owner_review_generation_bundle", reject)
    with pytest.raises(RuntimeError) as error:
        repository._generation_owner_binding(ticket, bundle, candidate, capability)
    assert error.value is failure
    assert calls == [dict(ticket=ticket, candidate=candidate, bundle=bundle)]
