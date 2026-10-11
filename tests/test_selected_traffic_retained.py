"""Actual range/selected SQL evidence bound into retained proof and historical rows."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from app.ads.models import DailyMetric
from app.campaign_performance.presence_models import MetricPresenceRow
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.lifecycle.export_serializers import serialize
from app.planning_documents import repository
from app.planning_documents import selected_plan_retained as retained
from app.planning_documents.actions import BudgetScenario
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow, PlanInputRow, PlanRow, PlanVersionRow
from app.planning_documents.retained_sources import RetainedSourcesChanged
from app.planning_documents.selected_plan_history import validate_selected_plan_history
from app.planning_documents.selected_plan_witnesses import capture_selected_retained_sources
from app.planning_documents.selected_traffic import RawRangeTrafficGraphV1
from app.planning_documents.selected_traffic_reader import load_raw_range_traffic
from app.planning_documents.storage import canonical
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, update
from sqlalchemy.orm import Session

from tests.selected_range_plan_fixture import prepared_range_plan
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("damage", ["receipt", "sidecar"])
def test_current_proof_contains_actual_traffic_and_second_read_guards(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    reader, ticket, f, _, _ = prepared_range_plan(
        customer_engine, configuration, replicas, monkeypatch
    )
    ref = ticket.inputs.accounts[0]
    selector = ticket.inputs.selected_reporting[0]
    with Session(customer_engine) as db, db.begin():
        proof = retained.capture_selected_reporting_pin(
            db, reader.principal, ref, ticket.privacy_revision, selector, datetime.now(UTC)
        )
        assert proof.capture_pin is not None and proof.traffic_pin is not None
        graph = load_raw_range_traffic(
            db, account=ref, expected_source=proof.source_fence, selected_pin=proof.capture_pin
        )
        assert isinstance(graph, RawRangeTrafficGraphV1)
        assert graph.pin() == proof.traffic_pin
        absent = retained.capture_selected_reporting_pin(
            db, reader.principal, ref, ticket.privacy_revision, None, datetime.now(UTC)
        )
        assert absent.traffic_pin is None and "traffic_pin" not in absent.model_dump()
    calls = 0

    def race(db: Session, **kwargs: Any) -> Any:
        nonlocal calls
        value = load_raw_range_traffic(db, **kwargs)
        calls += 1
        if calls == 1:
            db.execute(delete(RangeReceiptRow if damage == "receipt" else MetricPresenceRow))
        return value

    monkeypatch.setattr(retained, "load_raw_range_traffic", race)
    with Session(customer_engine) as db, db.begin():
        with pytest.raises((HTTPException, ValueError, RetainedSourcesChanged)):
            retained.capture_selected_reporting_pin(
                db, reader.principal, ref, ticket.privacy_revision, selector, datetime.now(UTC)
            )
        db.rollback()
    assert calls == 1


def stored(
    engine: Engine, config: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> PlanVersion:
    reader, ticket, _, _, _ = prepared_range_plan(engine, config, replicas, monkeypatch)
    bundle = reader.collect(ticket)
    # Explicit manual retention fixture, not a registered/commercial v4 composer.
    inputs = ticket.inputs.model_copy(update={"plan_id": uuid4().hex})
    assert not inputs.fixed_allocations and not inputs.scenario_intents
    refs = tuple(x.reference for x in (*bundle.catalogs, *bundle.performance, *bundle.context))
    if bundle.commerce is not None:
        refs += (bundle.commerce.reference,)
    document = PlanVersion(
        inputs=inputs,
        version=1,
        parent_digest=None,
        generator_version=reader.policy.generator_version,
        policy_version=reader.policy.version,
        readiness="needs_input",
        section_limitations=("Manual historical validation fixture",),
        generated_by=ticket.actor_id,
        generated_at=datetime.now(UTC),
        valid_until=min(x.expires_at for x in refs),
        evidence=refs,
        actions=(),
        briefs=(),
        scenarios=(
            BudgetScenario(
                key="unallocated",
                title="Unallocated",
                period=inputs.budget_period,
                ceiling_micros=inputs.total_ceiling_micros,
                allocations=(),
                unallocated_micros=inputs.total_ceiling_micros,
                assumptions=(),
            ),
        ),
        summary="Retained proof test",
        limitations=("No composer or runtime qualification",),
        selected_reporting_proof=bundle.reporting_proof,
    )
    assert document.selected_reporting_proof is not None
    assert document.selected_reporting_proof.accounts[0].traffic_pin is not None
    with Session(engine) as db, db.begin():
        witnesses = capture_selected_retained_sources(
            db, principal=reader.principal, document=document, now=datetime.now(UTC)
        )
        db.add(
            PlanRow(
                workspace_id=inputs.workspace_id,
                id=inputs.plan_id,
                input_head=1,
                version_head=1,
                event_sequence=0,
                created_by=inputs.created_by,
                created_at=inputs.created_at,
            )
        )
        db.flush()
        db.add(
            PlanInputRow(
                workspace_id=inputs.workspace_id,
                plan_id=inputs.plan_id,
                revision=1,
                goal_id=inputs.goal.goal_id,
                goal_revision=inputs.goal.revision,
                confirmed_preview_id=inputs.goal.confirmation_reference,
                definition_digest=inputs.goal.definition_digest,
                canonical_json=canonical(inputs),
                digest=inputs.digest(),
                actor_id=inputs.created_by,
                created_at=inputs.created_at,
            )
        )
        db.flush()
        db.add(
            PlanVersionRow(
                workspace_id=inputs.workspace_id,
                plan_id=inputs.plan_id,
                version=1,
                input_revision=1,
                parent_digest=None,
                canonical_json=canonical(document),
                digest=document.digest(),
                generator_version=document.generator_version,
                policy_version=document.policy_version,
                actor_id=document.generated_by,
                generated_at=document.generated_at,
                valid_until=document.valid_until,
                privacy_revision=ticket.privacy_revision,
            )
        )
        db.flush()
        for ref in refs:
            db.add(
                PlanDependencyRow(
                    workspace_id=inputs.workspace_id,
                    plan_id=inputs.plan_id,
                    version=1,
                    evidence_key=ref.key,
                    account_id=ref.account.account_id if ref.account else None,
                    connection_id=ref.account.connection_id if ref.account else None,
                    store_id=inputs.goal.definition.store_id
                    if ref.kind == "shopify_measurement"
                    else None,
                    kind=ref.kind,
                    source_binding_digest=ref.source_binding_digest,
                    document_digest=ref.document_digest,
                    source_revision=ref.source_revision,
                    observed_at=ref.observed_at,
                    expires_at=ref.expires_at,
                    privacy_revision=ref.privacy_revision,
                )
            )
        db.add_all(PlanDependencyRow(**w.model_dump()) for w in witnesses)
    return document


@pytest.mark.parametrize("damage", ["receipt", "sidecar"])
def test_retained_history_validates_traffic_after_exact_rows_and_dependencies(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    document = stored(customer_engine, configuration, replicas, monkeypatch)
    with Session(customer_engine) as db, db.begin():
        validate_selected_plan_history(db, document)
        plan = db.get(PlanRow, (document.inputs.workspace_id, document.inputs.plan_id))
        assert plan
        row, actual = repository.version(db, plan)
        assert actual == document
        exported, missing = serialize("planning_document_versions", repository.values(row), db=db)
        assert exported and not missing
        from app.planning_documents import selected_plan_history as history

        def auth_error(*args: Any, **kwargs: Any) -> None:
            raise HTTPException(403, "fixture authorization denial")

        with monkeypatch.context() as patch:
            patch.setattr(history, "validate_historical_raw_range_traffic", auth_error)
            with pytest.raises(HTTPException) as denied:
                validate_selected_plan_history(db, document)
            assert denied.value.status_code == 403
    # Immutable history is not invalidated by rewritten current aggregate metric cells.
    with Session(customer_engine) as db, db.begin():
        db.execute(update(DailyMetric).values(clicks=123))
    with Session(customer_engine) as db, db.begin():
        validate_selected_plan_history(db, document)
    with Session(customer_engine) as db, db.begin():
        db.execute(delete(RangeReceiptRow if damage == "receipt" else MetricPresenceRow))
    with Session(customer_engine) as db, db.begin():
        with pytest.raises(ValueError, match="historical traffic integrity unavailable"):
            validate_selected_plan_history(db, document)
        plan = db.get(PlanRow, (document.inputs.workspace_id, document.inputs.plan_id))
        assert plan
        with pytest.raises(HTTPException) as denied:
            repository.version(db, plan)
        assert denied.value.status_code == 409
        retained_row = db.get(
            PlanVersionRow,
            (document.inputs.workspace_id, document.inputs.plan_id, document.version),
        )
        assert retained_row
        with pytest.raises(ValueError, match="historical traffic integrity unavailable"):
            serialize("planning_document_versions", repository.values(retained_row), db=db)
