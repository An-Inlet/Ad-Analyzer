"""Offline pending obligations, never authority to replay analysis/import work."""

from datetime import datetime, timedelta, tzinfo

import pytest
from app.ads import repository
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdvertisingAccount, JobRun
from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
from app.analysis.models import AnalysisRun
from app.google_connections import service as google
from app.google_connections.models import GoogleCustomerConnection, GoogleImportCompletion
from app.operations.attention import OVERDUE_SECONDS, ROW_LIMIT, attention
from app.sources import advertising
from app.sources.models import SourceConnection
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import FixtureTransport, connect, setup
from tests.test_google_customer_connections import configured as configured
from tests.test_operations_attention import NOW, OLD, PRIVATE, workspace

CODE = "analysis_obligation_unstarted_overdue"


def pending(
    db: Session, provider: str
) -> tuple[JobRun, GoogleCustomerConnection | SourceConnection]:
    wid = workspace(db, provider).id
    integration = WorkspaceIntegration(
        workspace_id=wid,
        integration_key=provider,
        provider=provider,
        display_name=PRIVATE,
        status="active",
    )
    db.add(integration)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=wid,
        connection_id=integration.id,
        platform=AdvertisingPlatform(provider),
        external_account_id="1234567890",
        name=PRIVATE,
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    fields = dict(
        id="a" * 32,
        workspace_id=wid,
        integration_id=integration.id,
        account_id=account.id,
        status="connected",
        generation=1,
        window_start=NOW.date(),
        window_end=NOW.date(),
    )
    row: GoogleCustomerConnection | SourceConnection
    if provider == "google_ads":
        row = GoogleCustomerConnection(
            **fields,
            external_account_id=account.external_account_id,
            backfill_through=NOW.date(),
            history_floor=NOW.date(),
        )
    else:
        row = SourceConnection(**fields, provider=provider, external_id=account.external_account_id)
    db.add(row)
    job = JobRun(
        workspace_id=wid,
        connection_id=integration.id,
        account_id=account.id,
        platform=AdvertisingPlatform(provider),
        job_name="fixture-sync",
        status=JobRunStatus.SUCCEEDED,
        started_at=OLD,
        finished_at=OLD,
        error_message=PRIVATE,
    )
    db.add(job)
    db.flush()
    db.add(GoogleImportCompletion(job_id=job.id, state="pending"))
    db.commit()
    return job, row


def observed(db: Session) -> int:
    return next((s.observed_count for s in attention(db, NOW).signals if s.code == CODE), 0)


@pytest.mark.parametrize("provider", ["google_ads", "tiktok_ads"])
def test_current_obligation_backoff_and_exact_run_observation(
    customer_engine: Engine, provider: str
) -> None:
    with Session(customer_engine) as db:
        job, _ = pending(db, provider)
        report = attention(db, NOW)
        signal = next(s for s in report.signals if s.code == CODE)
        assert signal.observed_count == 1 and signal.action == "inspect_local_job"
        assert signal.severity == "warning" and PRIVATE not in report.model_dump_json()
        assert "analysis_obligation_historical_generation_not_recorded" in report.observation_gaps
        outbox = db.get(GoogleImportCompletion, job.id)
        assert outbox is not None
        outbox.next_attempt_at = NOW - timedelta(seconds=OVERDUE_SECONDS - 1)
        db.commit()
        assert observed(db) == 0
        outbox.next_attempt_at = NOW - timedelta(seconds=OVERDUE_SECONDS)
        db.commit()
        assert observed(db) == 1
        db.add(
            AnalysisRun(
                workspace_id=job.workspace_id,
                account_id=job.account_id,
                source_job_run_id=job.id,
                run_key=f"post_sync:job:{job.id}",
                cadence=AnalysisCadence.POST_SYNC,
                status=AnalysisRunStatus.RUNNING,
                scheduled_for=OLD,
                started_at=OLD,
                metric_date_from=OLD.date(),
                metric_date_to=OLD.date(),
                outcome_date_from=OLD.date(),
                outcome_date_to=OLD.date(),
            )
        )
        db.commit()
        assert observed(db) == 0
        assert outbox.state == "pending"


@pytest.mark.parametrize(
    "change",
    [
        "closed",
        "revoked",
        "disconnected",
        "foreign_external",
        "unfinished",
        "failed",
        "delivered",
        "recent_finish",
    ],
)
def test_only_current_owned_complete_obligations_observed(
    customer_engine: Engine, change: str
) -> None:
    from app.workspaces.models import Workspace

    with Session(customer_engine) as db:
        job, row = pending(db, "google_ads")
        assert isinstance(row, GoogleCustomerConnection)
        owned_workspace = db.get(Workspace, job.workspace_id)
        integration = db.get(WorkspaceIntegration, job.connection_id)
        outbox = db.get(GoogleImportCompletion, job.id)
        assert owned_workspace is not None and integration is not None and outbox is not None
        if change == "closed":
            owned_workspace.status = "closing"
        elif change == "revoked":
            integration.status = "revoked"
        elif change == "disconnected":
            row.status = "disconnected"
        elif change == "foreign_external":
            row.external_account_id = "9999999999"
        elif change == "unfinished":
            job.finished_at = None
        elif change == "failed":
            job.status = JobRunStatus.FAILED
        elif change == "delivered":
            outbox.state = "delivered"
        else:
            job.finished_at = NOW
            outbox.next_attempt_at = OLD
        db.commit()
        assert observed(db) == 0


def test_bounded_obligation_query(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        first, _ = pending(db, "google_ads")
        for index in range(ROW_LIMIT):
            job = JobRun(
                workspace_id=first.workspace_id,
                connection_id=first.connection_id,
                account_id=first.account_id,
                platform=first.platform,
                job_name=f"bounded-{index}",
                status=JobRunStatus.SUCCEEDED,
                started_at=OLD,
                finished_at=OLD,
            )
            db.add(job)
            db.flush()
            db.add(GoogleImportCompletion(job_id=job.id, state="pending"))
        db.commit()
        report = attention(db, NOW)
        assert report.evidence_truncated and report.counts_are_lower_bounds
        assert next(s.observed_count for s in report.signals if s.code == CODE) == ROW_LIMIT


@pytest.mark.parametrize("change", ["disconnect", "reauthorize"])
def test_actual_google_generation_retirement_preserves_other_workspace(
    customer_engine: Engine, configured: None, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_commerce_measurement import NOW as IMPORT_NOW

    class ImportClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> "ImportClock":
            return cls.fromtimestamp(IMPORT_NOW.timestamp(), tz)

    # Actual repository completions must share the import fixture's time domain.
    monkeypatch.setattr(repository, "datetime", ImportClock)

    transport = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "retired-obligation")
        one, _ = connect(db, wid, sid, transport)
        other, other_sid = setup(db, "other-obligation")
        two, _ = connect(db, other, other_sid, transport)
        for row in (one, two):
            google.tick(db, row.workspace_id, row.id, row.generation, transport, IMPORT_NOW)
            google.tick(db, row.workspace_id, row.id, row.generation, transport, IMPORT_NOW)
        completed = list(db.scalars(select(JobRun.finished_at)))
        assert len(completed) == 2
        assert all(
            value is not None and value.timestamp() == IMPORT_NOW.timestamp() for value in completed
        )
        assert observed(db) == 2
        generation = one.generation
        if change == "disconnect":
            google.disconnect(db, one)
        else:
            connect(db, wid, sid, transport)
        assert one.generation > generation
        assert observed(db) == 1


def test_actual_tiktok_stop_reads_retires_pending_generation(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        job, row = pending(db, "tiktok_ads")
        assert isinstance(row, SourceConnection)
        assert observed(db) == 1
        advertising._stop_reads(db, row)
        assert row.generation == 2 and row.status == "reconnect_required"
        assert db.get(GoogleImportCompletion, job.id) is None
        assert observed(db) == 0
