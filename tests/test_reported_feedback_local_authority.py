"""Background phases use original local authority without provider identity IO."""

from datetime import UTC, datetime

import pytest
from app.reported_feedback.models import ReportedFeedbackJob
from app.reported_feedback.service import local_job_authority
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import seed


@pytest.mark.parametrize("change", ["none", "logout", "membership", "closed"])
def test_local_original_authority(customer_engine: Engine, change: str) -> None:
    from app.customers.models import CustomerMembership
    from app.workspaces.models import Workspace

    with Session(customer_engine) as db:
        principal, wid = seed(db)
        job = ReportedFeedbackJob(
            workspace_id=wid,
            original_actor_id=principal.user.id,
            original_session_digest=principal.session.digest,
        )
        now = datetime.now(UTC)
        if change == "logout":
            principal.session.revoked_at = int(now.timestamp())
        elif change == "membership":
            member = db.get(CustomerMembership, (principal.user.id, wid))
            assert member is not None
            member.status = "suspended"
        elif change == "closed":
            workspace = db.get(Workspace, wid)
            assert workspace is not None
            workspace.status = "inactive"
        db.commit()
        if change == "none":
            actual = local_job_authority(db, job, now, lock=True)
            assert actual.session.digest == principal.session.digest
        else:
            with pytest.raises(HTTPException, match="original_session_unavailable"):
                local_job_authority(db, job, now, lock=True)
