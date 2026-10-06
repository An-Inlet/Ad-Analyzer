"""Shared privacy counter rollback/status semantics, without provider IO."""

import pytest
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import seed


def test_revision_tracks_transaction_not_customer_access(customer_engine: Engine) -> None:
    from app.workspaces.models import Workspace

    with Session(customer_engine) as db:
        _, wid = seed(db)
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.status = "closing"
        db.commit()
        assert workspace_export_revision(db, wid) == 0
        bump_workspace_export_revision(db, wid)
        assert workspace_export_revision(db, wid) == 1
        db.rollback()
        assert workspace_export_revision(db, wid) == 0
        bump_workspace_export_revision(db, wid)
        db.commit()
        assert workspace_export_revision(db, wid) == 1
        with pytest.raises(ValueError, match="unavailable"):
            bump_workspace_export_revision(db, wid + 10000)
