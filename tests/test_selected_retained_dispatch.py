"""Exact v4 current-witness dispatch and actual manual-event source gates."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from app.ads.models import DailyMetric
from app.planning_documents import authority, repository
from app.planning_documents import retained_sources as retained
from app.planning_documents.events import CustomerDecision, ManualAssertion
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRow,
    PlanVersionRow,
)
from app.planning_documents.selected_composer import SelectedPlanComposer
from app.planning_documents.selected_paired_reader import OwnedSelectedPairedReader
from app.planning_documents.storage import canonical
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from tests.selected_range_plan_fixture import prepared_range_plan
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def stored(engine: Engine, config: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    reader, ticket, f, _, _ = prepared_range_plan(engine, config, replicas, monkeypatch)
    paired = OwnedSelectedPairedReader(
        lambda: Session(engine),
        principal=reader.principal,
        provider=f.provider,
        policy=reader.policy,
        clock=lambda: datetime.now(UTC),
    )
    bundle = paired.collect(ticket)
    document = SelectedPlanComposer().compose(
        ticket=ticket, evidence=bundle, policy=reader.policy, generated_at=datetime.now(UTC)
    )
    inputs = document.inputs
    refs = document.evidence
    with Session(engine) as db, db.begin():
        witnesses = retained.capture_retained_sources(
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
    return document, reader.principal, f.provider


def dependencies(db: Session, document: Any) -> tuple[PlanDependencyRow, ...]:
    return tuple(
        db.scalars(
            select(PlanDependencyRow).where(
                PlanDependencyRow.workspace_id == document.inputs.workspace_id,
                PlanDependencyRow.plan_id == document.inputs.plan_id,
                PlanDependencyRow.version == document.version,
            )
        )
    )


def test_actual_v4_witness_and_manual_events_fail_closed_on_changed_metrics(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, principal, provider = stored(customer_engine, configuration, replicas, monkeypatch)
    with Session(customer_engine) as db, db.begin():
        retained.recheck_retained_sources(
            db,
            principal=principal,
            document=document,
            dependencies=dependencies(db, document),
            now=datetime.now(UTC),
        )
    action = document.actions[0]
    common = dict(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=document.version,
        document_digest=document.digest(),
        action_key=action.key,
        action_digest=action.digest(),
        actor_id=principal.user.id,
    )
    decision = CustomerDecision(
        **common,
        event_id=uuid4().hex,
        recorded_at=datetime.now(UTC),
        decision="accepted_for_manual_application",
        reason="Actual offline customer review",
        supersedes_event_id=None,
    )
    fact = authority.refresh(principal, provider)
    with Session(customer_engine) as db, db.begin():
        sequence, saved = repository.save_event(
            db,
            principal=principal,
            fact=fact,
            event=decision,
            expected_sequence=0,
            request_key="selected-decision",
            request_digest="1" * 64,
            now=datetime.now(UTC),
        )
        assert sequence == 1 and saved == decision
    assertion_time = datetime.now(UTC)
    assertion = ManualAssertion(
        **common,
        event_id=uuid4().hex,
        recorded_at=datetime.now(UTC),
        assertion="customer_reports_applied",
        statement="Customer reports manual action; no provider operation performed",
        reported_applied_at=assertion_time,
        supersedes_event_id=None,
    )
    fact = authority.refresh(principal, provider)
    with Session(customer_engine) as db, db.begin():
        sequence, saved = repository.save_event(
            db,
            principal=principal,
            fact=fact,
            event=assertion,
            expected_sequence=1,
            request_key="selected-manual",
            request_digest="2" * 64,
            now=datetime.now(UTC),
        )
        assert sequence == 2 and saved == assertion
    with Session(customer_engine) as db, db.begin():
        db.execute(update(DailyMetric).values(clicks=999))
    fact = authority.refresh(principal, provider)
    with Session(customer_engine) as db, db.begin():
        changed = assertion.model_copy(
            update={"event_id": uuid4().hex, "supersedes_event_id": assertion.event_id}
        )
        with pytest.raises(HTTPException) as rejected:
            repository.save_event(
                db,
                principal=principal,
                fact=fact,
                event=changed,
                expected_sequence=2,
                request_key="selected-stale",
                request_digest="3" * 64,
                now=datetime.now(UTC),
            )
        assert rejected.value.status_code == 409
        assert db.scalar(select(func.count()).select_from(PlanEventRow)) == 2


def test_v4_dispatch_error_boundaries_and_mixed_pairs(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.planning_documents import selected_plan_witnesses as selected

    document, principal, _ = stored(customer_engine, configuration, replicas, monkeypatch)
    for status in (401, 402, 403, 409, None):

        def fail(*args: Any, code: int | None = status, **kwargs: Any) -> Any:
            if code is None:
                raise ValueError("fixture invalid proof")
            raise HTTPException(code, "fixture denied")

        with monkeypatch.context() as patch:
            patch.setattr(selected, "capture_selected_retained_sources", fail)
            patch.setattr(selected, "recheck_selected_retained_sources", fail)
            with Session(customer_engine) as db, db.begin():
                for callback in (
                    lambda: retained.capture_retained_sources(
                        db, principal=principal, document=document, now=datetime.now(UTC)
                    ),
                    lambda: retained.recheck_retained_sources(
                        db,
                        principal=principal,
                        document=document,
                        dependencies=dependencies(db, document),
                        now=datetime.now(UTC),
                    ),
                ):
                    if status in (409, None):
                        with pytest.raises(retained.RetainedSourcesChanged) as error:
                            callback()
                        assert error.value.reason == (
                            "source_integrity_unavailable" if status == 409 else "proof_unavailable"
                        )
                    else:
                        with pytest.raises(HTTPException) as denied:
                            callback()
                        assert denied.value.status_code == status
    with Session(customer_engine) as db, db.begin():
        bad = document.model_copy(update={"generator_version": "inlet.descriptive-planning.v3"})
        with pytest.raises((ValueError, retained.RetainedSourcesChanged)):
            retained.capture_retained_sources(
                db, principal=principal, document=bad, now=datetime.now(UTC)
            )
        with pytest.raises(retained.RetainedSourcesChanged):
            retained.recheck_retained_sources(
                db,
                principal=principal,
                document=bad,
                dependencies=dependencies(db, document),
                now=datetime.now(UTC),
            )
