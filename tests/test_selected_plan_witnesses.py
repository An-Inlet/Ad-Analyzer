"""SQL witness integration; assembled no-selection v4 fixture, not v4 generation."""

from datetime import UTC, datetime
from typing import Any

import pytest
from app.ads.models import DailyMetric
from app.customers.models import CustomerMembership
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.retained_sources import RetainedSourcesChanged
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
)
from app.planning_documents.selected_plan_history import validate_selected_historical_dependencies
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1
from app.planning_documents.selected_plan_retained import capture_selected_reporting_pin
from app.planning_documents.selected_plan_witnesses import (
    capture_selected_retained_sources,
    recheck_selected_retained_sources,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_retained_sources import dependencies, prepare
from tests.test_shopify_sales import configuration as configuration


def test_current_selected_witnesses_and_historical_dependency_boundary(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, old, principal, _, _ = prepare(customer_engine, configuration, replicas, monkeypatch)
    with Session(customer_engine) as db, db.begin():
        privacy = old.evidence[0].privacy_revision
        proof = SelectedRetainedProofV1(
            accounts=tuple(
                capture_selected_reporting_pin(
                    db, principal, account, privacy, None, datetime.now(UTC)
                )
                for account in old.inputs.accounts
            )
        )
        document = PlanVersion.model_validate(
            old.model_copy(
                update={
                    "inputs": old.inputs.model_copy(update={"selected_reporting": ()}),
                    "policy_version": SELECTED_POLICY_VERSION,
                    "generator_version": SELECTED_GENERATOR_VERSION,
                    "selected_reporting_proof": proof,
                }
            )
        )
        ordinary = [r for r in dependencies(db, old) if not r.kind.startswith("local_")]
        witnesses = capture_selected_retained_sources(
            db, principal=principal, document=document, now=datetime.now(UTC)
        )
        rows = ordinary + [PlanDependencyRow(**w.model_dump()) for w in witnesses]
        assert {w.kind for w in witnesses} == {"local_reporting_v3", "local_commerce_v1"}
        assert validate_selected_historical_dependencies(document, rows) == ()
        recheck_selected_retained_sources(
            db, principal=principal, document=document, dependencies=rows, now=datetime.now(UTC)
        )
        # Source mutation makes current use fail while immutable history still binds.
        metric = db.scalar(select(DailyMetric))
        assert metric
        db.execute(
            update(DailyMetric)
            .where(DailyMetric.id == metric.id)
            .values(cost_micros=metric.cost_micros + 1)
        )
        with pytest.raises((RetainedSourcesChanged, HTTPException, ValueError)):
            recheck_selected_retained_sources(
                db, principal=principal, document=document, dependencies=rows, now=datetime.now(UTC)
            )
        assert validate_selected_historical_dependencies(document, rows) == ()
        db.rollback()
    # A viewer remains allowed to inspect currentness, but not to write by this port.
    with Session(customer_engine) as db, db.begin():
        db.execute(
            update(CustomerMembership)
            .where(
                CustomerMembership.workspace_id == old.inputs.workspace_id,
                CustomerMembership.user_id == principal.user.id,
            )
            .values(role="viewer")
        )
        assert capture_selected_retained_sources(
            db, principal=principal, document=document, now=datetime.now(UTC)
        )
