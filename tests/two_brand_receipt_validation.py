"""Re-resolve source scalar index; it never stands in for owned graph evidence."""

from pathlib import Path
from typing import Any

from app.campaign_review.storage import LocalMediaStore
from app.publication.activation_review import ActivationExecutionReview
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_contracts import ProviderMandatePolicy
from sqlalchemy import Engine

from tests.two_brand_closure_graph import snapshot
from tests.two_brand_receipt_contracts import TwoBrandReceiptSourceV1


def validate_source(engine: Engine, ids: TwoBrandReceiptSourceV1, media_path: Path) -> None:
    graph = snapshot(engine)

    def one(table: str, **filters: Any) -> dict[str, Any]:
        values = [r for r in graph[table] if all(r[k] == v for k, v in filters.items())]
        assert len(values) == 1, table
        return values[0]

    a, b = ids.brand_a, ids.brand_b
    assert a.workspace_id != b.workspace_id and a.actor_id != b.actor_id
    assert len(graph["workspaces"]) == len(graph["customer_users"]) == 2
    for brand in (a, b):
        one("workspaces", id=brand.workspace_id, status="active")
        one("customer_users", id=brand.actor_id, status="active")
        one(
            "customer_memberships",
            workspace_id=brand.workspace_id,
            user_id=brand.actor_id,
            role="owner",
            status="active",
        )
        one(
            "advertising_accounts",
            id=brand.account_id,
            workspace_id=brand.workspace_id,
            connection_id=brand.advertising_integration_id,
        )
        one(
            "workspace_integrations",
            id=brand.advertising_integration_id,
            workspace_id=brand.workspace_id,
            provider=brand.platform,
        )
        one(
            "commerce_stores",
            id=brand.store_id,
            workspace_id=brand.workspace_id,
            connection_id=brand.shopify_integration_id,
        )
        one(
            "shopify_connections",
            id=brand.shopify_connection_id,
            workspace_id=brand.workspace_id,
            commerce_store_id=brand.store_id,
            workspace_integration_id=brand.shopify_integration_id,
        )
        one(
            "workspace_integrations",
            id=brand.shopify_integration_id,
            workspace_id=brand.workspace_id,
            provider="shopify",
        )
        one(
            "customer_source_connections",
            id=brand.crm_connection_id,
            workspace_id=brand.workspace_id,
            integration_id=brand.crm_integration_id,
            provider=brand.crm,
        )
        one(
            "workspace_integrations",
            id=brand.crm_integration_id,
            workspace_id=brand.workspace_id,
            provider=brand.crm,
        )
        one(
            "customer_goals",
            id=brand.goal_id,
            workspace_id=brand.workspace_id,
            revision=brand.goal_revision,
        )
        one("spending_mandates", id=brand.simulation_mandate_id, workspace_id=brand.workspace_id)
        one("customer_campaign_drafts", id=brand.draft_id, workspace_id=brand.workspace_id)
        one(
            "customer_campaign_revisions",
            draft_id=brand.draft_id,
            revision=brand.draft_revision,
            digest=brand.draft_digest,
            approved_by=brand.actor_id,
        )
        one(
            "google_customer_connections" if brand.platform == "google_ads" else "meta_connections",
            id=brand.native_connection_id,
            workspace_id=brand.workspace_id,
            account_id=brand.account_id,
        )
    e = ids.execution
    policyrow = one(
        "provider_execution_revisions",
        mandate_id=e.provider_mandate_id,
        revision=e.provider_mandate_revision,
        workspace_id=a.workspace_id,
        digest=e.provider_policy_digest,
    )
    policy = ProviderMandatePolicy.model_validate(policyrow["policy"])
    assert policy.digest() == e.provider_policy_digest and policy.environment == "contract_test"
    one(
        "provider_execution_consents",
        id=e.provider_consent_id,
        workspace_id=a.workspace_id,
        mandate_id=e.provider_mandate_id,
        revision=e.provider_mandate_revision,
        policy_digest=e.provider_policy_digest,
        actor=a.actor_id,
    )
    one(
        "provider_execution_mandates",
        id=e.provider_mandate_id,
        workspace_id=a.workspace_id,
        ledger_id=e.ledger_id,
    )
    one("provider_period_ledgers", id=e.ledger_id, workspace_id=a.workspace_id)
    one(
        "provider_exposure_reservations",
        id=e.reservation_id,
        workspace_id=a.workspace_id,
        state="held",
        ledger_id=e.ledger_id,
    )
    creation = one(
        "provider_execution_reviews",
        id=e.creation_review_id,
        workspace_id=a.workspace_id,
        digest=e.creation_review_digest,
        plan_digest=e.creation_plan_digest,
    )
    activation = one(
        "provider_execution_reviews",
        id=e.activation_review_id,
        workspace_id=a.workspace_id,
        digest=e.activation_review_digest,
        plan_digest=e.activation_plan_digest,
    )
    c = CreationExecutionReview.model_validate(creation["document"])
    v = ActivationExecutionReview.model_validate(activation["document"])
    assert c.digest() == e.creation_review_digest and v.digest() == e.activation_review_digest
    assert c.plan.digest() == e.creation_plan_digest and v.plan.digest() == e.activation_plan_digest
    assert c.mandate == v.mandate and c.mandate.mandate_id == e.provider_mandate_id
    assert v.reservation_id == e.reservation_id
    one(
        "provider_execution_runs",
        id=e.creation_run_id,
        workspace_id=a.workspace_id,
        review_id=e.creation_review_id,
        reservation_id=e.reservation_id,
    )
    one(
        "provider_execution_runs",
        id=e.activation_run_id,
        workspace_id=a.workspace_id,
        review_id=e.activation_review_id,
        reservation_id=e.reservation_id,
        parent_run_id=e.creation_run_id,
    )
    counts = ids.counts
    for run_id, n, expected, outcome, domain in (
        (
            e.creation_run_id,
            counts.creation_attempts,
            len(c.plan.steps),
            "verified_effect",
            "inlet.provider-receipt.v1",
        ),
        (
            e.activation_run_id,
            counts.activation_attempts,
            len(v.plan.targets),
            "verified_target_state",
            "inlet.activation-receipt.v1",
        ),
    ):
        attempts = [r for r in graph["provider_execution_attempts"] if r["run_id"] == run_id]
        assert len(attempts) == n == expected
        for attempt in attempts:
            assert attempt["workspace_id"] == a.workspace_id
            receipt = one(
                "provider_execution_receipts",
                attempt_id=attempt["id"],
                workspace_id=a.workspace_id,
                sequence=1,
            )
            assert receipt["receipt"]["outcome"] == outcome
            # Same exact persisted receipt hash domain used by its current reader.
            assert fingerprint(domain, receipt["receipt"]) == receipt["digest"]
    assert counts.creation_receipts == counts.creation_attempts == counts.creation_provider_posts
    assert (
        counts.activation_receipts == counts.activation_attempts == counts.activation_provider_posts
    )
    assert counts.held_reservations == len(graph["provider_exposure_reservations"]) == 1
    one(
        "provider_execution_attempts",
        id=e.owned_attempt_id,
        workspace_id=a.workspace_id,
        run_id=e.activation_run_id,
        request_digest=e.owned_request_digest,
    )
    one(
        "provider_execution_receipts",
        id=e.owned_receipt_id,
        workspace_id=a.workspace_id,
        attempt_id=e.owned_attempt_id,
        digest=e.owned_receipt_digest,
    )
    store = LocalMediaStore(media_path)
    for row in graph["customer_media_objects"]:
        assert row["workspace_id"] == b.workspace_id and row["created_by"] == b.actor_id
        store.read_exact(row["workspace_id"], row["sha256"], row["size"])
