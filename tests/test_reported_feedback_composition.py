"""Actual Meta HTTP terminal windows → owned receipt comparison → explicit new round."""

from datetime import timedelta
from pathlib import Path

import pytest
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExposureReservation,
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
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_reported_feedback_acquisition import acquisition_fixture, complete
from tests.test_shopify_sales import configuration as configuration


def test_real_reports_compare_without_claiming_causality_and_idempotent_receipt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        wid, principal, runtime, job, request, source, clock, runner, requests, control, server = (
            acquisition_fixture(db, configuration, tmp_path, monkeypatch)
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
        assert len(server.posts) == 1
        assert db.scalar(select(func.count()).select_from(ReportedWindowCapsule)) == 4
        row = db.get(ReportedActionComparison, result.id)
        assert row is not None
        source.generation += 1
        db.commit()
        with pytest.raises(HTTPException):
            validate_comparison_dependencies(db, row, clock[0])


def test_actual_correction_requires_explicit_new_reports_same_original_opportunity(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        wid, principal, runtime, job, request, _, clock, runner, _, control, server = (
            acquisition_fixture(db, configuration, tmp_path, monkeypatch)
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
                ProviderExposureReservation,
            )
        )
        assert len(server.posts) == 1
