"""Configured V6 acceptance: independent owners, exact persistence, bounded scheduling."""

import json
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from app.ads.models import AdvertisingAccount
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.selected_models import SelectedCaptureRow, SelectedFactRow
from app.campaign_review.models import MediaObject
from app.customers.models import CustomerMembership
from app.database.session import Base
from app.main import app
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanRequestRow, PlanRow, PlanVersionRow
from app.planning_documents.requests import CreatePlan, GeneratePlan
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from tests.planning_concurrency_harness import (
    SCENARIOS,
    PassiveBlockingObserver,
    Scenario,
    Size,
    assert_response_contract,
    run_clients,
)
from tests.planning_matrix_fixture import OwnedMatrixPlan, build_pair, scoped_counts
from tests.planning_release_evidence import _CURRENT
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_authority_delay import _source_snapshot
from tests.test_prepared_generation_runtime import trace_preparation
from tests.test_shopify_sales import configuration as configuration


def workload(engine: Engine, plan: OwnedMatrixPlan) -> dict[str, Any]:
    identity = plan.identity
    count = 61 * identity.reporting_campaigns
    with Session(engine) as db:

        def rows(model: Any) -> list[Any]:
            return list(db.scalars(select(model).where(model.workspace_id == plan.workspace)))

        accounts = rows(AdvertisingAccount)
        assert len(accounts) == 1
        completions = rows(PerformanceCompletion)
        assert len(completions) == 1 and completions[0].row_count == count
        assert len(rows(SelectedCaptureRow)) == 1
        assert len(rows(SelectedFactRow)) == count
        assert len(rows(MediaObject)) == identity.owners
        owners = rows(CustomerMembership)
        assert len(owners) == 1 and owners[0].role == "owner"
    inputs = plan.body["inputs"]
    assert len(inputs["google_daily_budget_intents"]) == identity.owners
    assert len(inputs["scenario_intents"]) == 1
    assert len(inputs["scenario_intents"][0]["allocations"]) == identity.owners
    assert len(inputs["creative"]["media_selections"]) == identity.owners
    campaigns = [t for t in plan.catalog["targets"] if t["entity"]["kind"] == "campaign"]
    assert len(campaigns) == identity.native_campaigns
    adgroups = [t for t in plan.catalog["targets"] if t["entity"]["kind"] == "adgroup"]
    assert len(adgroups) == identity.native_campaigns
    budgets = Counter(t["budget_owner_key"] for t in campaigns)
    assert None not in budgets and len(budgets) == 2
    shared = sum(members == 2 for members in budgets.values())
    assert shared == identity.owners
    native = plan.catalog["native_observation"]["targets"]
    assert len(native) == identity.native_campaigns
    assert sum(t["settings"]["budget_explicitly_shared"] is True for t in native) == shared * 2
    return dict(
        size=identity.size,
        accounts=len(accounts),
        reporting_campaigns=identity.reporting_campaigns,
        native_campaigns=identity.native_campaigns,
        native_adgroups=len(adgroups),
        budgets=len(budgets),
        shared_owners=shared,
        owner_intents=identity.owners,
        scenario_allocations=identity.owners,
        owned_images=identity.owners,
        reporting_days=61,
        aggregate_rows=count,
        selected_rows=count,
        captures=1,
        scoped_table_counts=scoped_counts(engine, plan.workspace),
    )


def generate(client: TestClient, plan: OwnedMatrixPlan, key: str) -> Any:
    return client.post(
        plan.url + "/generate",
        headers=headers(client),
        json=dict(
            expected_input_revision=1,
            expected_version=0,
            request_key=key,
        ),
    )


def verify_saved(engine: Engine, plan: OwnedMatrixPlan, response: Any, key: str) -> dict[str, int]:
    document = PlanVersion.model_validate(response.json()["document"])
    assert response.json()["document_digest"] == document.digest()
    assert document.inputs.total_ceiling_micros == 1_000_000_000
    assert document.google_budget_owner_review is not None
    assert len(document.google_budget_owner_review.reviews) == plan.identity.owners
    for review in document.google_budget_owner_review.reviews:
        assert review.intent.requested_amount_micros == 5_000_000
        assert review.application == "unavailable"
        assert len(review.witness.affected_campaigns) == review.witness.reference_count == 2
        assert review.witness.explicitly_shared is True
        assert len(review.witness.model_dump_json().encode()) <= 256 * 1024
    with Session(engine) as db:
        versions = list(
            db.scalars(select(PlanVersionRow).where(PlanVersionRow.workspace_id == plan.workspace))
        )
        assert len(versions) == 1
        row = versions[0]
        assert row.version == 1 and row.input_revision == 1
        assert PlanVersion.model_validate_json(row.canonical_json) == document
        assert row.digest == document.digest()
        head = db.get(PlanRow, (plan.workspace, row.plan_id))
        assert head and head.version_head == 1 and head.input_head == 1
        receipts = list(
            db.scalars(select(PlanRequestRow).where(PlanRequestRow.workspace_id == plan.workspace))
        )
        assert len(receipts) == 2
        generated = [r for r in receipts if r.operation == "generate"]
        assert len(generated) == 1
        created = [r for r in receipts if r.operation == "create"]
        assert len(created) == 1
        assert created[0].request_key == plan.body["request_key"]
        assert created[0].request_digest == CreatePlan.model_validate(plan.body).digest()
        assert (
            created[0].result_kind,
            created[0].input_revision,
            created[0].version,
            created[0].event_sequence,
        ) == ("input", 1, None, None)
        assert created[0].plan_id == row.plan_id
        assert created[0].actor_id == generated[0].actor_id == row.actor_id == head.created_by
        assert (
            generated[0].request_digest
            == GeneratePlan(expected_input_revision=1, expected_version=0, request_key=key).digest()
        )
        assert (
            generated[0].result_kind,
            generated[0].input_revision,
            generated[0].event_sequence,
        ) == ("version", None, None)
        assert generated[0].request_key == key and generated[0].version == 1
        assert generated[0].plan_id == row.plan_id
        document_bytes = len(row.canonical_json.encode())
        assert 0 < document_bytes <= 1024 * 1024
    for suffix in ("/versions/1", "/export?version=1"):
        retained = plan.client.get(plan.url + suffix)
        assert retained.status_code == 200, retained.status_code
        assert PlanVersion.model_validate(retained.json()["document"]) == document
        assert retained.json()["document_digest"] == document.digest()
    return dict(document_bytes=document_bytes, versions=1, generate_receipts=1, create_receipts=1)


def workspace_planning_snapshot(engine: Engine, workspace: int) -> dict[str, tuple[str, ...]]:
    with Session(engine) as db:
        return {
            name: tuple(
                sorted(
                    repr(dict(row))
                    for row in db.execute(
                        select(table).where(table.c.workspace_id == workspace)
                    ).mappings()
                )
            )
            for name, table in sorted(Base.metadata.tables.items())
            if name.startswith("planning_") and "workspace_id" in table.c
        }


def isolation(first: OwnedMatrixPlan, second: OwnedMatrixPlan) -> None:
    assert first.client.get(second.url).status_code == 404
    assert second.client.get(first.url).status_code == 404


@pytest.mark.parametrize("size", ["small", "large"])
def test_workload_inventory(
    customer_engine: Engine,
    configuration: Any,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    size: Size,
) -> None:
    assert _CURRENT.get() is not None, "first-invocation release recorder required"
    with ExitStack() as stack:
        plans = build_pair(
            customer_engine, configuration, replicas, monkeypatch, tmp_path, size, stack
        )
        inventory = [workload(customer_engine, plan) for plan in plans]
        (tmp_path / "workload-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
        for plan in plans:
            plan.create()
        isolation(*plans)
        effects = financial_counts(customer_engine)
        assert effects == (0,) * 6
        sources = [_source_snapshot(customer_engine, p.workspace) for p in plans]
        providers = [p.provider_counts() for p in plans]
        preparations = trace_preparation(monkeypatch)
        for plan, counts in zip(plans, inventory, strict=True):
            response = generate(plan.client, plan, "inventory-generation")
            assert response.status_code == 200, response.status_code
            counts.update(verify_saved(customer_engine, plan, response, "inventory-generation"))
            (tmp_path / "workload-inventory.json").write_text(
                json.dumps(inventory, indent=2) + "\n"
            )
        assert len(preparations) == 2 and all(p[0].snapshots is None for p in preparations)
        isolation(*plans)
        assert financial_counts(customer_engine) == effects
        assert [_source_snapshot(customer_engine, p.workspace) for p in plans] == sources
        assert [p.provider_counts() for p in plans] == providers
        (tmp_path / "workload-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda case: case.key)
def test_release_matrix(
    customer_engine: Engine,
    configuration: Any,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario: Scenario,
) -> None:
    postgres = customer_engine.dialect.name == "postgresql"
    if not postgres and scenario.offset_ms != 0:
        pytest.skip("SQLite parity is sequential and has no arrival offset")
    evidence = _CURRENT.get()
    assert evidence is not None, "first-invocation release recorder required"
    with ExitStack() as stack:
        pair = build_pair(
            customer_engine, configuration, replicas, monkeypatch, tmp_path, scenario.size, stack
        )
        inventory = [workload(customer_engine, plan) for plan in pair]
        (tmp_path / "workload-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
        for plan in pair:
            plan.create()
        isolation(*pair)
        targets = pair if scenario.pattern == "distinct_workspaces" else (pair[0], pair[0])
        clients = []
        for plan in targets:
            client = stack.enter_context(TestClient(app, base_url=str(plan.client.base_url)))
            client.cookies.update(plan.client.cookies)
            clients.append(client)
        providers, effects = [p.provider_counts() for p in pair], financial_counts(customer_engine)
        assert effects == (0,) * 6
        sources = [_source_snapshot(customer_engine, p.workspace) for p in pair]
        untouched = workspace_planning_snapshot(customer_engine, pair[1].workspace)
        preparations = trace_preparation(monkeypatch)
        keys = (
            "matrix-request-0",
            "matrix-request-0" if scenario.pattern == "same_key" else "matrix-request-1",
        )
        overlap_count = incidental_count = 0
        if postgres:
            observer_engine = create_engine(
                customer_engine.url,
                poolclass=NullPool,
                connect_args={"connect_timeout": 1, "options": "-cstatement_timeout=500"},
            )
            stack.callback(observer_engine.dispose)
            observer_connection = stack.enter_context(observer_engine.connect())
            observer_connection = observer_connection.execution_options(
                isolation_level="AUTOCOMMIT"
            )
            with PassiveBlockingObserver(
                customer_engine, observer_connection, evidence
            ) as observer:
                responses = run_clients(
                    lambda: generate(clients[0], targets[0], keys[0]),
                    lambda: generate(clients[1], targets[1], keys[1]),
                    offset_ms=scenario.offset_ms,
                    evidence=evidence,
                )
            overlap_count, incidental_count = len(observer.overlaps), len(observer.incidental)
            arrivals = {
                r["worker"]: r["at"]
                for r in evidence.records
                if r["event"] == "stage_start" and r.get("stage") == "client_arrival"
            }
            assert set(arrivals) == {0, 1}
            actual_offset = arrivals[1] - arrivals[0]
            assert abs(actual_offset - scenario.offset_ms / 1000) <= 1.0
            if scenario.offset_ms:
                assert actual_offset >= scenario.offset_ms / 1000 - 0.005
        else:
            sequential = []
            for worker, (client, plan, key) in enumerate(zip(clients, targets, keys, strict=True)):
                with evidence.worker(worker):
                    response = generate(client, plan, key)
                    evidence.response(worker, response)
                    sequential.append(response)
            responses = (sequential[0], sequential[1])
        scopes = tuple((p.workspace, p.url.rsplit("/", 1)[1]) for p in targets)
        assert_response_contract(scenario, responses, (scopes[0], scopes[1]))
        successful: set[int] = set()
        for plan, response, key in zip(targets, responses, keys, strict=True):
            if response.status_code == 200 and plan.workspace not in successful:
                index = pair.index(plan)
                inventory[index].update(verify_saved(customer_engine, plan, response, key))
                successful.add(plan.workspace)
        if scenario.pattern != "distinct_workspaces":
            with Session(customer_engine) as db:
                assert (
                    db.scalar(
                        select(func.count())
                        .select_from(PlanVersionRow)
                        .where(PlanVersionRow.workspace_id == pair[1].workspace)
                    )
                    == 0
                )
                head = db.get(PlanRow, (pair[1].workspace, pair[1].url.rsplit("/", 1)[1]))
                assert head and head.version_head == 0
        if scenario.pattern != "distinct_workspaces":
            assert workspace_planning_snapshot(customer_engine, pair[1].workspace) == untouched
        assert [_source_snapshot(customer_engine, p.workspace) for p in pair] == sources
        assert preparations and all(p[0].snapshots is None for p in preparations)
        isolation(*pair)
        assert financial_counts(customer_engine) == effects
        assert [p.provider_counts() for p in pair] == providers
        (tmp_path / "matrix-result.json").write_text(
            json.dumps(
                dict(
                    scenario=scenario.key,
                    workload=inventory,
                    final_save_overlaps=overlap_count,
                    incidental_overlaps=incidental_count,
                    preparations=len(preparations),
                ),
                indent=2,
            )
            + "\n"
        )
        if postgres and scenario.requires_overlap:
            assert overlap_count, "required final-save overlap missing; no retry"
