"""Closed scalar boundary rejects ambiguity; it does not validate graph authority."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from tests.two_brand_receipt_contracts import parse_source


def scalar_fixture() -> dict[str, Any]:
    # Pure parser inputs only, never installed in a DB or used as source evidence.
    common = dict(
        workspace_id=1,
        actor_id="a" * 32,
        account_id=1,
        advertising_integration_id=1,
        store_id="b" * 32,
        shopify_connection_id=1,
        shopify_integration_id=2,
        crm_connection_id="c" * 32,
        crm_integration_id=3,
        goal_id="d" * 32,
        goal_revision=1,
        simulation_mandate_id="e" * 32,
        draft_id="f" * 32,
        draft_revision=1,
        draft_digest="a" * 64,
    )
    from tests.two_brand_receipt_contracts import ActivationGraph, GraphCounts

    execution = {
        k: (1 if k == "provider_mandate_revision" else "a" * (64 if "digest" in k else 32))
        for k in ActivationGraph.model_fields
    }
    return dict(
        schema_version="inlet.test.two-brand-receipt-source.v1",
        source_commit="2155ff3e3ab00cd62057dd86cb49d45359d4f49f",
        brand_a=dict(common, platform="google_ads", crm="klaviyo", native_connection_id="a" * 32),
        brand_b=dict(common, platform="meta_ads", crm="hubspot", native_connection_id=1),
        execution=execution,
        counts={k: 1 for k in GraphCounts.model_fields},
    )


def test_scalar_json_roundtrip_and_distinct_shopify_ids() -> None:
    parsed = parse_source(json.dumps(scalar_fixture()))
    assert parsed.brand_a.shopify_connection_id != parsed.brand_a.shopify_integration_id
    assert parse_source(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize("mutation", ["boolean", "string", "wrong_native_type", "extra", "pin"])
def test_scalar_index_rejects_unreviewed_values(mutation: str) -> None:
    value = scalar_fixture()
    if mutation in {"boolean", "string"}:
        value["brand_a"]["workspace_id"] = True if mutation == "boolean" else "1"
    elif mutation == "wrong_native_type":
        value["brand_b"]["native_connection_id"] = "a" * 32
    elif mutation == "pin":
        value["source_commit"] = "f" * 40
    else:
        value["source_path"] = "/unowned"
    with pytest.raises(ValidationError):
        parse_source(json.dumps(value))


def test_scalar_index_rejects_duplicate_fields_and_size() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        parse_source('{"brand_a":{},"brand_a":{}}')
    with pytest.raises(ValueError, match="bound"):
        parse_source(" " * 16385)
