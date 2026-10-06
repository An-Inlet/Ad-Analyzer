"""Customer post-import analysis borrows one session and revalidates after claim."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Any

import pytest
from app.analysis.enums import AnalysisRunStatus
from app.analysis.models import AnalysisRun
from app.analysis.repository import AnalysisRunRepository
from app.analysis.service import AnalysisRunService
from app.billing.models import WorkspaceBilling
from app.billing.scope import LEGACY_TEST_SCOPE
from app.google_connections.dispatcher import run_imports
from app.google_connections.models import GoogleImportCompletion
from app.jobs import customer_runtime as runtime
from app.settings import settings
from app.workspaces.locking import lock_workspace_row
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session

from tests.test_analysis_closure_fence import close
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import NOW, seed
from tests.test_google_customer_connections import FixtureTransport, connect
from tests.test_google_customer_connections import configured as configured


def prepare(engine: Engine) -> tuple[int, str, str, int]:
    with Session(engine) as db:
        principal, wid = seed(db)
        uid, sid = principal.user.id, principal.session.digest
        connect(db, wid, sid, FixtureTransport())
    run_imports(engine, FixtureTransport(), NOW)
    run_imports(engine, FixtureTransport(), NOW)
    with Session(engine) as db:
        job = db.scalar(select(GoogleImportCompletion.job_id))
        assert job is not None
    return wid, uid, sid, job


def test_customer_analysis_no_cross_session_self_deadlock(
    export_engine: Engine, configured: None
) -> None:
    _, _, _, job = prepare(export_engine)

    def bounded(dbapi: Any, record: Any, proxy: Any) -> None:
        with dbapi.cursor() as cursor:
            cursor.execute("SET statement_timeout = 5000")

    if export_engine.dialect.name == "postgresql":
        event.listen(export_engine, "checkout", bounded)
    try:
        result = runtime._analyze(export_engine, job)
        assert isinstance(result, AnalysisRun) and result.status == AnalysisRunStatus.SUCCEEDED
    finally:
        if export_engine.dialect.name == "postgresql":
            event.remove(export_engine, "checkout", bounded)


@pytest.mark.parametrize("change", ["closure", "source", "billing"])
def test_post_claim_revalidates_customer_source_and_paid_authority(
    export_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    wid, uid, sid, job = prepare(export_engine)
    now = datetime.now(UTC)
    with Session(export_engine) as db:
        db.add(
            WorkspaceBilling(
                workspace_id=wid,
                customer_request_key="fixture-billing",
                status="active",
                price_id="price_fixture",
                verified_at=now,
                period_end=now + timedelta(days=1),
            )
        )
        db.commit()
    monkeypatch.setattr(settings, "billing_required", True)
    monkeypatch.setattr(settings, "billing_price_id", "price_fixture")
    claimed, proceed, analyzed = Event(), Event(), Event()
    original = AnalysisRunRepository.claim

    def pause(self: AnalysisRunRepository, **kwargs: Any) -> tuple[AnalysisRun, bool]:
        result = original(self, **kwargs)
        claimed.set()
        assert proceed.wait(15)
        return result

    def forbidden(self: AnalysisRunService, **kwargs: Any) -> Any:
        analyzed.set()
        raise AssertionError("local outputs must not begin")

    monkeypatch.setattr(AnalysisRunRepository, "claim", pause)
    monkeypatch.setattr(AnalysisRunService, "_analyze", forbidden)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(runtime._analyze, export_engine, job)
        try:
            assert claimed.wait(10)
            if change == "closure":
                close(export_engine, wid, uid, sid)
            else:
                with Session(export_engine) as db:
                    lock_workspace_row(db, wid)
                    if change == "source":
                        integration = db.scalar(
                            select(WorkspaceIntegration).where(
                                WorkspaceIntegration.workspace_id == wid
                            )
                        )
                        assert integration is not None
                        integration.status = "revoked"
                    else:
                        billing = db.get(WorkspaceBilling, LEGACY_TEST_SCOPE.key(wid))
                        assert billing is not None
                        billing.status = "past_due"
                    db.commit()
        finally:
            proceed.set()
        with pytest.raises(ValueError, match="analysis incomplete"):
            future.result(timeout=20)
    assert not analyzed.is_set()
    with Session(export_engine) as db:
        row = db.scalar(select(AnalysisRun))
        assert row is not None and row.status == AnalysisRunStatus.FAILED
        assert row.error_code == "analysis_failed"
