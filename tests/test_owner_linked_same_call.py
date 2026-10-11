"""Same-call owner proof reuse; real validators, no SQL authority qualification."""

from datetime import timedelta, timezone
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.planning_documents import owner_review_generation as generation
from app.planning_documents import owner_review_plan_document as document
from app.planning_documents.catalog_receipts import CatalogReceiptUnavailable
from app.planning_documents.documents import PlanVersion
from app.planning_documents.google_budget_owner_review import validate_google_budget_owner_review
from app.planning_documents.ports import GenerationTicket
from fastapi import HTTPException

from tests.owner_review_v6_fixture import ready
from tests.test_owner_review_v6_pure import compose


def spies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    original = validate_google_budget_owner_review

    def checked(**kwargs: Any) -> None:
        calls.append("document")
        original(**kwargs)

    def fallback(**kwargs: Any) -> None:
        calls.append("fallback")
        original(**kwargs)

    monkeypatch.setattr(document, "validate_google_budget_owner_review", checked)
    monkeypatch.setattr(generation, "validate_google_budget_owner_review", fallback)
    return calls


@pytest.mark.parametrize("empty", [False, True])
def test_exact_arguments_reuse_only_this_full_validation(
    monkeypatch: pytest.MonkeyPatch, empty: bool
) -> None:
    values = ready(empty=empty)
    ticket, bundle, _, _ = values
    candidate = compose(values)
    before = candidate.model_dump_json()
    calls = spies(monkeypatch)
    for _ in range(2):
        assert generation._linked(ticket, candidate, bundle.reporting.selected.catalogs) == (
            candidate.google_budget_input_catalogs
        )
    assert calls == ["document", "document"]
    assert candidate.model_dump_json() == before


@pytest.mark.parametrize("difference", ["order", "unselected"])
def test_valid_source_difference_uses_original_fallback(
    monkeypatch: pytest.MonkeyPatch, difference: str
) -> None:
    values = ready(social="meta", usage="unselected")
    ticket, bundle, _, _ = values
    candidate = compose(values)
    sources = (
        tuple(reversed(ticket.sources))
        if difference == "order"
        else (
            ticket.sources[0],
            ticket.sources[1].model_copy(update={"source_binding_digest": "f" * 64}),
        )
    )
    changed = GenerationTicket.model_validate(ticket.model_copy(update={"sources": sources}))
    calls = spies(monkeypatch)
    assert generation._linked(changed, candidate, bundle.reporting.selected.catalogs) == (
        candidate.google_budget_input_catalogs
    )
    assert calls == ["document", "fallback"]


@pytest.mark.parametrize(
    "difference", ["missing", "duplicate", "extra", "privacy_bool", "privacy", "selected"]
)
def test_invalid_source_or_privacy_never_reuses_prior_validation(
    monkeypatch: pytest.MonkeyPatch, difference: str
) -> None:
    values = ready(social="meta", usage="unselected")
    ticket, bundle, _, _ = values
    candidate = compose(values)
    changes: dict[str, Any]
    if difference == "missing":
        changes = dict(sources=ticket.sources[:1])
    elif difference == "duplicate":
        changes = dict(sources=(ticket.sources[0], ticket.sources[0]))
    elif difference == "extra":
        extra = ticket.sources[1].model_copy(
            update={"account": ticket.sources[1].account.model_copy(update={"account_id": 999})}
        )
        changes = dict(sources=ticket.sources + (extra,))
    elif difference == "selected":
        changes = dict(
            sources=(
                ticket.sources[0].model_copy(update={"source_binding_digest": "f" * 64}),
                ticket.sources[1],
            )
        )
    else:
        changes = dict(
            privacy_revision=True if difference == "privacy_bool" else ticket.privacy_revision + 1
        )
    calls = spies(monkeypatch)
    with pytest.raises(ValueError):
        generation._linked(
            ticket.model_copy(update=changes), candidate, bundle.reporting.selected.catalogs
        )
    if difference == "selected":
        assert calls == ["document", "fallback"]
    else:
        assert calls == []  # Ticket validation is still first and mandatory.


def test_equivalent_offset_does_not_avoid_original_input_join() -> None:
    values = ready()
    ticket, bundle, _, _ = values
    candidate = compose(values)
    changed = ticket.model_copy(
        update={
            "inputs": ticket.inputs.model_copy(
                update={
                    "created_at": ticket.inputs.created_at.astimezone(timezone(timedelta(hours=2)))
                }
            )
        }
    )
    assert changed.inputs.created_at == ticket.inputs.created_at
    # Original full input digest join is retained, even for equal instants.
    with pytest.raises(ValueError, match="exact owner generation ticket required"):
        generation._linked(changed, candidate, bundle.reporting.selected.catalogs)


@pytest.mark.parametrize("field,value", [("version", True), ("advertising_writes_enabled", 0)])
def test_unsafe_copied_candidate_still_fully_validates(field: str, value: Any) -> None:
    values = ready()
    ticket, bundle, _, _ = values
    with pytest.raises(ValueError):
        generation._linked(
            ticket,
            compose(values).model_copy(update={field: value}),
            bundle.reporting.selected.catalogs,
        )


def test_each_receipt_side_call_resolves_and_validates_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = ready()
    ticket, bundle, _, now = values
    candidate = compose(values)
    catalogs = bundle.reporting.selected.catalogs
    resolved: list[int] = []

    def resolve(*args: Any, **kwargs: Any) -> Any:
        resolved.append(1)
        return SimpleNamespace(catalogs=candidate.google_budget_input_catalogs)

    monkeypatch.setattr(generation, "resolve_saved_input_catalogs", resolve)
    calls = spies(monkeypatch)
    for _ in range(2):
        generation.recheck_owner_review_input_receipts(
            cast(Any, None),
            principal=cast(Any, None),
            ticket=ticket,
            candidate=candidate,
            catalogs=catalogs,
            now=now,
        )
    assert resolved == [1, 1]
    assert calls == ["document", "document"]
    with pytest.raises(HTTPException) as error:
        generation.recheck_owner_review_input_receipts(
            cast(Any, None),
            principal=cast(Any, None),
            ticket=ticket,
            candidate=PlanVersion.model_copy(candidate, update={"version": True}),
            catalogs=catalogs,
            now=now,
        )
    assert error.value.status_code == 409
    assert resolved == [1, 1, 1]

    changed_source = ticket.sources[0].model_copy(update={"source_binding_digest": "f" * 64})
    with pytest.raises(HTTPException) as changed:
        generation.recheck_owner_review_input_receipts(
            cast(Any, None),
            principal=cast(Any, None),
            ticket=ticket.model_copy(update={"sources": (changed_source,)}),
            candidate=candidate,
            catalogs=catalogs,
            now=now,
        )
    assert changed.value.status_code == 409
    assert changed.value.detail == "owner review differs from actual collected evidence"
    assert resolved == [1, 1, 1, 1]
    assert calls[-2:] == ["document", "fallback"]


@pytest.mark.parametrize("kind", ["receipt", "unexpected"])
def test_resolver_exceptions_propagate_identically(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    values = ready()
    ticket, bundle, _, now = values
    candidate = compose(values)
    failure = (
        CatalogReceiptUnavailable("missing")
        if kind == "receipt"
        else RuntimeError("test unexpected")
    )
    calls = spies(monkeypatch)

    def resolve(*args: Any, **kwargs: Any) -> Any:
        raise failure

    monkeypatch.setattr(generation, "resolve_saved_input_catalogs", resolve)
    with pytest.raises(type(failure)) as error:
        generation.recheck_owner_review_input_receipts(
            cast(Any, None),
            principal=cast(Any, None),
            ticket=ticket,
            candidate=candidate,
            catalogs=bundle.reporting.selected.catalogs,
            now=now,
        )
    assert error.value is failure
    assert calls == []
