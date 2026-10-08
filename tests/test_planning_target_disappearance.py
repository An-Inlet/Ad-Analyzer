"""Fresh inventory changes never silently remap an exact, retained as-of selection."""

from copy import deepcopy
from typing import Any

import httpx
import pytest
from app.api import customer_planning_documents, customer_planning_target_catalog
from app.collectors import account_diagnostics
from app.planning_documents.catalog_receipt_models import InputCatalogReceiptRow
from app.planning_documents.models import PlanInputRow, PlanRow, PlanVersionRow
from app.publication.execution_models import ProviderExecutionAttempt
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_disappearance_and_same_name_replacement_require_exact_reselection(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    _, ticket, _, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    original_transport = account_diagnostics.diagnostic_transport
    mode = "original"

    def wire(request: httpx.Request) -> httpx.Response:
        transport = original_transport()
        assert transport is not None
        with transport:
            response = transport.handle_request(request)
            response.read()
        payload = response.json()
        if platform == "google_ads" and "results" in payload:
            rows = payload["results"]
            if any("campaign" in row for row in rows):
                if mode == "absent":
                    payload["results"] = []
                elif mode == "replacement":
                    for row in rows:
                        row["campaign"]["resourceName"] = "customers/1234567890/campaigns/9"
        elif platform == "meta_ads" and request.url.path.endswith(("/campaigns", "/adsets")):
            if mode == "absent":
                payload["data"] = []
            elif mode == "replacement":
                for row in payload["data"]:
                    if "campaign_id" in row:
                        row["campaign_id"] = "9"
                    else:
                        row["id"] = "9"
        elif platform == "tiktok_ads" and request.url.path.endswith(
            ("/campaign/get/", "/adgroup/get/")
        ):
            if mode == "absent":
                payload["data"]["list"] = []
                payload["data"]["page_info"]["total_number"] = 0
            elif mode == "replacement":
                for row in payload["data"]["list"]:
                    row["campaign_id"] = "9"
        return httpx.Response(response.status_code, json=payload)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    alice.app.include_router(customer_planning_documents.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning"
    aid = ticket.inputs.accounts[0].account_id
    query = dict(
        account_id=aid,
        starts_at=ticket.inputs.reporting_window.starts_at.isoformat(),
        ends_at=ticket.inputs.reporting_window.ends_at_exclusive.isoformat(),
    )

    def observe() -> dict[str, Any]:
        result = alice.post(root + "/target-catalog-v2", headers=headers(alice), json=query)
        assert result.status_code == 200, result.text
        return result.json()  # type: ignore[no-any-return]

    def selector(target: dict[str, Any]) -> dict[str, Any]:
        return dict(
            account_id=aid,
            canonical_entity_key=target["canonical_entity_key"],
            selection_key=target["selection_key"],
        )

    def graph() -> tuple[int, ...]:
        with Session(customer_engine) as db:
            return tuple(
                db.scalar(select(func.count()).select_from(model)) or 0
                for model in (PlanRow, PlanInputRow, PlanVersionRow, InputCatalogReceiptRow)
            )

    original_catalog = observe()
    old = next(t for t in original_catalog["targets"] if t["entity"]["kind"] == "campaign")
    old_id = "1" if platform == "google_ads" else "5"
    assert old["entity"]["reference"]["entity_id"] == old_id
    body = create_body(ticket.inputs)
    body["inputs"]["fixed_allocations"] = [{"target": selector(old), "amount_micros": 0}]
    created = alice.post(root + "/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/plans/" + created.json()["plan_id"]

    # A fresh empty observation is not retroactive invalidation of original as-of evidence.
    mode = "absent"
    missing = observe()
    assert missing["targets"] == []
    before = len(calls)
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(request_key="original-asof", expected_input_revision=1, expected_version=0),
    )
    assert generated.status_code == 200, generated.text
    assert len(calls) == before, "targeted generation must use its exact original receipt"
    old_document = generated.json()["document"]
    assert old_document["inputs"] == created.json()["inputs"]
    old_target = old_document["inputs"]["fixed_allocations"][0]["target"]
    assert old_target["provider_reference"]["entity_id"] == old_id
    assert old_target["selection_key"] == old["selection_key"]

    mode = "replacement"
    replacement_catalog = observe()
    new = next(t for t in replacement_catalog["targets"] if t["entity"]["kind"] == "campaign")
    assert new["entity"]["name"] == old["entity"]["name"]
    assert new["entity"]["reference"]["entity_id"] == "9"
    assert all(
        t["entity"]["reference"]["entity_id"] != old_id for t in replacement_catalog["targets"]
    )
    assert new["canonical_entity_key"] != old["canonical_entity_key"]
    assert new["selection_key"] != old["selection_key"]
    assert all(
        t["entity"]["reference"]["parent_campaign_id"] == "9"
        for t in replacement_catalog["targets"]
        if t["entity"]["kind"] != "campaign"
    )
    current = alice.get(url)
    assert current.status_code == 200, current.text
    assert current.json()["document"] == old_document
    stable_graph = graph()
    before = len(calls)
    for index, (canonical, selection) in enumerate(((old, new), (new, old))):
        invalid = deepcopy(body)
        invalid.update(
            request_key=f"wrong-pair-{index}", expected_input_revision=1, expected_version=1
        )
        invalid["inputs"]["fixed_allocations"][0]["target"] = dict(
            account_id=aid,
            canonical_entity_key=canonical["canonical_entity_key"],
            selection_key=selection["selection_key"],
        )
        denied = alice.post(url + "/inputs", headers=headers(alice), json=invalid)
        assert denied.status_code == 409, denied.text
        assert graph() == stable_graph
    assert len(calls) == before

    edited_body = deepcopy(body)
    edited_body.update(
        request_key="explicit-reselection", expected_input_revision=1, expected_version=1
    )
    edited_body["inputs"]["fixed_allocations"][0]["target"] = selector(new)
    edited = alice.post(url + "/inputs", headers=headers(alice), json=edited_body)
    assert edited.status_code == 200, edited.text
    assert edited.json()["input_revision"] == 2
    successor = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(request_key="replacement-asof", expected_input_revision=2, expected_version=1),
    )
    assert successor.status_code == 200, successor.text
    assert len(calls) == before
    new_target = successor.json()["document"]["inputs"]["fixed_allocations"][0]["target"]
    assert new_target["provider_reference"]["entity_id"] == "9"
    assert new_target["selection_key"] == new["selection_key"]
    assert new_target["canonical_entity_key"] == new["canonical_entity_key"]
    assert alice.get(url + "/versions/1").json()["document"] == old_document
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200, exported.text
    assert exported.json()["document_digest"] == generated.json()["document_digest"]
    assert graph() == (1, 2, 2, 2)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
