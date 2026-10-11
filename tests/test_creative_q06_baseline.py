"""Actual shared-owner topology and planning rejection; no native-edit qualification."""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_planning_target_catalog
from app.collectors import account_diagnostics
from app.customers.access import SESSION_COOKIE
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.documents import PlanVersion
from app.planning_documents.google_budget_owner_contracts import (
    GoogleBudgetOwnerUnavailable,
    derive_google_daily_budget_owner,
)
from app.settings import Settings
from sqlalchemy import Engine

from tests.creative_common_basis_fixture import prepare_creative_common_basis
from tests.creative_q07_fixture import planning_snapshot
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_google_native_inventory import PREFIX, key, payloads
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("partial", [False, True], ids=["complete-owner", "incomplete-owner"])
def test_actual_v5_q06_shared_owner_baseline(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    partial: bool,
) -> None:
    fixture = prepare_creative_common_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        platform="google_ads",
        selected_value="10",
    )
    alice, _, _ = replicas
    aid, wid = fixture.basis.account_id, fixture.basis.workspace_id
    original_session = alice.cookies[SESSION_COOKIE]
    data = payloads()
    original = data["campaign"][0]["campaign"]
    data["campaign"] = [
        {
            "campaign": {
                **original,
                "resourceName": PREFIX + f"campaigns/{native}",
                "campaignBudget": PREFIX + f"campaignBudgets/{budget}",
                "name": f"Mug Campaign {native}",
            }
        }
        for native, budget in (("1", "2"), ("2", "2"), ("3", "4"))
    ]
    shared = data["campaign_budget"][0]["campaignBudget"]
    shared.update(referenceCount="3" if partial else "2", explicitlyShared=True)
    data["campaign_budget"].append(
        {
            "campaignBudget": {
                **shared,
                "resourceName": PREFIX + "campaignBudgets/4",
                "referenceCount": "1",
                "explicitlyShared": False,
            }
        }
    )
    calls: list[tuple[str, str]] = []
    campaign_pages: list[str] = []

    def wire(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        calls.append((request.url.host, request.url.path))
        if request.url.host == "oauth2.googleapis.com":
            assert request.url.path == "/token"
            return httpx.Response(
                200,
                json=dict(access_token="synthetic-access", token_type="Bearer", expires_in=3600),
            )
        assert request.url.host == "googleads.googleapis.com"
        assert request.url.path.endswith("/googleAds:search")
        body = json.loads(request.content)
        query = body["query"]
        if "FROM ad_group" in query:
            rows = [
                {
                    "adGroup": dict(
                        id=str(10 + i),
                        resourceName=PREFIX + f"adGroups/{10 + i}",
                        campaign=PREFIX + f"campaigns/{i}",
                        name=f"Mug Child {i}",
                        status="ENABLED",
                        type="SEARCH_STANDARD",
                    )
                }
                for i in (1, 2, 3)
            ]
        elif "FROM campaign " in query or query.endswith("FROM campaign"):
            token = body.get("pageToken", "")
            assert token in {"", "second"}
            campaign_pages.append(token)
            return httpx.Response(
                200,
                json={
                    "results": data["campaign"][1:] if token else data["campaign"][:1],
                    **({} if token else {"nextPageToken": "second"}),
                },
            )
        else:
            rows = data[key(query)]
        return httpx.Response(200, json={"results": rows})

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    alice.app.include_router(customer_planning_target_catalog.router)
    root = f"/api/customer/v1/workspaces/{wid}"
    window = fixture.body["inputs"]["reporting_window"]
    response = alice.post(
        root + "/planning/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=aid, starts_at=window["starts_at"], ends_at=window["ends_at_exclusive"]
        ),
    )
    assert response.status_code == 200, response.text
    catalog = response.json()
    targets = {
        t["entity"]["reference"]["entity_id"]: t
        for t in catalog["targets"]
        if t["entity"]["kind"] == "campaign"
    }
    assert set(targets) == {"1", "2", "3"}
    native = catalog["native_observation"]
    assert (native["workspace_id"], native["account_id"], native["platform"]) == (
        wid,
        aid,
        "google_ads",
    )
    settings_by_key = {row["selection_key"]: row for row in native["targets"]}
    for identity, target in targets.items():
        assert target["entity"]["reference"] == dict(
            platform="google_ads",
            advertiser_id="1234567890",
            entity_id=identity,
            parent_campaign_id=None,
        )
        assert target["entity"]["name"] == f"Mug Campaign {identity}"
        row = settings_by_key[target["native_settings_key"]]
        assert row["budget_owner_key"] == target["budget_owner_key"]
        value = row["settings"]
        assert target["entity"]["status"] == value["status"] == "ENABLED"
        assert tuple(
            value[field]
            for field in (
                "budget_amount_micros",
                "budget_total_amount_micros",
                "budget_period",
                "budget_status",
                "budget_type",
                "budget_explicitly_shared",
                "budget_reference_count",
            )
        ) == (
            10_000_000,
            None,
            "DAILY",
            "ENABLED",
            "STANDARD",
            identity != "3",
            (3 if partial else 2) if identity != "3" else 1,
        )
    children = [t for t in catalog["targets"] if t["entity"]["kind"] == "adgroup"]
    assert len(children) == 3
    for child in children:
        ref = child["entity"]["reference"]
        parent = ref["parent_campaign_id"]
        assert parent in targets
        assert ref == dict(
            platform="google_ads",
            advertiser_id="1234567890",
            entity_id=str(10 + int(parent)),
            parent_campaign_id=parent,
        )
        assert child["entity"]["name"] == f"Mug Child {parent}"
        assert (
            child["native_settings_key"] is None
        )  # named metadata does not invent native settings
    assert targets["1"]["budget_owner_key"] == targets["2"]["budget_owner_key"]
    assert targets["1"]["budget_owner_key"] is not None
    assert targets["3"]["budget_owner_key"] != targets["1"]["budget_owner_key"]
    native_coverage = next(
        c for c in catalog["native_observation"]["coverage"] if c["kind"] == "campaign"
    )
    assert native_coverage["observed_count"] == 3
    assert native_coverage["status"] == ("partial" if partial else "complete")
    assert native_coverage["reasons"] == (["advertising_inventory_incomplete"] if partial else [])
    assert campaign_pages and "second" in campaign_pages

    def selector(native: str) -> dict[str, Any]:
        return dict(
            account_id=aid,
            canonical_entity_key=targets[native]["canonical_entity_key"],
            selection_key=targets[native]["selection_key"],
        )

    body = copy.deepcopy(fixture.body)
    body["request_key"] = "q06-native-owner"
    body["inputs"]["scenario_intents"] = [
        dict(
            key="owner_split",
            title="Independent Owner Planning",
            unallocated_micros=500_000_000,
            allocations=[
                dict(target=selector(native), amount_micros=amount)
                for native, amount in (("1", 300_000_000), ("2", 200_000_000))
            ],
        )
    ]
    snapshot = planning_snapshot(customer_engine)
    effects = financial_counts(customer_engine)
    assert effects == (0,) * 6
    denied = alice.post(root + "/planning/plans", headers=headers(alice), json=body)
    assert denied.status_code == 422, denied.text
    assert (
        denied.json()["detail"]
        == "Planning selections and scenarios must match the confirmed budget and constraints."
    )
    assert planning_snapshot(customer_engine) == snapshot
    assert financial_counts(customer_engine) == effects
    body["inputs"]["scenario_intents"][0]["allocations"][1]["target"] = selector("3")
    created = alice.post(root + "/planning/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/planning/plans/" + created.json()["plan_id"]
    intent = dict(expected_input_revision=1, expected_version=0, request_key="q06-owner-generate")
    generated = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert generated.status_code == 200, generated.text
    document = generated.json()["document"]
    doc = PlanVersion.model_validate(document)
    collected = CatalogEvidence.model_validate(
        dict(reference=next(e for e in doc.evidence if e.kind == "native_catalog"), catalog=catalog)
    )
    if partial:
        with pytest.raises(GoogleBudgetOwnerUnavailable, match="coverage_unavailable"):
            derive_google_daily_budget_owner(collected, targets["1"]["budget_owner_key"])
    else:
        witness = derive_google_daily_budget_owner(collected, targets["1"]["budget_owner_key"])
        assert {t.provider_reference.entity_id for t in witness.affected_campaigns} == {"1", "2"}
        assert witness.reference_count == 2 and witness.current_amount_micros == 10_000_000
    alternative = next(s for s in doc.scenarios if s.customer_intent_key == "owner_split")
    assert [a.target.provider_reference.entity_id for a in alternative.allocations] == ["1", "3"]
    for allocation in alternative.allocations:
        account = allocation.target.account
        assert (
            account.workspace_id,
            account.account_id,
            account.platform,
            account.connection_id,
            account.connection_version,
        ) == (
            wid,
            aid,
            "google_ads",
            native["connection_id"],
            native["connection_version"],
        )
        assert allocation.target.provider_reference.advertiser_id == "1234567890"
        assert allocation.target.provider_reference.parent_campaign_id is None
        assert (
            allocation.target.canonical_entity_key
            == targets[allocation.target.provider_reference.entity_id]["canonical_entity_key"]
        )
    assert [a.amount_micros for a in alternative.allocations] == [300_000_000, 200_000_000]
    assert alternative.ceiling_micros == 1_000_000_000
    assert (
        sum(a.amount_micros for a in alternative.allocations) + alternative.unallocated_micros
        == alternative.ceiling_micros
    )
    assert alternative.semantics == "independent_alternative" and alternative.forecast is None
    assert all(a.native_budget is None and not a.proposed_fields for a in doc.actions)
    assert (
        "No native budget change or forecast is qualified by this descriptive policy."
        in doc.limitations
    )
    if partial:
        assert any("catalog coverage is partial" in s for s in doc.section_limitations)
    assert doc.spending_authority == "none" and not doc.advertising_writes_enabled
    count = len(calls)
    replay = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert replay.status_code == 200 and replay.json() == generated.json(), replay.text
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["document"] == document, current.text
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == document, exported.text
    assert exported.json()["document_digest"] == doc.digest()
    assert len(calls) == count and financial_counts(customer_engine) == effects
    assert alice.cookies[SESSION_COOKIE] == original_session
    prefix = f"q06-{customer_engine.dialect.name}-{'partial' if partial else 'complete'}"
    manifest = {}
    for label, value in (("catalog", catalog), ("document", document), ("export", exported.json())):
        path = tmp_path / f"{prefix}-{label}.json"
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / f"{prefix}-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
