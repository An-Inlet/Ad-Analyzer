"""Three owned platforms, actual receipt APIs and independently reconciled hypotheses."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.api import customer_planning_documents, customer_planning_target_catalog
from app.collectors import account_diagnostics
from app.meta.models import MetaConnection
from app.meta.security import Vault
from app.planning_documents.catalog_receipt_models import InputCatalogReceiptRow
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_meta_native_inventory import PRIVATE
from tests.test_meta_native_inventory import Server as MetaServer
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_native_inventory import Server as TikTokServer

pytestmark = pytest.mark.planning_boundary
MICROS = 1_000_000


def add_social_accounts(engine: Engine, wid: int) -> list[int]:
    """Owned connection fixtures only; no synthetic planning or execution documents."""
    identifiers = []
    with Session(engine) as db, db.begin():
        for platform in ("meta_ads", "tiktok_ads"):
            connection = WorkspaceIntegration(
                workspace_id=wid,
                integration_key=platform,
                provider=platform,
                display_name="Owned Alternative Account",
                status="active",
                configuration={},
            )
            db.add(connection)
            db.flush()
            account = AdvertisingAccount(
                workspace_id=wid,
                connection_id=connection.id,
                platform=AdvertisingPlatform(platform),
                external_account_id="123",
                name="Owned Alternative Account",
                currency_code="USD",
                time_zone="UTC",
            )
            db.add(account)
            db.flush()
            identifiers.append(account.id)
            grant = dict(
                access_token=PRIVATE,
                expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            )
            if platform == "meta_ads":
                db.add(
                    MetaConnection(
                        workspace_id=wid,
                        workspace_integration_id=connection.id,
                        account_id=account.id,
                        external_account_id="123",
                        encrypted_credentials=Vault(settings).seal(wid, "123", grant),
                    )
                )
            else:
                sid = uuid4().hex
                db.add(
                    SourceConnection(
                        id=sid,
                        workspace_id=wid,
                        integration_id=connection.id,
                        account_id=account.id,
                        provider=platform,
                        external_id="123",
                        status="connected",
                        generation=1,
                        window_start=(datetime.now(UTC) - timedelta(days=2)).date(),
                        window_end=(datetime.now(UTC) - timedelta(days=2)).date(),
                        encrypted_grant=SourceVault().seal(wid, platform, sid, grant),
                    )
                )
    return identifiers


def test_actual_three_platform_customer_alternatives_and_atomic_rejections(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ticket, _, google_calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    alice.app.include_router(customer_planning_documents.router)
    wid = ticket.inputs.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}"
    aids = [ticket.inputs.accounts[0].account_id, *add_social_accounts(customer_engine, wid)]
    transport_factory = account_diagnostics.diagnostic_transport
    meta, tiktok = MetaServer(), TikTokServer()
    social_calls: list[tuple[str, str]] = []

    def wire(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host not in {"graph.facebook.com", "business-api.tiktok.com"}:
            transport = transport_factory()
            assert transport is not None
            with transport:
                return transport.handle_request(request)
        social_calls.append((host, request.method))
        fields = request.url.params.get("fields", "")
        named = "name" in fields.split(",") or "campaign_name" in fields or "adgroup_name" in fields
        if host == "graph.facebook.com":
            if not named:
                return meta(request)
            rows = meta.adsets if request.url.path.endswith("adsets") else meta.campaigns
            return httpx.Response(200, json={"data": [{**r, "name": "Owned Target"} for r in rows]})
        data = tiktok(request).json()
        if named:
            for row in data["data"]["list"]:
                row["adgroup_name" if "adgroup/get" in request.url.path else "campaign_name"] = (
                    "Owned Target"
                )
        return httpx.Response(200, json=data)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    # Actual customer goal edit/preview/confirmation, not a changed ticket or forged basis.
    goal_url = root + "/goals/" + ticket.inputs.goal.goal_id
    original = alice.get(goal_url)
    assert original.status_code == 200, original.text
    definition = {**original.json()["definition"], "budget_micros": 1000 * MICROS}
    edited = alice.put(
        goal_url,
        headers=headers(alice),
        json={
            "expected_revision": original.json()["revision"],
            "definition": definition,
        },
    )
    assert edited.status_code == 200, edited.text
    revision = edited.json()["revision"]
    preview = alice.post(
        goal_url + "/preview",
        headers=headers(alice),
        json={
            "expected_revision": revision,
        },
    )
    assert preview.status_code == 200, preview.text
    confirmed = alice.post(
        goal_url + "/confirm",
        headers=headers(alice),
        json={
            "expected_revision": revision,
            "preview_id": preview.json()["preview_id"],
            "idempotency_key": "alternatives-confirm",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["assessment"] == "confirmed"
    selectors = []
    for aid in aids:
        response = alice.post(
            root + "/planning/target-catalog-v2",
            headers=headers(alice),
            json={
                "account_id": aid,
                "starts_at": ticket.inputs.reporting_window.starts_at.isoformat(),
                "ends_at": ticket.inputs.reporting_window.ends_at_exclusive.isoformat(),
            },
        )
        assert response.status_code == 200, response.text
        target = next(t for t in response.json()["targets"] if t["entity"]["kind"] == "campaign")
        selectors.append(
            dict(
                account_id=aid,
                canonical_entity_key=target["canonical_entity_key"],
                selection_key=target["selection_key"],
            )
        )
    body = create_body(ticket.inputs)
    body["inputs"].update(goal_revision=revision, account_ids=aids, maximum_creative_assets=0)
    body["inputs"]["scenario_intents"] = [
        dict(
            key=key,
            title=key,
            unallocated_micros=100 * MICROS,
            allocations=[
                dict(target=target, amount_micros=amount * MICROS)
                for target, amount in zip(selectors, amounts, strict=True)
            ],
        )
        for key, amounts in (("option_a", (400, 300, 200)), ("option_b", (300, 400, 200)))
    ]
    plans = root + "/planning/plans"
    graph = (
        PlanRow,
        PlanInputRow,
        PlanVersionRow,
        PlanDependencyRow,
        PlanEventRow,
        PlanRequestRow,
        InputCatalogReceiptRow,
        ProviderExecutionRun,
        ProviderExecutionAttempt,
    )
    for invalid in ("over_ceiling", "negative", "fixed_mismatch"):
        broken = deepcopy(body)
        broken["request_key"] = "invalid-" + invalid
        if invalid == "over_ceiling":
            broken["inputs"]["scenario_intents"][0]["allocations"][1]["amount_micros"] = (
                400 * MICROS
            )
        elif invalid == "negative":
            broken["inputs"]["scenario_intents"][0]["allocations"][0]["amount_micros"] = -1
        else:
            broken["inputs"]["fixed_allocations"] = [
                dict(target=selectors[0], amount_micros=400 * MICROS)
            ]  # option_b contradicts this fixed amount even though both sums reconcile.
        rejected = alice.post(plans, headers=headers(alice), json=broken)
        assert rejected.status_code == 422, (invalid, rejected.text)
        with Session(customer_engine) as db:
            for model in graph:
                assert db.scalar(select(func.count()).select_from(model)) == 0, (invalid, model)
    created = alice.post(plans, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    calls_before = (len(google_calls), len(social_calls))
    generated = alice.post(
        plans + "/" + created.json()["plan_id"] + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=1,
            expected_version=0,
            request_key="alternatives-generate",
        ),
    )
    assert generated.status_code == 200, generated.text
    assert (len(google_calls), len(social_calls)) == calls_before
    document = generated.json()["document"]
    assert document["inputs"]["total_ceiling_micros"] == 1000 * MICROS
    assert document["inputs"]["goal"]["revision"] == revision
    alternatives = {
        s["customer_intent_key"]: s
        for s in document["scenarios"]
        if s["provenance"] == "customer_supplied_hypothesis"
    }
    assert set(alternatives) == {"option_a", "option_b"}
    for key, amounts in (("option_a", (400, 300, 200)), ("option_b", (300, 400, 200))):
        scenario = alternatives[key]
        assert [a["amount_micros"] for a in scenario["allocations"]] == [
            a * MICROS for a in amounts
        ]
        assert [a["target"]["account"]["platform"] for a in scenario["allocations"]] == [
            "google_ads",
            "meta_ads",
            "tiktok_ads",
        ]
        assert [a["target"]["selection_key"] for a in scenario["allocations"]] == [
            s["selection_key"] for s in selectors
        ]
        assert (
            sum(a["amount_micros"] for a in scenario["allocations"])
            + scenario["unallocated_micros"]
            == 1000 * MICROS
        )
        assert scenario["unallocated_micros"] == 100 * MICROS
        assert scenario["semantics"] == "independent_alternative"
        assert scenario["native_conversion"] == "not_assessed" and scenario["forecast"] is None
        assert (
            scenario["spending_authority"] == "none" and not scenario["advertising_writes_enabled"]
        )
    assert document["spending_authority"] == "none" and not document["advertising_writes_enabled"]
    assert all(action["native_budget"] is None for action in document["actions"])
    assert (
        "Provider reports do not establish causal lift, unique customers or future sales."
        in document["limitations"]
    )
    assert all(method == "GET" for _, method in social_calls)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanRow)) == 1
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
        assert db.scalar(select(func.count()).select_from(InputCatalogReceiptRow)) == 3
        for model in (ProviderExecutionRun, ProviderExecutionAttempt):
            assert db.scalar(select(func.count()).select_from(model)) == 0
