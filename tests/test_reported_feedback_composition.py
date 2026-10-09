"""Actual Meta HTTP terminal windows → owned receipt comparison → explicit new round."""

from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from app.executors.meta_optimization import MetaOptimizationTransport
from app.publication import optimization
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExposureReservation,
)
from app.publication.optimization_contracts import (
    OptimizationContext,
    OptimizationRequest,
    OptimizationResponse,
)
from app.reported_feedback.models import (
    ReportedActionComparison,
    ReportedFeedbackJob,
    ReportedWindowCapsule,
)
from app.reported_feedback.service import (
    read_comparison,
    reobserve_comparison,
    validate_comparison_dependencies,
)
from app.settings import Settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_original_fixture import (
    ExpectedUnknownReadback,
    RetainedReportedOriginalIds,
    assert_no_attempt_derivatives,
    prepare_reported_read,
    retained_reported_original_fixture,
)
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_original_fixture import reported_original as reported_original
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_reported_feedback_acquisition import complete
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.planning_boundary
def test_real_reports_compare_without_claiming_causality_and_idempotent_receipt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
) -> None:
    with Session(customer_engine) as db:
        (
            wid,
            principal,
            runtime,
            job,
            request,
            source,
            clock,
            runner,
            requests,
            control,
            original_ids,
        ) = prepare_reported_acquisition(
            db, configuration, prepare_reported_read(db, reported_original), monkeypatch
        )
        control.update(before_conversions="2", after_conversions="4")
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        clock[0] += timedelta(seconds=61)
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        result = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        db.commit()
        assert result.status == "operational_reported_as_of"
        assert result.before.reported_cpa_micros == 5_000_000
        assert result.after.reported_cpa_micros == 2_500_000
        assert result.relative_cpa_improvement == 0.5
        assert result.causal_lift == result.delivery_time == "unavailable"
        assert result.spending_authority == "none"
        assert read_comparison(db, principal, FakeProvider(), wid, job.id, runtime).id == result.id
        assert original_ids.original_post_count == 1
        assert db.scalar(select(func.count()).select_from(ReportedWindowCapsule)) == 4
        row = db.get(ReportedActionComparison, result.id)
        assert row is not None
        source.generation += 1
        db.commit()
        with pytest.raises(HTTPException):
            validate_comparison_dependencies(db, row, clock[0])


@pytest.mark.planning_boundary
def test_actual_correction_requires_explicit_new_reports_same_original_opportunity(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
) -> None:
    with Session(customer_engine) as db:
        wid, principal, runtime, job, request, _, clock, runner, _, control, original_ids = (
            prepare_reported_acquisition(
                db, configuration, prepare_reported_read(db, reported_original), monkeypatch
            )
        )
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        clock[0] += timedelta(seconds=61)
        control["revision"] = 1
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        result = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        db.commit()
        assert result.status == "insufficient"
        assert "reported_revision_outside_tolerance" in result.reasons
        protected = tuple(
            db.scalar(select(func.count()).select_from(model))
            for model in (
                ProviderExecutionAttempt,
                ProviderExecutionReceipt,
                ProviderExecutionResponse,
                ProviderExposureReservation,
            )
        )
        successor = reobserve_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        db.commit()
        assert successor.id != job.id and successor.completed_observations == 0
        assert (
            reobserve_comparison(db, principal, FakeProvider(), wid, job.id, runtime).id
            == successor.id
        )
        next_job = db.get(ReportedFeedbackJob, successor.id)
        assert next_job is not None and next_job.opportunity_digest == job.opportunity_digest
        assert next_job.original_attempt_id == job.original_attempt_id and job.state == "blocked"
        assert db.get(ReportedActionComparison, result.id) is None
        with pytest.raises(HTTPException):
            read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        clock[0] += timedelta(seconds=61)
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        actual = read_comparison(db, principal, FakeProvider(), wid, next_job.id, runtime)
        assert actual.status == "operational_reported_as_of"
        assert actual.anchor.original_attempt_id == result.anchor.original_attempt_id
        assert db.scalar(select(func.count()).select_from(ReportedWindowCapsule)) == 8
        assert protected == tuple(
            db.scalar(select(func.count()).select_from(model))
            for model in (
                ProviderExecutionAttempt,
                ProviderExecutionReceipt,
                ProviderExecutionResponse,
                ProviderExposureReservation,
            )
        )
        assert original_ids.original_post_count == 1


@pytest.mark.parametrize("change", ["original_session", "latest_unknown_receipt"])
@pytest.mark.planning_boundary
def test_final_delivery_rechecks_original_session_and_latest_receipt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    expected = ExpectedUnknownReadback() if change == "latest_unknown_receipt" else None
    with (
        retained_reported_original_fixture(
            customer_engine, tmp_path / "original", expected_unknown=expected
        ) as (_, ids),
        Session(customer_engine) as db,
    ):
        wid, principal, runtime, job, _, _, clock, runner, _, _, original_ids = (
            prepare_reported_acquisition(
                db, configuration, prepare_reported_read(db, ids), monkeypatch
            )
        )
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        clock[0] += timedelta(seconds=61)
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        result = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        db.commit()
        row = db.get(ReportedActionComparison, result.id)
        assert row is not None
        if change == "original_session":
            principal.session.revoked_at = int(clock[0].timestamp())
            db.commit()
        else:
            original = db.get(ProviderExecutionAttempt, job.original_attempt_id)
            assert original is not None
            request = OptimizationRequest.model_validate(original.request)

            calls: list[str] = []

            def fail(req: httpx.Request) -> httpx.Response:
                assert req.method == "GET"
                calls.append(req.method)
                raise httpx.ReadTimeout("offline unavailable current provider state")

            adapter = MetaOptimizationTransport(transport=httpx.MockTransport(fail))
            context = OptimizationContext(
                scope=request.intent.scope,
                access_token=SecretStr("offline-only"),
                expires_at=clock[0] + timedelta(hours=1),
            )
            response_row = db.scalar(
                select(ProviderExecutionResponse).where(
                    ProviderExecutionResponse.attempt_id == original.id
                )
            )
            assert response_row is not None
            response = OptimizationResponse.model_validate(response_row.response)
            assert_no_attempt_derivatives(db)
            assert expected is not None
            expected.arm(clock[0])
            receipt = adapter.read_back(request, response, context, clock[0])
            assert calls == ["GET"]
            assert receipt.outcome == "unknown"
            optimization.record_receipt(db, wid, job.original_attempt_id, receipt, lambda: clock[0])
        with pytest.raises(HTTPException):
            read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        with pytest.raises(HTTPException):
            validate_comparison_dependencies(db, row, clock[0])
        assert original_ids.original_post_count == 1
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
