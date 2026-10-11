"""Deliberate real-clock V6 final-publication authority expiry, not a timing benchmark."""

import json
import time
from pathlib import Path
from typing import Any

import pytest
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.selected_models import (
    CurrentEventSelectionRow,
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from app.customers.access import CustomerPrincipal
from app.planning_documents import authority
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow, PlanRequestRow, PlanRow, PlanVersionRow
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_api import generation
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def _source_snapshot(engine: Engine, wid: int) -> tuple[tuple[str, ...], ...]:
    with Session(engine) as db:
        return tuple(
            tuple(
                sorted(
                    repr(dict(row))
                    for row in db.execute(
                        select(model.__table__).where(model.workspace_id == wid)
                    ).mappings()
                )
            )
            for model in (
                CatalogReceiptRow,
                CatalogReceiptSelectionRow,
                InputCatalogReceiptRow,
                RangeReceiptRow,
                EventSelectionRow,
                CurrentEventSelectionRow,
                SelectedCaptureRow,
                SelectedFactRow,
                MetricPresenceRow,
                ReportingSemanticsRow,
            )
        )


def test_v6_real_delay_after_final_flush_rolls_back(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture, body, calls, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    wid = fixture.basis.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    saved = alice.post(root, headers=headers(alice), json=body)
    assert saved.status_code == 201, saved.text
    plan_id = saved.json()["plan_id"]
    before = planning_snapshot(customer_engine), _source_snapshot(customer_engine, wid)
    financial_before = financial_counts(customer_engine)
    assert financial_before == (0, 0, 0, 0, 0, 0)
    provider_before = len(calls), len(fixture.calls)
    flushed: list[bool] = []
    refused: list[bool] = []
    original_flush = Session.flush
    original_final = authority.final
    request = generation()

    def flush(db: Session, *args: Any, **kwargs: Any) -> None:
        pending_receipts = [
            row
            for row in db.new
            if isinstance(row, PlanRequestRow)
            and row.workspace_id == wid
            and row.plan_id == plan_id
            and row.operation == "generate"
            and row.version == 1
            and row.request_key == request["request_key"]
        ]
        pending_dependencies = [
            row
            for row in db.new
            if isinstance(row, PlanDependencyRow)
            and row.workspace_id == wid
            and row.plan_id == plan_id
            and row.version == 1
        ]
        original_flush(db, *args, **kwargs)
        if not pending_receipts:
            return
        assert not flushed and len(pending_receipts) == 1 and pending_dependencies
        with db.no_autoflush:
            version = db.scalars(
                select(PlanVersionRow).where(
                    PlanVersionRow.workspace_id == wid,
                    PlanVersionRow.plan_id == plan_id,
                    PlanVersionRow.version == 1,
                )
            ).one()
            head = db.execute(
                select(PlanRow.input_head, PlanRow.version_head).where(
                    PlanRow.workspace_id == wid, PlanRow.id == plan_id
                )
            ).one()
            assert tuple(head) == (1, 1)
            dependencies = list(
                db.scalars(
                    select(PlanDependencyRow).where(
                        PlanDependencyRow.workspace_id == wid,
                        PlanDependencyRow.plan_id == plan_id,
                        PlanDependencyRow.version == 1,
                    )
                )
            )
            assert {"local_reporting_v3", "local_creative_basis_v1"} <= {
                row.kind for row in dependencies
            }
            receipt = db.scalars(
                select(PlanRequestRow).where(
                    PlanRequestRow.workspace_id == wid,
                    PlanRequestRow.plan_id == plan_id,
                    PlanRequestRow.operation == "generate",
                    PlanRequestRow.request_key == request["request_key"],
                )
            ).one()
            assert receipt.version == 1 and receipt.result_kind == "version"
            # This explicit test-only validation adds cost; no natural timing claim.
            document = PlanVersion.model_validate_json(version.canonical_json)
            assert document.policy_version == "inlet.descriptive-review.v6"
            assert document.generator_version == "inlet.descriptive-planning.v6"
            assert document.google_budget_owner_review is not None
            assert document.google_budget_owner_review.reviews
        flushed.append(True)
        time.sleep(6)  # One real delay; original fact, clocks and guards remain unchanged.

    def final(principal: CustomerPrincipal, fact: authority.IdentityFact) -> None:
        if not flushed:
            return original_final(principal, fact)
        assert not refused
        try:
            original_final(principal, fact)
        except HTTPException as error:
            assert error.status_code == 409 and error.detail == "planning_authority_expired"
            refused.append(True)
            raise  # Preserve the same original exception, never substitute a predicate.
        raise AssertionError("Original final authority guard unexpectedly accepted the delay")

    monkeypatch.setattr(Session, "flush", flush)
    monkeypatch.setattr(authority, "final", final)
    response = alice.post(root + f"/{plan_id}/generate", headers=headers(alice), json=request)
    assert flushed == refused == [True]
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "planning_authority_expired"
    assert (planning_snapshot(customer_engine), _source_snapshot(customer_engine, wid)) == before
    assert financial_counts(customer_engine) == financial_before
    assert (len(calls), len(fixture.calls)) == provider_before
    with Session(customer_engine) as db:
        head = db.get(PlanRow, (wid, plan_id))
        assert head is not None and (head.input_head, head.version_head) == (1, 0)
        for model in (PlanVersionRow, PlanDependencyRow):
            assert db.scalar(select(model).where(model.workspace_id == wid)) is None
        assert db.scalar(
            select(PlanRequestRow).where(
                PlanRequestRow.workspace_id == wid, PlanRequestRow.operation == "generate"
            )
        ) is None
    (tmp_path / "authority-delay-outcome.json").write_text(
        json.dumps(
            dict(
                final_publication_flushed=True,
                real_delay_seconds=6,
                original_final_refused=True,
                detail="planning_authority_expired",
                full_graph_rollback=True,
                no_new_advertising_effects=True,
                historical_incident_or_performance_closure=False,
            ),
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
