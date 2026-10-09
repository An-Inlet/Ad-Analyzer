"""Actual Meta HTTP reports and native checkpoints; original receipt/authority are real fixtures."""

import base64
import io
import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from app.meta import client as wire
from app.meta.models import MetaConnection, MetaStagedMetric
from app.meta.security import Vault, utc
from app.meta.sync import MetaSyncService
from app.reported_feedback.contracts import ReportedAcquisitionRequestV1, ReportedWindowCapsuleV1
from app.reported_feedback.models import ReportedFeedbackJob, ReportedWindowCapsule
from app.settings import Settings
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.reported_feedback_fixture import seeded
from tests.reported_original_fixture import RetainedReportedOriginalIds, prepare_reported_read
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_original_fixture import reported_original as reported_original
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_meta_connection import campaign, insight, page
from tests.test_shopify_sales import configuration as configuration


def acquisition_fixture(
    db: Session,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    period_end: datetime | None = None,
    existing: tuple[Any, ...] | None = None,
) -> Any:
    wid, principal, provider, runtime, intent, progress, clock, server = (
        existing if existing is not None else seeded(db, config, path, period_end=period_end)
    )
    config = config.model_copy(
        update={
            "meta_enabled": True,
            "meta_client_id": "100000000000001",
            "meta_client_secret": SecretStr("offline-secret-" * 3),
            "meta_token_encryption_key": SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
            "meta_redirect_uri": "https://example.test/dashboard/meta/callback",
        }
    )
    job = db.get(ReportedFeedbackJob, progress.id)
    assert job is not None
    request = ReportedAcquisitionRequestV1.model_validate(job.document)
    clock[0] = max(clock[0], utc(job.next_due_at) + timedelta(seconds=1))
    source = db.get(MetaConnection, job.source_connection_id)
    assert source is not None
    source.encrypted_credentials = Vault(config).seal(
        wid,
        source.external_account_id,
        {
            "access_token": "offline-report-token",
            "expires_at": (clock[0] + timedelta(days=90)).isoformat(),
        },
    )
    db.commit()
    external_account_id = source.external_account_id
    requests: list[tuple[str, dict[str, list[str]]]] = []
    control: dict[str, Any] = {"missing": False, "zero": False, "revision": 0}

    class Opener:
        def open(self, outgoing: Any, timeout: int) -> io.BytesIO:
            parsed = urlsplit(outgoing.full_url)
            assert parsed.hostname == "graph.facebook.com" and outgoing.method == "GET"
            assert timeout == 12
            query = parse_qs(parsed.query)
            requests.append((parsed.path, query))
            if parsed.path.endswith("/campaigns"):
                payload = page(campaign("5", external_account_id))
            elif parsed.path.endswith("/adsets"):
                payload = page()
            else:
                assert parsed.path.endswith("/insights") and query["level"] == ["campaign"]
                window = json.loads(query["time_range"][0])
                start, end = (
                    date.fromisoformat(window["since"]),
                    date.fromisoformat(window["until"]),
                )
                days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
                if control["missing"]:
                    days = days[:-1]
                conversions = control.get(
                    "before_conversions"
                    if start == request.before.starts_on
                    else "after_conversions",
                    "3",
                )
                payload = page(
                    *[
                        insight(
                            account_id=external_account_id,
                            campaign_id="5",
                            date_start=d.isoformat(),
                            date_stop=d.isoformat(),
                            spend="0" if control["zero"] else str(10 + control["revision"]),
                            actions=[]
                            if control["zero"]
                            else [{"action_type": "purchase", "value": str(conversions)}],
                            action_values=[]
                            if control["zero"]
                            else [{"action_type": "purchase", "value": "30"}],
                        )
                        for d in days
                    ]
                )
                if control.get("on_insights"):
                    control["on_insights"]()
            return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(wire, "build_opener", lambda *_: Opener())
    runner = MetaSyncService(db, config, reported_feedback=runtime)
    return wid, principal, runtime, job, request, source, clock, runner, requests, control, server


def complete(runner: MetaSyncService, wid: int, now: Any) -> None:
    for expected in ("syncing", "syncing", "complete"):
        result = runner.page(wid, now=now)
        assert result["status"] == expected, result


@pytest.mark.planning_boundary
def test_fixed_windows_preserve_rolling_coverage_and_repeat_spacing(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
) -> None:
    with Session(customer_engine) as db:
        wid, _, runtime, job, request, source, clock, runner, requests, _, original_ids = (
            prepare_reported_acquisition(
                db, configuration, prepare_reported_read(db, reported_original), monkeypatch
            )
        )
        complete(runner, wid, clock[0])  # Ordinary due rolling acquisition has priority.
        assert source.last_sync_at is not None
        saved = (source.covered_from, source.covered_through, utc(source.last_sync_at))
        assert job.completed_observations == 0
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        assert (source.covered_from, source.covered_through, utc(source.last_sync_at)) == saved
        assert job.completed_observations == 2
        assert runner.page(wid, now=clock[0])["status"] == "up_to_date"
        assert job.completed_observations == 2
        clock[0] += timedelta(seconds=61)
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        values = [
            ReportedWindowCapsuleV1.model_validate(r.document)
            for r in db.scalars(
                select(ReportedWindowCapsule).order_by(
                    ReportedWindowCapsule.acquisition_completed_at
                )
            )
        ]
        assert len(values) == 4 and job.state == "ready"
        assert len({v.completion_id for v in values}) == 4
        assert len({v.acquisition_run_id for v in values}) == 4
        assert all(not v.missing_dates() and len(v.days) == 7 for v in values)
        assert [v.window for v in values] == [request.before, request.after] * 2
        assert values[2].acquisition_started_at >= values[0].acquisition_completed_at + timedelta(
            seconds=60
        )
        assert len([path for path, _ in requests if path.endswith("/insights")]) == 5
        assert (
            original_ids.original_post_count == 1
        )  # Only the separately seeded original action, no report writes.


@pytest.mark.parametrize("change", ["logout", "removed_job", "disabled", "generation"])
@pytest.mark.planning_boundary
def test_interrupted_fixed_run_never_becomes_rolling_or_publishes(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        wid, principal, runtime, job, _, source, clock, runner, requests, _, _ = (
            prepare_reported_acquisition(
                db, configuration, prepare_reported_read(db, reported_original), monkeypatch
            )
        )
        complete(runner, wid, clock[0])
        assert runner.page(wid, now=clock[0])["status"] == "syncing"
        assert source.phase == "rf_adsets"
        before = len(requests)
        if change == "logout":
            principal.session.revoked_at = int(clock[0].timestamp())
        elif change == "removed_job":
            db.delete(job)
        elif change == "generation":
            source.generation += 1
        else:
            runner.reported_feedback = None
        db.commit()
        result = runner.page(wid, now=clock[0])
        assert result["status"] in {
            "reported_feedback_unavailable",
            "meta_reported_feedback_checkpoint_invalid",
        }, result
        assert len(requests) == before
        assert (
            source.phase == "campaigns"
            and source.window_start is None
            and source.window_end is None
        )
        assert not list(db.scalars(select(ReportedWindowCapsule)))
        assert not list(db.scalars(select(MetaStagedMetric)))


@pytest.mark.planning_boundary
def test_actual_zero_and_missing_day_remain_distinct(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
) -> None:
    with Session(customer_engine) as db:
        wid, _, _, _, _, _, clock, runner, _, control, _ = prepare_reported_acquisition(
            db, configuration, prepare_reported_read(db, reported_original), monkeypatch
        )
        complete(runner, wid, clock[0])
        control.update(zero=True, missing=True)
        complete(runner, wid, clock[0])
        row = db.scalar(select(ReportedWindowCapsule))
        assert row is not None
        value = ReportedWindowCapsuleV1.model_validate(row.document)
        assert len(value.days) == 6 and len(value.missing_dates()) == 1
        assert all(d.spend_micros == 0 and d.conversions == 0 for d in value.days)


@pytest.mark.planning_boundary
def test_invalid_first_job_cannot_select_another_owner_after_native_lock(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
) -> None:
    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
    from app.reported_feedback.contracts import ComparisonIntentV1
    from app.reported_feedback.service import request_comparison

    from tests.test_customer_identity import FakeProvider

    with Session(customer_engine) as db:
        wid, principal, runtime, first, request, _, clock, runner, requests, _, _ = (
            prepare_reported_acquisition(
                db, configuration, prepare_reported_read(db, reported_original), monkeypatch
            )
        )
        complete(runner, wid, clock[0])
        user = CustomerUser(
            id=uuid4().hex,
            issuer=FakeProvider.issuer,
            subject="another-owner",
            email="second@example.test",
            status="active",
        )
        db.add(user)
        db.flush()
        session = CustomerSession(
            digest=uuid4().hex * 2,
            user_id=user.id,
            csrf_digest="e" * 64,
            created_at=int(clock[0].timestamp()),
            authenticated_at=int(clock[0].timestamp()),
            expires_at=int((clock[0] + timedelta(days=20)).timestamp()),
        )
        db.add_all(
            [
                session,
                CustomerMembership(
                    user_id=user.id, workspace_id=wid, role="owner", status="active"
                ),
            ]
        )
        db.commit()
        assert runtime.window_policy is not None
        runtime = replace(
            runtime, window_policy=runtime.window_policy.model_copy(update={"family": "c" * 32})
        )
        second = request_comparison(
            db,
            CustomerPrincipal(user, session),
            FakeProvider(),
            wid,
            ComparisonIntentV1(
                attempt_id=first.original_attempt_id,
                goal_id=request.objective.goal_id,
                goal_revision=request.objective.goal_revision,
                maximum_reported_cpa_micros=100_000_000,
            ),
            runtime,
        )
        principal.session.revoked_at = int(clock[0].timestamp())
        db.commit()
        runner.reported_feedback = runtime
        before = len(requests)
        assert runner.page(wid, now=clock[0])["status"] == "up_to_date"
        assert len(requests) == before
        assert first.state == "blocked"
        second_row = db.get(ReportedFeedbackJob, second.id)
        assert second_row is not None and second_row.state == "pending"
        # The following page obtains this owner's original locks before the native lock.
        assert runner.page(wid, now=clock[0])["status"] == "syncing"
        assert second_row.state == "acquiring" and len(requests) == before + 1


@pytest.mark.planning_boundary
def test_expiry_during_terminal_http_retains_previous_publication(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_original: RetainedReportedOriginalIds,
) -> None:
    from app.campaign_performance.models import CurrentPerformance

    with Session(customer_engine) as db:
        wid, _, _, job, _, source, clock, runner, _, control, _ = prepare_reported_acquisition(
            db, configuration, prepare_reported_read(db, reported_original), monkeypatch
        )
        complete(runner, wid, clock[0])
        previous = db.get(CurrentPerformance, source.account_id)
        assert previous is not None
        previous_id = previous.completion_id
        for _ in range(2):
            assert runner.page(wid, now=clock[0])["status"] == "syncing"

        def expire() -> None:
            clock[0] = utc(job.expires_at) + timedelta(seconds=1)

        control["on_insights"] = expire
        result = runner.page(wid, now=clock[0])
        assert result["status"] == "meta_reported_feedback_authority_changed", result
        current = db.get(CurrentPerformance, source.account_id, populate_existing=True)
        assert current is not None and current.completion_id == previous_id
        assert not list(db.scalars(select(ReportedWindowCapsule)))
        assert source.phase == "campaigns" and source.window_start is None
