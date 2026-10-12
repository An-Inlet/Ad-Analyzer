"""Distinct persisted schema, bound prior-row linkage, and legacy reader compatibility."""

from typing import Any

import pytest
from app.planning_documents.google_budget_events import (
    GoogleBudgetInvalidationV1,
    GoogleBudgetObservationV1,
)
from app.planning_documents.storage import canonical, document_for_row, export_row

from tests.google_budget_event_fixture import history


@pytest.fixture(scope="module")
def events() -> Any:
    return history()


def row(event: Any, sequence: int, prior: int | None) -> dict[str, Any]:
    return dict(
        workspace_id=event.workspace_id,
        plan_id=event.plan_id,
        sequence=sequence,
        event_id=event.event_id,
        version=event.version,
        action_key=event.action_key,
        action_digest=event.action_digest,
        kind="observation",
        actor_id=event.actor_id,
        recorded_at=event.recorded_at,
        prior_sequence=prior,
        canonical_json=canonical(event),
        digest=event.digest(),
    )


def test_budget_event_reader_export_and_prior_linkage(events: Any) -> None:
    for event, sequence, prior in ((events[0], 1, None), (events[1], 2, 1)):
        values = row(event, sequence, prior)
        assert document_for_row("planning_document_events", values) == event
        exported = export_row("planning_document_events", values)
        assert exported["document"] == event.model_dump(mode="json")
        assert exported["document"]["current_reliance"] == "not_assessed"
        assert exported["document"]["implementation"] == "not_assessed"
        wrong = dict(values, prior_sequence=7)
        with pytest.raises(ValueError, match="ownership/content"):
            document_for_row("planning_document_events", wrong)
    assert isinstance(events[0], GoogleBudgetObservationV1)
    assert isinstance(events[1], GoogleBudgetInvalidationV1)


@pytest.mark.parametrize(
    "case",
    [
        "foreign-ticket",
        "copied-amount",
        "wrong-finding",
        "live-provenance",
        "invalidation-time",
        "invalidation-source",
    ],
)
def test_new_event_forgery_refusal(events: Any, case: str) -> None:
    first, second = events
    if case == "foreign-ticket":
        bad = first.model_copy(
            update={
                "proof": first.proof.model_copy(
                    update={
                        "ticket": first.proof.ticket.model_copy(
                            update={
                                "binding": first.binding().model_copy(update={"plan_id": "0" * 32})
                            }
                        )
                    }
                )
            }
        )
    elif case == "copied-amount":
        bad = first.model_copy(
            update={
                "comparison": first.comparison.model_copy(
                    update={
                        "fresh": first.comparison.fresh.model_copy(
                            update={"current_amount_micros": 2}
                        )
                    }
                )
            }
        )
    elif case == "wrong-finding":
        bad = first.model_copy(update={"finding": "differs_from_hypothesis"})
    elif case == "live-provenance":
        bad = first.model_copy(update={"provenance": "authenticated_provider"})
    elif case == "invalidation-time":
        bad = second.model_copy(update={"recorded_at": first.comparison.document.generated_at})
    else:
        bad = second.model_copy(update={"current_source_digest": second.original_source_digest})
    with pytest.raises(ValueError):
        canonical(bad)
