"""Exact injected acquisition and extraction; no live provenance qualification."""

import json
from datetime import timedelta
from typing import Any

import pytest
from app.collectors.google_native_inventory import GoogleNativeInventory
from app.planning_catalog.contracts import GoogleSettingsV1
from app.planning_documents.google_budget_read import GoogleBudgetReadProofV1, read_google_budget
from app.planning_documents.google_budget_read_projection import budget_read_witness

from tests.google_budget_read_fixture import Search, ticket
from tests.owner_review_v6_fixture import ready
from tests.test_google_budget_hypothesis_comparison import packet
from tests.test_owner_review_v6_pure import compose
from tests.test_planning_metadata_binding import bundle


@pytest.fixture(scope="module")
def values() -> Any:
    doc = compose(ready())
    inventory, _ = bundle("google")
    assert isinstance(inventory, GoogleNativeInventory)
    return doc, ticket(doc, inventory.request.account), inventory.campaign_budgets[0].resource_name


def setup(values: Any) -> Any:
    doc, request, resource = values
    search = Search(request.account.external_advertiser_id, resource.rsplit("/", 1)[1])
    assert doc.google_budget_owner_review is not None
    search.data["customer"][0]["customer"]["timeZone"] = doc.google_budget_owner_review.reviews[
        0
    ].witness.catalog_evidence.catalog.native_observation.time_zone
    return doc, request, search


def test_full_pages_projection_and_historical_comparison(values: Any) -> None:
    doc, request, search = setup(values)
    proof = read_google_budget(request, search, lambda: request.prepared_at)
    assert search.calls == [
        ("customer", None),
        ("campaign", None),
        ("campaign", "fixture-page-2"),
        ("campaignBudget", None),
    ]
    assert GoogleBudgetReadProofV1.model_validate_json(proof.model_dump_json()) == proof
    fresh = budget_read_witness(proof, doc.google_budget_owner_review.reviews[0].witness.owner_key)
    result = packet(doc, fresh)
    assert result.status == "matches_hypothesis"
    assert fresh.current_amount_micros == 1 and fresh.atomic_snapshot is False
    assert fresh.catalog_evidence.catalog.native_observation.inventory_digest == proof.digest()
    for row in fresh.catalog_evidence.catalog.native_observation.targets:
        assert isinstance(row.settings, GoogleSettingsV1)
        assert row.settings.channel is None and row.settings.bidding_strategy is None
    assert all(t.entity.name is None for t in fresh.catalog_evidence.catalog.targets)


@pytest.mark.parametrize(
    "case",
    [
        "amount-missing",
        "amount-number",
        "amount-leading-zero",
        "amount-null",
        "count",
        "sharing",
        "total",
        "foreign",
        "duplicate",
        "incomplete",
        "query-order",
        "expiry",
        "timestamp",
        "version",
        "profile",
        "unknown-field",
        "duplicate-json",
        "cursor-loop",
    ],
)
def test_read_provenance_refusals(values: Any, case: str) -> None:
    doc, request, search = setup(values)
    budget = search.data["campaignBudget"][0]["campaignBudget"]
    if case == "amount-missing":
        del budget["amountMicros"]
    elif case == "amount-number":
        budget["amountMicros"] = 1
    elif case == "amount-leading-zero":
        budget["amountMicros"] = "01"
    elif case == "amount-null":
        budget["amountMicros"] = None
    elif case == "count":
        budget["referenceCount"] = "3"
    elif case == "sharing":
        del budget["explicitlyShared"]
    elif case == "total":
        budget["totalAmountMicros"] = "0"
    elif case == "foreign":
        budget["resourceName"] = "customers/9999999999/campaignBudgets/2"
    elif case == "duplicate":
        search.data["campaign"][1] = search.data["campaign"][0]
    elif case == "version":
        request = request.model_copy(update={"api_version": "v25"})
    elif case == "profile":
        request = request.model_copy(update={"profile_digest": "0" * 64})
    elif case == "unknown-field":
        budget["accessToken"] = "not-a-token"
    elif case == "duplicate-json":
        search.override = lambda *_: '{"results":[],"results":[]}'
    elif case == "cursor-loop":
        search.override = lambda *_: json.dumps(dict(results=[], nextPageToken="loop"))
    with pytest.raises((ValueError, RuntimeError)):
        proof = read_google_budget(
            request, search, lambda: request.expires_at if case == "expiry" else request.prepared_at
        )
        if case == "incomplete":
            proof = proof.model_copy(update={"pages": proof.pages[:-1]})
        elif case == "query-order":
            proof = proof.model_copy(update={"pages": tuple(reversed(proof.pages))})
        elif case == "timestamp":
            proof = proof.model_copy(
                update={
                    "pages": (
                        proof.pages[0].model_copy(
                            update={"requested_at": request.prepared_at - timedelta(seconds=1)}
                        ),
                        *proof.pages[1:],
                    )
                }
            )
        budget_read_witness(proof, doc.google_budget_owner_review.reviews[0].witness.owner_key)


def test_zero_explicit_and_missing_false_are_distinct(values: Any) -> None:
    doc, request, search = setup(values)
    search.data["campaignBudget"][0]["campaignBudget"]["amountMicros"] = "0"
    proof = read_google_budget(request, search, lambda: request.prepared_at)
    fresh = budget_read_witness(proof, doc.google_budget_owner_review.reviews[0].witness.owner_key)
    assert (
        fresh.current_amount_micros == 0 and packet(doc, fresh).status == "differs_from_hypothesis"
    )
    del search.data["customer"][0]["customer"]["manager"]
    with pytest.raises(ValueError, match="presence"):
        read_google_budget(request, search, lambda: request.prepared_at)


def test_cross_call_clock_rollback_and_non_json_constants(values: Any) -> None:
    _, request, search = setup(values)
    instants = iter(
        (request.prepared_at, request.prepared_at + timedelta(seconds=1), request.prepared_at)
    )
    with pytest.raises(ValueError):
        read_google_budget(request, search, lambda: next(instants))
    assert len(search.calls) == 1
    search.override = lambda *_: '{"results": NaN}'
    with pytest.raises(ValueError, match="non-JSON"):
        read_google_budget(request, search, lambda: request.prepared_at)
