"""Actual V2 HTTP receipt→customer selection→owned generation without native rereads."""

from typing import Any

import pytest
from app.api import customer_planning_documents, customer_planning_target_catalog
from app.planning_documents.catalog_receipt_models import CatalogReceiptRow, InputCatalogReceiptRow
from app.planning_documents.models import PlanVersionRow
from app.publication.execution_models import ProviderExecutionAttempt
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("selection", ["allocation", "exclusion"])
def test_original_catalog_selection_survives_new_observation_and_generation(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    selection: str,
) -> None:
    _, ticket, _, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    alice.app.include_router(customer_planning_documents.router)
    wid = ticket.inputs.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}/planning"
    query = dict(
        account_id=ticket.inputs.accounts[0].account_id,
        starts_at=ticket.inputs.reporting_window.starts_at.isoformat(),
        ends_at=ticket.inputs.reporting_window.ends_at_exclusive.isoformat(),
    )
    first = alice.post(root + "/target-catalog-v2", headers=headers(alice), json=query)
    assert first.status_code == 200, first.text
    original = first.json()
    second = alice.post(root + "/target-catalog-v2", headers=headers(alice), json=query)
    assert second.status_code == 200, second.text
    target = original["targets"][0]
    observed_again = next(
        t
        for t in second.json()["targets"]
        if t["canonical_entity_key"] == target["canonical_entity_key"]
    )
    assert target["selection_key"] != observed_again["selection_key"]
    selected = {key: target[key] for key in ("canonical_entity_key", "selection_key")}
    selected["account_id"] = query["account_id"]
    body = create_body(ticket.inputs)
    if selection == "allocation":
        body["inputs"]["fixed_allocations"] = [{"target": selected, "amount_micros": 0}]
    else:
        body["inputs"]["exclusions"] = [selected]
    native_count = len(calls)
    created = alice.post(root + "/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    assert len(calls) == native_count
    plan_id = created.json()["plan_id"]
    url = root + "/plans/" + plan_id
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            request_key="exact-target-generate",
            expected_input_revision=1,
            expected_version=0,
        ),
    )
    assert generated.status_code == 200, generated.text
    assert len(calls) == native_count, "targeted generation must reuse exact receipt"
    assert generated.json()["document"]["inputs"] == created.json()["inputs"]
    if selection == "allocation":
        allocation = generated.json()["document"]["inputs"]["fixed_allocations"][0]
        assert allocation["target"]["selection_key"] == target["selection_key"]
    else:
        assert generated.json()["document"]["inputs"]["excluded_entity_keys"] == [
            target["canonical_entity_key"]
        ]
    replay = alice.post(root + "/plans", headers=headers(alice), json=body)
    assert replay.status_code == 201 and replay.json() == created.json()
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CatalogReceiptRow)) == 2
        assert db.scalar(select(func.count()).select_from(InputCatalogReceiptRow)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
    login(alice, "goal-progress:new-session")
    historical = alice.get(url)
    assert historical.status_code == 200, historical.text
    denied = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            request_key="new-session-generation",
            expected_input_revision=1,
            expected_version=1,
        ),
    )
    assert denied.status_code == 409, denied.text
    assert len(calls) == native_count
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1


def test_v2_receipt_identity_and_native_io_run_outside_sql_transactions(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx
    from app.collectors import account_diagnostics
    from sqlalchemy import event

    _, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    alice, _, provider = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    transactions: set[int] = set()
    active = False
    external: list[str] = []

    def begin(connection: Any) -> None:
        transactions.add(id(connection))

    def end(connection: Any) -> None:
        transactions.discard(id(connection))

    event.listen(customer_engine, "begin", begin)
    event.listen(customer_engine, "commit", end)
    event.listen(customer_engine, "rollback", end)
    from app.planning_documents.catalog_runtime import read_catalog_receipt

    original_runtime = read_catalog_receipt
    original_check = provider.check_active
    original_transport = account_diagnostics.diagnostic_transport

    def runtime(*args: Any, **kwargs: Any) -> Any:
        nonlocal active
        assert not transactions, "route authentication transaction must be released"
        active = True
        try:
            return original_runtime(*args, **kwargs)
        finally:
            active = False

    def check(subject: str, authenticated_at: int) -> None:
        if active:
            assert not transactions, "planning identity IO cannot span SQL transactions"
            external.append("identity")
        original_check(subject, authenticated_at)

    class Transport(httpx.BaseTransport):
        def __init__(self) -> None:
            self.inner = original_transport()
            assert self.inner is not None

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            assert active and not transactions, "native IO cannot span SQL transactions"
            external.append("native")
            assert self.inner is not None
            return self.inner.handle_request(request)

        def close(self) -> None:
            assert self.inner is not None
            self.inner.close()

    monkeypatch.setattr(customer_planning_target_catalog, "read_catalog_receipt", runtime)
    monkeypatch.setattr(provider, "check_active", check)
    monkeypatch.setattr(account_diagnostics, "diagnostic_transport", Transport)
    try:
        response = alice.post(
            f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/target-catalog-v2",
            headers=headers(alice),
            json=dict(
                account_id=ticket.inputs.accounts[0].account_id,
                starts_at=ticket.inputs.reporting_window.starts_at.isoformat(),
                ends_at=ticket.inputs.reporting_window.ends_at_exclusive.isoformat(),
            ),
        )
        assert response.status_code == 200, response.text
        assert {"identity", "native"} <= set(external)
    finally:
        event.remove(customer_engine, "begin", begin)
        event.remove(customer_engine, "commit", end)
        event.remove(customer_engine, "rollback", end)


def test_targeted_account_reuses_receipt_while_other_account_reads_normally(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    import httpx
    from app.ads.enums import AdvertisingPlatform
    from app.ads.models import AdvertisingAccount
    from app.collectors import account_diagnostics
    from app.meta.models import MetaConnection
    from app.meta.security import Vault
    from app.settings import settings
    from app.workspaces.models import WorkspaceIntegration

    from tests.test_meta_native_inventory import PRIVATE, Server

    _, ticket, _, google_calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    alice.app.include_router(customer_planning_documents.router)
    wid = ticket.inputs.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}/planning"
    observed = alice.post(
        root + "/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=ticket.inputs.accounts[0].account_id,
            starts_at=ticket.inputs.reporting_window.starts_at.isoformat(),
            ends_at=ticket.inputs.reporting_window.ends_at_exclusive.isoformat(),
        ),
    )
    assert observed.status_code == 200, observed.text
    with Session(customer_engine) as db:
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="mixed-meta",
            provider="meta_ads",
            display_name="Second Owned Account",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform.META_ADS,
            external_account_id="123",
            name="Owned Meta Account",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        aid = account.id
        db.add(
            MetaConnection(
                workspace_id=wid,
                workspace_integration_id=integration.id,
                account_id=aid,
                external_account_id="123",
                encrypted_credentials=Vault(settings).seal(
                    wid,
                    "123",
                    dict(
                        access_token=PRIVATE,
                        expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    ),
                ),
            )
        )
        db.commit()
    old_transport = account_diagnostics.diagnostic_transport
    server = Server()
    meta_calls: list[str] = []

    def wire(request: httpx.Request) -> httpx.Response:
        if request.url.host == "graph.facebook.com":
            meta_calls.append(request.url.path)
            if "name" in request.url.params.get("fields", "").split(","):
                rows = server.adsets if request.url.path.endswith("adsets") else server.campaigns
                return httpx.Response(
                    200, json={"data": [{**r, "name": "Owned Meta Target"} for r in rows]}
                )
            return server(request)
        transport = old_transport()
        assert transport is not None
        with transport:
            return transport.handle_request(request)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    body = create_body(ticket.inputs)
    target = observed.json()["targets"][0]
    body["inputs"]["account_ids"].append(aid)
    body["inputs"]["exclusions"] = [
        dict(
            account_id=ticket.inputs.accounts[0].account_id,
            canonical_entity_key=target["canonical_entity_key"],
            selection_key=target["selection_key"],
        )
    ]
    created = alice.post(root + "/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    before = len(google_calls)
    result = alice.post(
        root + "/plans/" + created.json()["plan_id"] + "/generate",
        headers=headers(alice),
        json=dict(
            request_key="mixed-account-generation", expected_input_revision=1, expected_version=0
        ),
    )
    assert result.status_code == 200, result.text
    assert len(google_calls) == before and meta_calls
    catalogs = [e for e in result.json()["document"]["evidence"] if e["kind"] == "native_catalog"]
    assert {e["account"]["account_id"] for e in catalogs} == {
        ticket.inputs.accounts[0].account_id,
        aid,
    }


def test_postgres_same_key_targeted_create_race_keeps_one_binding(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, local

    from app.planning_documents import authority
    from app.planning_documents.models import PlanInputRow, PlanRow
    from app.planning_documents.requests import CreatePlan
    from app.planning_documents.service import PlanningDocumentService

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency qualification")
    _, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    alice, _, provider = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    response = alice.post(
        f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=ticket.inputs.accounts[0].account_id,
            starts_at=ticket.inputs.reporting_window.starts_at.isoformat(),
            ends_at=ticket.inputs.reporting_window.ends_at_exclusive.isoformat(),
        ),
    )
    assert response.status_code == 200, response.text
    body = create_body(ticket.inputs)
    target = response.json()["targets"][0]
    body["inputs"]["exclusions"] = [
        dict(
            account_id=ticket.inputs.accounts[0].account_id,
            canonical_entity_key=target["canonical_entity_key"],
            selection_key=target["selection_key"],
        )
    ]
    request = CreatePlan.model_validate(body)
    barrier = Barrier(2)
    counts = local()
    refresh = authority.refresh

    def synchronized(*args: Any, **kwargs: Any) -> Any:
        counts.value = getattr(counts, "value", 0) + 1
        if counts.value == 2:
            barrier.wait(timeout=15)
        return refresh(*args, **kwargs)

    monkeypatch.setattr(authority, "refresh", synchronized)

    def create() -> Any:
        return PlanningDocumentService(customer_engine, provider).create(
            principal, ticket.inputs.workspace_id, request
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create(), range(2)))
    assert results[0] == results[1]
    with Session(customer_engine) as db:
        for model in (PlanRow, PlanInputRow, InputCatalogReceiptRow):
            assert db.scalar(select(func.count()).select_from(model)) == 1
