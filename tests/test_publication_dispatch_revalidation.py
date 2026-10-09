"""The mandate dispatch commit must not bypass subsequent customer stops."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event

import pytest
from app.mandates import service as mandates
from app.mandates.models import Mandate, MandateAction
from app.mandates.schemas import SyntheticEvidence
from app.publication import service as s
from app.publication.fixture import FixturePublicationTransport
from app.publication.models import PublicationStepRecord
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_publication_core import approved
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("stop_kind", ["cancel", "pause", "revoke"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_stop_after_mandate_dispatch_commit_prevents_first_provider_step(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stop_kind: str,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("commit interleaving requires PostgreSQL")
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
    committed, resume = Event(), Event()
    original = mandates.dispatch

    def paused_dispatch(
        db: Session,
        m: Mandate,
        a: MandateAction,
        fence: str,
        e: SyntheticEvidence,
        actor: str,
        now: datetime,
    ) -> None:
        original(db, m, a, fence, e, actor, now)
        committed.set()
        assert resume.wait(10), "customer stop did not finish"

    monkeypatch.setattr(mandates, "dispatch", paused_dispatch)
    adapter = FixturePublicationTransport()

    def worker() -> int:
        with Session(customer_engine) as db:
            try:
                s.dispatch_next(db, wid, pid, "publication-one", actor, authority, adapter, NOW)
            except HTTPException as exc:
                return exc.status_code
            return 200

    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(worker)
        try:
            assert committed.wait(10), "worker did not commit mandate dispatch"
            with Session(customer_engine) as db:
                if stop_kind == "cancel":
                    s.cancel(db, wid, pid, actor, NOW)
                else:
                    _, _, mandate, _ = s.locked(db, wid, pid)
                    mandates.stop(db, mandate, actor, NOW, revoke=stop_kind == "revoke")
                    db.commit()
        finally:
            resume.set()
        assert result.result(timeout=10) == 409
    with Session(customer_engine) as db:
        record, _, mandate, action = s.locked(db, wid, pid)
        steps = list(
            db.scalars(select(PublicationStepRecord).where(PublicationStepRecord.plan_id == pid))
        )
        assert all(step.attempt == 0 and step.request is None for step in steps)
        assert mandate.reserved_micros == 40
        assert action.state == "dispatching"
        assert record.state == ("cancel_requested" if stop_kind == "cancel" else "approved")


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_delayed_submission_is_not_retried_from_absent_readback(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    adapter = FixturePublicationTransport()
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        request = s.claim_next(db, wid, pid, "publication-one", actor, authority, NOW)
        assert request is not None
    waiting, resume = Event(), Event()

    def delayed_worker() -> int:
        waiting.set()
        assert resume.wait(10)
        receipt = adapter.apply_once(request, NOW)
        with Session(customer_engine) as db:
            try:
                s.record_receipt(db, wid, pid, receipt, NOW)
            except HTTPException as exc:
                return exc.status_code
            return 200

    with ThreadPoolExecutor(max_workers=1) as pool:
        original = pool.submit(delayed_worker)
        try:
            assert waiting.wait(10)
            with Session(customer_engine) as db:
                s.reconcile_step(db, wid, pid, request.step.step_id, adapter, NOW)
                replacement = s.dispatch_next(
                    db, wid, pid, "publication-one", actor, authority, adapter, NOW
                )
        finally:
            resume.set()
        original_status = original.result(timeout=10)
    assert len(adapter.resources) == 1
    assert adapter.calls == 1 and replacement is None and original_status == 200
    with Session(customer_engine) as db:
        row = db.get(PublicationStepRecord, (pid, request.step.step_id))
        assert row is not None and row.state == "verified" and row.fence == request.fence
