"""Routine customer/source changes are controlled errors, not lost retained history."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.commerce.models import CommerceStore
from app.planning_documents.models import PlanInputRow, PlanRequestRow, PlanRow
from app.planning_documents.requests import (
    AssertionIntent,
    CreatePlan,
    CustomerInputs,
    DecisionIntent,
    GeneratePlan,
    ScenarioIntent,
)
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def ready(engine: Engine, config: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    _, ticket, principal, calls = setup_evidence(engine, config, replicas, monkeypatch, "meta_ads")
    source = ticket.inputs
    intent = CustomerInputs(
        goal_id=source.goal.goal_id,
        goal_revision=source.goal.revision,
        account_ids=tuple(a.account_id for a in source.accounts),
        reporting_window=source.reporting_window,
        comparison_window=None,
        milestone=source.milestone,
        product_offer=None,
        constraints=(),
        assumptions=(),
        exclusions=(),
        fixed_allocations=(),
        scenario_intents=(),
    )
    return PlanningDocumentService(engine, replicas[2]), principal, source, intent, calls


@pytest.mark.parametrize("changed", ["store", "integration"])
def test_disconnected_commerce_preserves_history_and_denies_new_mutations(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    changed: str,
) -> None:
    service, principal, source, intent, calls = ready(
        customer_engine, configuration, replicas, monkeypatch
    )
    wid = source.workspace_id
    created = service.create(
        principal, wid, CreatePlan(inputs=intent, request_key="create-error-01")
    )
    generated = service.generate(
        principal,
        wid,
        created.plan_id,
        GeneratePlan(
            expected_input_revision=1, expected_version=0, request_key="generate-error-01"
        ),
    )
    action = generated.document.actions[0]
    reported = service.assert_applied(
        principal,
        wid,
        created.plan_id,
        AssertionIntent(
            expected_version=1,
            expected_event_sequence=0,
            document_digest=generated.document.digest(),
            action_key=action.key,
            action_digest=action.digest(),
            assertion="customer_reports_applied",
            reported_applied_at=datetime.now(UTC),
            statement="Customer report",
            supersedes_event_id=None,
            request_key="report-error-01",
        ),
    )
    before = len(calls)
    with Session(customer_engine) as db, db.begin():
        store = db.get(CommerceStore, source.goal.definition.store_id)
        assert store is not None
        if changed == "store":
            store.status = "disconnected"
        else:
            integration = db.get(WorkspaceIntegration, store.connection_id)
            assert integration is not None
            integration.status = "inactive"
    read = service.read(principal, wid, created.plan_id)
    assert read.freshness == "goal_changed" and read.document == generated.document
    assert service.export(principal, wid, created.plan_id, 1) == read
    with pytest.raises(HTTPException) as generation:
        service.generate(
            principal,
            wid,
            created.plan_id,
            GeneratePlan(
                expected_input_revision=1, expected_version=1, request_key="new-generation-error"
            ),
        )
    assert generation.value.status_code == 409
    with pytest.raises(HTTPException) as decision:
        service.decide(
            principal,
            wid,
            created.plan_id,
            DecisionIntent(
                expected_version=1,
                expected_event_sequence=1,
                document_digest=generated.document.digest(),
                action_key=action.key,
                action_digest=action.digest(),
                decision="deferred",
                reason="Review",
                supersedes_event_id=None,
                request_key="new-decision-error",
            ),
        )
    assert decision.value.status_code == 409
    withdrawn = service.assert_applied(
        principal,
        wid,
        created.plan_id,
        AssertionIntent(
            expected_version=1,
            expected_event_sequence=1,
            document_digest=generated.document.digest(),
            action_key=action.key,
            action_digest=action.digest(),
            assertion="retracted",
            reported_applied_at=None,
            statement="Withdraw report",
            supersedes_event_id=reported.event.event_id,
            request_key="withdraw-error-01",
        ),
    )
    assert withdrawn.event_sequence == 2 and len(calls) == before


@pytest.mark.parametrize("changed", ["future", "overlap", "budget", "duplicate_scenario"])
def test_customer_resolution_errors_are_422_and_atomic(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    changed: str,
) -> None:
    service, principal, source, intent, _ = ready(
        customer_engine, configuration, replicas, monkeypatch
    )
    values = intent.model_dump(mode="python")
    if changed == "future":
        values["reporting_window"] = dict(
            starts_at=datetime.now(UTC) + timedelta(days=1),
            ends_at_exclusive=datetime.now(UTC) + timedelta(days=2),
        )
    elif changed == "overlap":
        values["comparison_window"] = intent.reporting_window
    else:
        scenario = ScenarioIntent(
            key="option",
            title="Independent Option",
            allocations=(),
            unallocated_micros=source.total_ceiling_micros
            if changed == "duplicate_scenario"
            else source.total_ceiling_micros + 1,
        )
        values["scenario_intents"] = (
            (scenario, scenario) if changed == "duplicate_scenario" else (scenario,)
        )
    invalid = CustomerInputs.model_validate(values)
    with pytest.raises(HTTPException) as error:
        service.create(
            principal,
            source.workspace_id,
            CreatePlan(inputs=invalid, request_key="invalid-input-01"),
        )
    assert error.value.status_code == 422
    with Session(customer_engine) as db:
        for model in (PlanRow, PlanInputRow, PlanRequestRow):
            assert db.scalar(select(func.count()).select_from(model)) == 0
