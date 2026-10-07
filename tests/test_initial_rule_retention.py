"""No expired pending data delivery or counter churn from actual UTC cleanup."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.campaign_review.storage import LocalMediaStore
from app.initial_planning.automatic_models import InitialRuleOpportunity
from app.initial_planning.automatic_retention import purge_expired_initial_rules
from app.lifecycle.exports import SLOTS, Download
from app.lifecycle.privacy import workspace_export_revision
from app.publication.execution_models import ProviderPeriodLedger
from fastapi import HTTPException
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from tests.test_customer_exports import build, prepared
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine


def pending(db: Session, wid: int, deadline: datetime) -> str:
    ledger = ProviderPeriodLedger(
        id=uuid4().hex,
        workspace_id=wid,
        environment="contract_test",
        currency="USD",
        starts_at=deadline - timedelta(days=1),
        ends_at=deadline + timedelta(days=1),
    )
    db.add(ledger)
    db.flush()
    key = uuid4().hex * 2
    db.add(
        InitialRuleOpportunity(
            id=key[:32],
            workspace_id=wid,
            environment="contract_test",
            ledger_id=ledger.id,
            native_account_identity_digest="a" * 64,
            budget_owner_identity_digest="b" * 64,
            semantic_key_digest=key,
            created_at=deadline - timedelta(minutes=5),
            pending_expires_at=deadline,
        )
    )
    db.commit()
    return key[:32]


def test_pre_expiry_raw_deletion_revokes_prepared_archive(
    export_engine: Engine,
    tmp_path: Path,
) -> None:
    authority, wid = prepared(export_engine)
    with Session(export_engine) as db:
        identifier = pending(db, wid, datetime.now(UTC) + timedelta(minutes=1))
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    authority.finish(manifest)
    with Session(export_engine) as db:
        before = workspace_export_revision(db, wid)
        db.execute(delete(InitialRuleOpportunity).where(InitialRuleOpportunity.id == identifier))
        db.commit()
        assert workspace_export_revision(db, wid) > before
    assert SLOTS.acquire(blocking=False)
    with pytest.raises(HTTPException):
        next(Download(file, authority).chunks())
    assert file.closed


def test_actual_expired_pending_cleanup_preserves_counter_and_cannot_deliver(
    export_engine: Engine,
    tmp_path: Path,
) -> None:
    authority, wid = prepared(export_engine)
    deadline = datetime.now(UTC) - timedelta(seconds=1)
    with Session(export_engine) as db:
        identifier = pending(db, wid, deadline)
        before = workspace_export_revision(db, wid)
    with pytest.raises(HTTPException, match="retention expired"):
        build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    assert purge_expired_initial_rules(lambda: Session(export_engine)) == 1
    with Session(export_engine) as db:
        assert db.get(InitialRuleOpportunity, identifier) is None
        assert workspace_export_revision(db, wid) == before
    # Captured retention deadline remains authoritative even after rows disappear.
    with pytest.raises(HTTPException, match="retention expired"):
        authority.check_retention(datetime.now(UTC))
