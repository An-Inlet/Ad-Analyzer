"""Production entrypoint wiring tested with injected offline transports."""

from datetime import UTC, timedelta
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest
from app.ads.models import JobRun
from app.analysis.enums import AnalysisRunStatus
from app.automation.models import PlatformAutomationControl, WorkspaceAutomationControl
from app.google_connections.models import GoogleImportCompletion
from app.jobs import customer_runtime as runtime
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import FixtureTransport, connect, setup
from tests.test_google_customer_connections import configured as configured
from tests.test_tiktok_sources import TikTokFixture
from tests.test_tiktok_sources import configured as tiktok_configured  # noqa: F401
from tests.test_tiktok_sources import connect as tiktok_connect


def test_disabled_does_not_construct_providers(customer_engine: Engine) -> None:
    def forbidden() -> NoReturn:
        raise AssertionError("provider factory called")

    assert (
        runtime.run_customer_tick(
            customer_engine,
            configuration=Settings(),
            google_factory=forbidden,
            tiktok_factory=forbidden,
            billing_factory=forbidden,
            automation_factory=forbidden,
        )
        == {}
    )


@pytest.mark.usefixtures("tiktok_configured")
def test_actual_dispatchers_and_kill_switch(customer_engine: Engine, configured: None) -> None:
    google, tiktok = FixtureTransport(), TikTokFixture()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "scheduler")
        connect(db, wid, sid, google)
        tiktok_connect(db, wid, sid, tiktok)
    config = Settings(
        AD_ANALYZER_CUSTOMER_GOOGLE_SCHEDULER_ENABLED=True,
        AD_ANALYZER_CUSTOMER_TIKTOK_SCHEDULER_ENABLED=True,
    )
    before = google.calls, tiktok.calls
    assert runtime.run_customer_tick(
        customer_engine,
        configuration=config,
        now=NOW,
        google_factory=lambda: google,
        tiktok_factory=lambda: tiktok,
    ) == {"google": "completed", "tiktok": "completed"}
    assert (google.calls, tiktok.calls) == (before[0] + 1, before[1] + 1)
    with Session(customer_engine) as db:
        db.add(PlatformAutomationControl(key="all_data_syncs", enabled=False, updated_by="fixture"))
        db.commit()
    before = google.calls, tiktok.calls
    runtime.run_customer_tick(
        customer_engine,
        configuration=config,
        now=NOW,
        google_factory=lambda: google,
        tiktok_factory=lambda: tiktok,
    )
    assert (google.calls, tiktok.calls) == before


def test_factory_failure_does_not_block_next_stage(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def failure() -> NoReturn:
        raise RuntimeError("sensitive provider detail")

    monkeypatch.setattr(runtime, "run_tiktok", lambda *args: calls.append("tiktok"))
    config = Settings(
        AD_ANALYZER_CUSTOMER_GOOGLE_SCHEDULER_ENABLED=True,
        AD_ANALYZER_CUSTOMER_TIKTOK_SCHEDULER_ENABLED=True,
    )
    assert runtime.run_customer_tick(
        customer_engine, configuration=config, google_factory=failure, tiktok_factory=TikTokFixture
    ) == {"google": "failed", "tiktok": "completed"}
    assert calls == ["tiktok"]


def test_outbox_disabled_workspace_backs_off_and_healthy_tenant_progresses(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.google_connections.dispatcher import deliver_analysis, run_imports

    google = FixtureTransport()
    with Session(customer_engine) as db:
        blocked, sid = setup(db, "blocked")
        connect(db, blocked, sid, google)
        healthy, sid = setup(db, "healthy")
        connect(db, healthy, sid, google)
    run_imports(customer_engine, google, NOW)
    run_imports(customer_engine, google, NOW)
    with Session(customer_engine) as db:
        first = db.scalar(select(JobRun).order_by(JobRun.id))
        assert first is not None
        db.add(
            WorkspaceAutomationControl(
                workspace_id=first.workspace_id,
                key="post_sync_analysis",
                enabled=False,
                updated_by="fixture",
            )
        )
        db.commit()
    analyzed = []

    def record_analysis(engine: Engine, job: int, **kwargs: Any) -> SimpleNamespace:
        analyzed.append(job)
        return SimpleNamespace(status="succeeded")

    monkeypatch.setattr(runtime, "run_post_sync_analysis", record_analysis)
    assert deliver_analysis(customer_engine, runtime._analyze, limit=1, now=NOW) == 0
    assert deliver_analysis(customer_engine, runtime._analyze, limit=1, now=NOW) == 1
    assert len(analyzed) == 1
    with Session(customer_engine) as db:
        pending = db.scalar(
            select(GoogleImportCompletion).where(GoogleImportCompletion.state == "pending")
        )
        assert pending is not None and pending.next_attempt_at is not None
        assert pending.next_attempt_at.replace(tzinfo=UTC) == NOW + timedelta(minutes=5)


def test_shipped_scheduler_invokes_customer_coordinator(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.jobs.google_ads_scheduler import _run_analysis_tick

    calls = []
    monkeypatch.setattr(runtime, "run_customer_tick", lambda engine: calls.append(engine))
    monkeypatch.setattr("app.analysis.cadence.run_analysis_tick", lambda *args: None)
    for module, name in [
        ("app.shopify.privacy", "purge_expired_facts"),
        ("app.shopify.privacy", "run_privacy_tick"),
        ("app.shopify.sync", "run_shopify_tick"),
        ("app.meta.sync", "run_meta_tick"),
    ]:
        monkeypatch.setattr(f"{module}.{name}", lambda *args: None)
    _run_analysis_tick(customer_engine, None)
    assert calls == [customer_engine]


def test_billing_refresh_runs_through_coordinator_even_when_syncs_disabled(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.billing.models import WorkspaceBilling
    from app.billing.scope import LEGACY_TEST_SCOPE
    from app.settings import settings

    from tests.test_customer_billing import POLICY, FixtureBilling

    monkeypatch.setattr(settings, "billing_price_id", POLICY.price_id)
    monkeypatch.setattr(settings, "billing_max_accounts", POLICY.max_accounts)
    with Session(customer_engine) as db:
        wid, _ = setup(db, "billing-scheduler")
        db.add(
            WorkspaceBilling(
                workspace_id=wid,
                customer_id="cus_fixture",
                subscription_id="sub_fixture",
                customer_request_key="fixture-key",
            )
        )
        db.add(PlatformAutomationControl(key="all_data_syncs", enabled=False, updated_by="fixture"))
        db.commit()
    result = runtime.run_customer_tick(
        customer_engine,
        configuration=Settings(AD_ANALYZER_CUSTOMER_BILLING_SCHEDULER_ENABLED=True),
        now=NOW,
        billing_factory=FixtureBilling,
    )
    assert result == {"billing": "completed"}
    with Session(customer_engine) as db:
        row = db.get(WorkspaceBilling, LEGACY_TEST_SCOPE.key(wid))
        assert row is not None and row.status == "active" and row.verified_at is not None


@pytest.mark.parametrize("lifecycle", ["disconnect", "reconnect"])
def test_stale_selected_outbox_never_analyzes_after_lifecycle_change(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch, lifecycle: str
) -> None:
    from app.google_connections import service
    from app.google_connections.dispatcher import run_imports

    google = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "retired")
        connection, _ = connect(db, wid, sid, google)
        cid = connection.id
    run_imports(customer_engine, google, NOW)
    run_imports(customer_engine, google, NOW)
    with Session(customer_engine) as db:
        job_id = db.scalar(select(GoogleImportCompletion.job_id))
        assert job_id is not None
        if lifecycle == "disconnect":
            service.disconnect(db, service.owned(db, wid, cid))
        else:
            connect(db, wid, sid, google)
    analyzed: list[int] = []

    def record_analysis(engine: Engine, job: int, **kwargs: Any) -> SimpleNamespace:
        analyzed.append(job)
        return SimpleNamespace(status="succeeded")

    monkeypatch.setattr(runtime, "run_post_sync_analysis", record_analysis)
    with pytest.raises(ValueError, match="analysis source"):
        runtime._analyze(customer_engine, job_id)
    assert analyzed == []


def test_real_local_analysis_executes_under_lifecycle_guard(
    customer_engine: Engine, configured: None
) -> None:
    from app.analysis.models import AnalysisRun
    from app.google_connections.dispatcher import run_imports

    google = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "real-analysis")
        connect(db, wid, sid, google)
    run_imports(customer_engine, google, NOW)
    run_imports(customer_engine, google, NOW)
    result = runtime.run_customer_tick(
        customer_engine,
        configuration=Settings(AD_ANALYZER_CUSTOMER_ANALYSIS_OUTBOX_ENABLED=True),
        now=NOW,
    )
    assert result == {"analysis_outbox": "completed"}
    with Session(customer_engine) as db:
        analysis = db.scalar(select(AnalysisRun))
        completion = db.scalar(select(GoogleImportCompletion))
        assert analysis is not None and analysis.status == "succeeded"
        assert analysis.workspace_id == wid
        assert completion is not None and completion.state == "delivered"


def test_failed_analysis_retries_same_run_after_backoff_once(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.analysis.models import AnalysisRun
    from app.analysis.service import AnalysisRunService
    from app.google_connections.dispatcher import deliver_analysis, run_imports

    google = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "retry-analysis")
        connect(db, wid, sid, google)
    run_imports(customer_engine, google, NOW)
    run_imports(customer_engine, google, NOW)
    original = AnalysisRunService._analyze
    calls = []

    def fail_once(self: AnalysisRunService, **kwargs: Any) -> Any:
        calls.append(kwargs["workspace_id"])
        if len(calls) == 1:
            raise RuntimeError("private failure must not enter audit")
        return original(self, **kwargs)

    monkeypatch.setattr(AnalysisRunService, "_analyze", fail_once)
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW) == 0
    with Session(customer_engine) as db:
        failed = db.scalar(select(AnalysisRun))
        assert failed is not None and failed.status == "failed"
        run_id = failed.id
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW) == 0
    assert calls == [wid]
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW + timedelta(minutes=5)) == 1
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW + timedelta(minutes=10)) == 0
    with Session(customer_engine) as db:
        rows = list(db.scalars(select(AnalysisRun)))
        assert len(rows) == 1 and rows[0].id == run_id and rows[0].status == "succeeded"
        assert rows[0].retry_count == 1
        assert rows[0].retry_history[0]["error_code"] == "analysis_failed"
        assert "private" not in str(rows[0].retry_history)
    assert calls == [wid, wid]


def test_ambiguous_running_analysis_is_never_reclaimed(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.analysis.models import AnalysisRun
    from app.analysis.service import AnalysisRunService
    from app.google_connections.dispatcher import deliver_analysis, run_imports

    google = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "ambiguous-analysis")
        connect(db, wid, sid, google)
    run_imports(customer_engine, google, NOW)
    run_imports(customer_engine, google, NOW)
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW) == 1
    with Session(customer_engine) as db:
        run = db.scalar(select(AnalysisRun))
        completion = db.scalar(select(GoogleImportCompletion))
        assert run is not None and completion is not None
        # Simulate a durably claimed attempt with unknown outcome.
        run.status = AnalysisRunStatus.RUNNING
        run.finished_at = None
        completion.state = "pending"
        db.commit()

    def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("ambiguous run executed again")

    monkeypatch.setattr(AnalysisRunService, "_analyze", forbidden)
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW + timedelta(days=10)) == 0
    with Session(customer_engine) as db:
        run = db.scalar(select(AnalysisRun))
        assert run is not None and run.status == "running" and run.retry_count == 0


def test_lost_analysis_commit_ack_does_not_relabel_success_retryable(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.analysis.models import AnalysisRun
    from app.google_connections.dispatcher import deliver_analysis, run_imports

    google = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "lost-analysis-ack")
        connect(db, wid, sid, google)
    run_imports(customer_engine, google, NOW)
    run_imports(customer_engine, google, NOW)
    original = Session.commit
    lost: list[bool] = []

    def commit_then_lose_ack(db: Session) -> None:
        should_fail = not lost and any(
            isinstance(row, AnalysisRun) and row.status == AnalysisRunStatus.SUCCEEDED
            for row in db.dirty
        )
        original(db)
        if should_fail:
            lost.append(True)
            raise RuntimeError("simulated lost commit acknowledgement")

    monkeypatch.setattr(Session, "commit", commit_then_lose_ack)
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW) == 1
    assert lost == [True]
    with Session(customer_engine) as db:
        run = db.scalar(select(AnalysisRun))
        assert (
            run is not None and run.status == AnalysisRunStatus.SUCCEEDED and run.retry_count == 0
        )


@pytest.mark.usefixtures("tiktok_configured")
def test_tiktok_actual_import_analysis_and_duplicate_delivery(customer_engine: Engine) -> None:
    from app.analysis.models import AnalysisRun
    from app.google_connections.dispatcher import deliver_analysis
    from app.sources.dispatcher import run_tiktok

    transport = TikTokFixture()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "tiktok-real-analysis")
        tiktok_connect(db, wid, sid, transport)
    run_tiktok(customer_engine, transport, NOW)
    assert run_tiktok(customer_engine, transport, NOW)["completed_windows"] == 1
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW) == 1
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW) == 0
    with Session(customer_engine) as db:
        analyses = list(db.scalars(select(AnalysisRun)))
        assert len(analyses) == 1 and analyses[0].workspace_id == wid
        assert analyses[0].status == AnalysisRunStatus.SUCCEEDED


@pytest.mark.usefixtures("tiktok_configured")
@pytest.mark.parametrize("lifecycle", ["disconnect", "reconnect"])
def test_tiktok_retired_generation_cannot_deliver_and_other_tenant_survives(
    customer_engine: Engine, lifecycle: str
) -> None:
    from app.analysis.models import AnalysisRun
    from app.google_connections.dispatcher import deliver_analysis
    from app.sources import service as sources
    from app.sources.dispatcher import run_tiktok

    transport = TikTokFixture()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "tiktok-retired")
        row, _ = tiktok_connect(db, wid, sid, transport)
        cid = row.id
        other, other_sid = setup(db, "tiktok-other")
        tiktok_connect(db, other, other_sid, transport)
    run_tiktok(customer_engine, transport, NOW)
    run_tiktok(customer_engine, transport, NOW)
    with Session(customer_engine) as db:
        job_id = db.scalar(select(JobRun.id).where(JobRun.workspace_id == wid))
        assert job_id is not None
        if lifecycle == "disconnect":
            sources.disconnect(db, sources.owned(db, wid, "tiktok_ads", cid))
        else:
            tiktok_connect(db, wid, sid, transport)
    with pytest.raises(ValueError, match="analysis source"):
        runtime._analyze(customer_engine, job_id)
    assert deliver_analysis(customer_engine, runtime._analyze, now=NOW) == 1
    with Session(customer_engine) as db:
        analyses = list(db.scalars(select(AnalysisRun)))
        assert len(analyses) == 1 and analyses[0].workspace_id == other
        assert db.get(GoogleImportCompletion, job_id) is None


@pytest.mark.usefixtures("tiktok_configured")
def test_tiktok_foreign_workspace_connection_cannot_authorize_analysis(
    customer_engine: Engine,
) -> None:
    from app.sources import service as sources
    from app.sources.dispatcher import run_tiktok

    transport = TikTokFixture()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "tiktok-unbound")
        row, _ = tiktok_connect(db, wid, sid, transport)
        cid = row.id
        other, other_sid = setup(db, "tiktok-foreign")
        tiktok_connect(
            db, other, other_sid, transport
        )  # Same external advertiser, distinct tenant.
    run_tiktok(customer_engine, transport, NOW)
    run_tiktok(customer_engine, transport, NOW)
    with Session(customer_engine) as db:
        job_id = db.scalar(select(JobRun.id).where(JobRun.workspace_id == wid))
        assert job_id is not None
        row = sources.owned(db, wid, "tiktok_ads", cid)
        row.account_id = None
        db.commit()
    with pytest.raises(ValueError, match="analysis source unavailable"):
        runtime._analyze(customer_engine, job_id)
