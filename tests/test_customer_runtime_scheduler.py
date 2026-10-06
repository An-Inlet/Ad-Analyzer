"""Production entrypoint wiring tested with injected offline transports."""

from datetime import UTC, timedelta
from types import SimpleNamespace
from typing import NoReturn

import pytest
from app.ads.models import JobRun
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

    def record_analysis(engine: Engine, job: int) -> SimpleNamespace:
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
        row = db.get(WorkspaceBilling, wid)
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

    def record_analysis(engine: Engine, job: int) -> SimpleNamespace:
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
