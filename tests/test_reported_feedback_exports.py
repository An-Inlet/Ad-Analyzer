"""Actual fixed Meta acquisitions through comparison and owned ephemeral archive."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.campaign_review.storage import LocalMediaStore
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.exports import Authority
from app.lifecycle.service import begin
from app.reported_feedback.service import read_comparison
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_customer_exports import build, unpack
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_reported_feedback_acquisition import acquisition_fixture, complete
from tests.test_shopify_sales import configuration as configuration


def test_actual_comparison_archive_rechecks_original_session_without_slot(
    export_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_engine = export_engine
    monkeypatch.setattr(settings, "customer_export_enabled", True)
    with Session(customer_engine) as db:
        wid, principal, runtime, job, _, _, clock, runner, _, _, _ = acquisition_fixture(
            db, configuration, tmp_path, monkeypatch
        )
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        clock[0] += timedelta(seconds=61)
        complete(runner, wid, clock[0])
        complete(runner, wid, clock[0])
        comparison = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        assert comparison.status == "operational_reported_as_of"
        db.commit()
        original = principal.session.digest
        # Export from another still-valid owner session. Revoking the original
        # comparison session later must be detected by numeric dependency checks,
        # not accidentally by the export session's ordinary authentication check.
        export_session = CustomerSession(
            digest=uuid4().hex * 2,
            user_id=principal.user.id,
            csrf_digest="f" * 64,
            created_at=int(datetime.now(UTC).timestamp()),
            authenticated_at=int(datetime.now(UTC).timestamp()),
            expires_at=principal.session.expires_at,
        )
        db.add(export_session)
        db.flush()
        exporter = CustomerPrincipal(principal.user, export_session)
        request = begin(
            db,
            exporter,
            FakeProvider(),
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "reported-export-fixture",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(customer_engine, exporter, FakeProvider(), wid, request.id)
    # The existing acquisition fixture observes a closed future after-window via
    # an explicit offline clock. No production clock/configuration is changed.
    monkeypatch.setattr("app.lifecycle.privacy.database_utc_now", lambda db: clock[0])
    monkeypatch.setattr("app.lifecycle.exports.database_utc_now", lambda db: clock[0])
    authority.claim()
    file, manifest = build(customer_engine, authority, LocalMediaStore(tmp_path))
    try:
        _, entries = unpack(file)
        assert manifest["supported_customer_data_complete"]
        assert comparison.id.encode() in entries["data/reported_action_comparisons.jsonl"]
        assert original.encode() not in b"".join(entries.values())
        authority.check()
        with Session(customer_engine) as db:
            session = db.get(CustomerSession, original)
            assert session
            session.revoked_at = int(datetime.now(UTC).timestamp())
            db.commit()
        with pytest.raises(HTTPException, match="original_session_unavailable"):
            authority.check()
    finally:
        file.close()
