"""Actual current Meta/Shopify history without an execution acquisition anchor."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.goals import service as goals
from app.initial_planning.models import ObservationRow
from app.meta.models import MetaConnection
from app.meta.security import Vault
from app.reported_feedback.models import ReportedFeedbackJob, ReportedWindowCapsule
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import login
from tests.test_initial_planning_api import ready_history
from tests.tiktok_read_fixture import assert_no_advertising_authority


@dataclass(frozen=True)
class MetaBudgetReadIds:
    workspace_id: int
    goal_id: str
    goal_revision: int
    account_id: int
    campaign_id: int
    source_id: int
    actor_id: str
    session_digest: str
    observation_id: str
    now: datetime


def prepare_meta_budget_read(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> MetaBudgetReadIds:
    assert_no_advertising_authority(engine)
    actor = login(replicas[0], "meta-read:1")
    token = digest(replicas[0].cookies[SESSION_COOKIE])
    with Session(engine) as db:
        user, session = db.get(CustomerUser, actor), db.get(CustomerSession, token)
        assert user and session
        wid, gid, aid, cid, runtime, observations = ready_history(
            engine, configuration, monkeypatch, CustomerPrincipal(user, session), replicas[2]
        )
    now = runtime.clock()
    with Session(engine) as db:
        source = db.scalar(select(MetaConnection).where(MetaConnection.account_id == aid))
        assert source and source.workspace_id == wid
        assert source.last_sync_at is not None
        goal = goals.owned(db, wid, gid)
        assert goal.revision == 1 and goals.assessment(db, goal, now) == "confirmed"
        observed = db.get(ObservationRow, observations[-1])
        assert observed and observed.account_id == aid and observed.campaign_id == cid
        assert observed.completion_id
        for model in (ReportedFeedbackJob, ReportedWindowCapsule):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        source.encrypted_credentials = Vault(configuration).seal(
            wid,
            source.external_account_id,
            {
                "access_token": "offline-report-token",
                "expires_at": (now + timedelta(days=90)).isoformat(),
            },
        )
        db.commit()
        result = MetaBudgetReadIds(
            wid, gid, 1, aid, cid, source.id, actor, token, observations[-1], now
        )
    assert_no_advertising_authority(engine)
    return result
