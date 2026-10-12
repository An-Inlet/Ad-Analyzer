"""Genuine retained pure plan with explicit injected fixture acquisition."""

from datetime import timedelta

from app.collectors.google_native_inventory import GoogleNativeInventory
from app.planning_documents.google_budget_events import (
    GoogleBudgetInvalidationV1,
    GoogleBudgetObservationV1,
)
from app.planning_documents.google_budget_read import read_google_budget
from app.planning_documents.google_budget_read_projection import budget_read_witness
from app.publication.contracts import fingerprint

from tests.google_budget_read_fixture import Search, ticket
from tests.owner_review_v6_fixture import ready
from tests.test_google_budget_hypothesis_comparison import packet
from tests.test_owner_review_v6_pure import compose
from tests.test_planning_metadata_binding import bundle


def history() -> tuple[GoogleBudgetObservationV1, GoogleBudgetInvalidationV1]:
    doc = compose(ready())
    inventory, _ = bundle("google")
    assert isinstance(inventory, GoogleNativeInventory)
    request = ticket(doc, inventory.request.account)
    search = Search(
        request.account.external_advertiser_id,
        inventory.campaign_budgets[0].resource_name.rsplit("/", 1)[1],
    )
    assert doc.google_budget_owner_review is not None
    review = doc.google_budget_owner_review.reviews[0]
    search.data["customer"][0]["customer"]["timeZone"] = (
        review.witness.catalog_evidence.catalog.native_observation.time_zone
    )
    proof = read_google_budget(request, search, lambda: request.prepared_at)
    comparison = packet(doc, budget_read_witness(proof, review.witness.owner_key))
    observed = GoogleBudgetObservationV1(
        **request.binding.model_dump(),
        event_id="e" * 32,
        actor_id=doc.generated_by,
        recorded_at=comparison.compared_at,
        comparison=comparison,
        proof=proof,
        finding="matches_hypothesis",
    )
    changed = request.account.model_copy(update={"connection_version": "next-generation"})
    invalidated = GoogleBudgetInvalidationV1(
        **request.binding.model_dump(),
        event_id="f" * 32,
        actor_id=doc.generated_by,
        recorded_at=comparison.compared_at + timedelta(seconds=1),
        observation_event_id=observed.event_id,
        observation_digest=observed.digest(),
        observation_sequence=1,
        observation_recorded_at=observed.recorded_at,
        original_source_digest=request.source_digest(),
        current_account=changed,
        current_source_digest=fingerprint(
            "inlet.planning-source.v1", changed.model_dump(mode="json")
        ),
        privacy_revision=request.privacy_revision,
    )
    return observed, invalidated
