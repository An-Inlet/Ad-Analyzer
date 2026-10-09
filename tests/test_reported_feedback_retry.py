"""Actual bounded Meta transport backoff keeps the original fixed-run checkpoint."""

from datetime import timedelta
from email.message import Message
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from app.meta import client as wire
from app.meta.security import utc
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.reported_original_fixture import RetainedReportedOriginalIds, prepare_reported_read
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_original_fixture import reported_original as reported_original
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_reported_feedback_acquisition import complete
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("failure", ["timeout", "throttle"])
@pytest.mark.planning_boundary
def test_transient_fixed_page_resumes_only_after_deadline_same_run(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
    failure: str,
) -> None:
    with Session(customer_engine) as db:
        wid, _, _, job, _, source, clock, runner, requests, _, _ = prepare_reported_acquisition(
            db, configuration, prepare_reported_read(db, reported_original), monkeypatch
        )
        complete(runner, wid, clock[0])
        assert runner.page(wid, now=clock[0])["status"] == "syncing"
        assert source.phase == "rf_adsets"
        assert job.acquisition_started_at is not None
        run_id, started = job.native_run_id, utc(job.acquisition_started_at)
        original = vars(wire)["build_opener"]
        failed = [False]

        class Once:
            def open(self, outgoing: Any, timeout: int) -> Any:
                if not failed[0]:
                    failed[0] = True
                    if failure == "throttle":
                        raise HTTPError(
                            "https://graph.facebook.com/offline",
                            429,
                            "offline throttle",
                            Message(),
                            BytesIO(b"{}"),
                        )
                    raise URLError("offline transient failure")
                return original().open(outgoing, timeout=timeout)

        monkeypatch.setattr(wire, "build_opener", lambda *_: Once())
        assert runner.page(wid, now=clock[0])["status"] == (
            "meta_throttled" if failure == "throttle" else "meta_unavailable"
        )
        assert source.phase == "rf_adsets" and job.completed_observations == 0
        assert job.native_run_id == run_id and utc(job.acquisition_started_at) == started
        assert source.next_attempt_at is not None
        before = len(requests)
        clock[0] = utc(source.next_attempt_at) - timedelta(seconds=1)
        assert runner.page(wid, now=clock[0])["status"] == "retry_later"
        assert len(requests) == before
        clock[0] += timedelta(seconds=1)
        assert runner.page(wid, now=clock[0])["status"] == "syncing"
        assert job.native_run_id == run_id and utc(job.acquisition_started_at) == started
        assert source.phase == "rf_insights" and source.error_code is None
        assert runner.page(wid, now=clock[0])["status"] == "complete"
        assert job.completed_observations == 1


@pytest.mark.parametrize("change", ["session", "generation", "fatal", "missing_deadline"])
@pytest.mark.planning_boundary
def test_transport_retry_never_bypasses_current_authority_or_fatal_error(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        wid, principal, _, job, _, source, clock, runner, requests, _, _ = (
            prepare_reported_acquisition(
                db, configuration, prepare_reported_read(db, reported_original), monkeypatch
            )
        )
        complete(runner, wid, clock[0])
        assert runner.page(wid, now=clock[0])["status"] == "syncing"
        original = vars(wire)["build_opener"]

        class Failing:
            def open(self, outgoing: Any, timeout: int) -> Any:
                if change == "fatal":
                    raise HTTPError(
                        "https://graph.facebook.com/offline",
                        401,
                        "offline expired token",
                        Message(),
                        BytesIO(b"{}"),
                    )
                raise URLError("offline transient failure")

        monkeypatch.setattr(wire, "build_opener", lambda *_: Failing())
        assert runner.page(wid, now=clock[0])["status"] == (
            "meta_reconnect_required" if change == "fatal" else "meta_unavailable"
        )
        assert source.next_attempt_at is not None
        clock[0] = utc(source.next_attempt_at)
        if change == "session":
            principal.session.revoked_at = int(clock[0].timestamp())
        elif change == "generation":
            source.generation += 1
        elif change == "missing_deadline":
            source.next_attempt_at = None
        db.commit()
        monkeypatch.setattr(wire, "build_opener", original)
        before = len(requests)
        result = runner.page(wid, now=clock[0])
        assert result["status"] in {
            "not_connected_or_busy",
            "meta_reported_feedback_authority_changed",
            "meta_reported_feedback_checkpoint_invalid",
        }
        assert len(requests) == before
