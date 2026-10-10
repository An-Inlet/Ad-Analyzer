"""Closed source index only; every field is re-resolved against the owned database."""

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Id = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{32}$")]
Digest = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
Positive = Annotated[int, Field(strict=True, ge=1, le=2**63 - 1)]
Count = Annotated[int, Field(strict=True, ge=0, le=256)]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BrandCommon(Closed):
    workspace_id: Positive
    actor_id: Id
    account_id: Positive
    advertising_integration_id: Positive
    store_id: Id
    shopify_connection_id: Positive
    shopify_integration_id: Positive
    crm_connection_id: Id
    crm_integration_id: Positive
    goal_id: Id
    goal_revision: Positive
    simulation_mandate_id: Id
    draft_id: Id
    draft_revision: Positive
    draft_digest: Digest


class BrandA(BrandCommon):
    platform: Literal["google_ads"]
    crm: Literal["klaviyo"]
    native_connection_id: Id


class BrandB(BrandCommon):
    platform: Literal["meta_ads"]
    crm: Literal["hubspot"]
    native_connection_id: Positive


class ActivationGraph(Closed):
    provider_mandate_id: Id
    provider_mandate_revision: Positive
    provider_policy_digest: Digest
    provider_consent_id: Id
    ledger_id: Id
    reservation_id: Id
    creation_review_id: Id
    creation_review_digest: Digest
    creation_plan_digest: Digest
    creation_run_id: Id
    activation_review_id: Id
    activation_review_digest: Digest
    activation_plan_digest: Digest
    activation_run_id: Id
    owned_attempt_id: Id
    owned_request_digest: Digest
    owned_receipt_id: Id
    owned_receipt_digest: Digest


class GraphCounts(Closed):
    creation_attempts: Count
    creation_receipts: Count
    activation_attempts: Count
    activation_receipts: Count
    held_reservations: Count
    creation_provider_posts: Count
    activation_provider_posts: Count


class TwoBrandReceiptSourceV1(Closed):
    schema_version: Literal["inlet.test.two-brand-receipt-source.v1"]
    source_commit: Literal["2155ff3e3ab00cd62057dd86cb49d45359d4f49f"]
    brand_a: BrandA
    brand_b: BrandB
    execution: ActivationGraph
    counts: GraphCounts


def parse_source(raw: str) -> TwoBrandReceiptSourceV1:
    """Reject ambiguous or oversized scalar indexes before owned graph resolution."""
    if len(raw.encode("utf-8")) > 16384:
        raise ValueError("source index exceeds bound")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate source field")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    return TwoBrandReceiptSourceV1.model_validate(value)
