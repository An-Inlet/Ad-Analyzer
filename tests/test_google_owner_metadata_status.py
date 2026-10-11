"""Injected metadata query through owner derivation; no live or ownership claim."""

import json
from typing import Any

import httpx
import pytest
from app.collectors.google_native_inventory import GoogleNativeInventory
from app.planning_catalog.metadata_http import PlanningMetadataUnavailable, read_metadata
from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.google_budget_owner_contracts import (
    GoogleBudgetOwnerUnavailable,
    derive_google_daily_budget_owner,
)
from pydantic import SecretStr

from tests.test_google_budget_owner_contracts import evidence
from tests.test_planning_metadata_binding import bundle


@pytest.mark.parametrize(
    "variant", ["observed", "missing", "null", "contradiction", "unknown", "bool"]
)
def test_google_campaign_status_reaches_strict_owner_derivation(variant: str) -> None:
    original, _ = bundle("google")
    assert isinstance(original, GoogleNativeInventory)
    raw = original.model_dump(mode="python")
    campaign = raw["campaigns"][0]
    prefix = campaign["resource_name"].rsplit("/", 1)[0] + "/"
    raw["campaigns"] = [
        dict(campaign, resource_name=prefix + ident, status=status)
        for ident, status in (("1", "ENABLED"), ("2", "PAUSED"), ("9", "REMOVED"))
    ]
    raw["campaign_budgets"][0].update(explicitly_shared=True, reference_count=2)
    inventory = GoogleNativeInventory.model_validate(raw)
    calls: list[str] = []

    def wire(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.host == "googleads.googleapis.com"
        query = json.loads(request.content)["query"]
        calls.append(query)
        if "FROM ad_group" in query:
            return httpx.Response(200, json={"results": []})
        assert (
            query == "SELECT campaign.resource_name, campaign.name, campaign.status FROM campaign"
        )
        rows: list[dict[str, Any]] = []
        for observed in inventory.campaigns:
            row: dict[str, Any] = dict(
                resourceName=observed.resource_name,
                name="Observed Campaign",
                status=observed.status,
            )
            if observed.resource_name.endswith("/2"):
                if variant == "missing":
                    row.pop("status")
                elif variant != "observed":
                    row["status"] = {
                        "null": None,
                        "contradiction": "ENABLED",
                        "unknown": "UNKNOWN",
                        "bool": True,
                    }[variant]
            rows.append({"campaign": row})
        return httpx.Response(200, json={"results": rows})

    def read() -> Any:
        return read_metadata(
            inventory,
            httpx.MockTransport(wire),
            lambda req, now: dict(
                scope=req.account,
                request_digest=req.digest(),
                access_token=SecretStr("synthetic"),
                expires_at=inventory.expires_at,
                developer_token=None,
                login_customer_id=None,
            ),
            lambda: inventory.observed_at,
        )

    if variant == "bool":
        with pytest.raises(PlanningMetadataUnavailable):
            read()
        assert len(calls) == 1
        return
    metadata = read()
    assert len(calls) == 2
    statuses = {e.reference.entity_id: e.status for e in metadata.entities}
    assert statuses["1"] == "ENABLED" and statuses["9"] == "REMOVED"
    assert (
        statuses["2"]
        == {
            "observed": "PAUSED",
            "missing": None,
            "null": None,
            "contradiction": "ENABLED",
            "unknown": "UNKNOWN",
        }[variant]
    )
    catalog = project_v2(inventory, metadata)
    ref = evidence(removed=True).reference.model_copy(
        update={
            "document_digest": catalog.composite_digest,
            "source_binding_digest": metadata.source_binding_digest,
        }
    )
    collected = CatalogEvidence(reference=ref, catalog=catalog)
    owner = catalog.targets[0].budget_owner_key
    assert owner is not None
    if variant != "observed":
        with pytest.raises(GoogleBudgetOwnerUnavailable, match="status_unavailable"):
            derive_google_daily_budget_owner(collected, owner)
    else:
        witness = derive_google_daily_budget_owner(collected, owner)
        assert {t.provider_reference.entity_id for t in witness.affected_campaigns} == {"1", "2"}
        assert witness.reference_count == 2
