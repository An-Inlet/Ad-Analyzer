"""Genuine approved source followed only by current draft/role/stop operations."""

import json
import re
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from app.api import customer_mandates as api
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import Base
from app.goals import service as goals
from app.mandates import service as simulation
from app.mandates.models import Mandate
from app.mandates.schemas import MandateDefinition
from app.shopify.security import utc
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import (
    SourceIds,
    current_policy,
    financial_source_engine,
    retained_financial_source,
    schema_snapshot,
)
from tests.test_customer_identity import FakeProvider, login, replicas
from tests.test_inlet_customer_journey import JourneyClock

Change = Literal["edit", "pause", "none"]


def normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return utc(value)
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    with engine.connect() as db:
        return {
            table.name: sorted(
                [normalize(dict(row)) for row in db.execute(select(table)).mappings()],
                key=canonical,
            )
            for table in Base.metadata.sorted_tables
            if table.name.startswith(("provider_", "customer_campaign"))
            or table.name
            in {
                "spending_mandates",
                "spending_mandate_revisions",
                "mandate_actions",
                "mandate_audits",
                "optimization_mandate_preparations",
                "google_original_completions",
            }
        }


def assert_delta(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    ids: SourceIds,
    policy: MandateDefinition,
    change: Change,
) -> None:
    expected = deepcopy(before)
    if change != "none":
        rows = expected["spending_mandates"]
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == ids.simulation_mandate_id and row["workspace_id"] == ids.workspace_id
        row["paused"] = True
        if change == "edit":
            row["revision"] += 1
            row["state"] = "draft"
            expected["spending_mandate_revisions"].append(
                dict(
                    mandate_id=row["id"],
                    revision=row["revision"],
                    definition=policy.model_dump(mode="json"),
                    created_by=ids.actor_id,
                    created_at=JourneyClock.now(),
                    approved_by=None,
                    approved_at=None,
                )
            )
        old = {item["id"] for item in before["mandate_audits"]}
        added = [item for item in after["mandate_audits"] if item["id"] not in old]
        assert len(added) == 1 and re.fullmatch(r"[a-f0-9]{32}", added[0]["id"])
        expected["mandate_audits"].append(
            dict(
                id=added[0]["id"],
                mandate_id=row["id"],
                action_id=None,
                event="revised_simulation" if change == "edit" else "paused",
                actor=ids.actor_id,
                created_at=JourneyClock.now(),
            )
        )
    expected = {name: sorted(rows, key=canonical) for name, rows in expected.items()}
    assert after == expected


@dataclass
class PlanReviewCase:
    engine: Engine
    ids: SourceIds
    revision: int
    policy: MandateDefinition
    ceiling: int
    clients: tuple[TestClient, TestClient, FakeProvider]

    def check(self, before: dict[str, list[dict[str, Any]]], change: Change) -> None:
        actual = graph(self.engine)
        assert_delta(before, actual, self.ids, self.policy, change)
        # A copied row must not hide extra financial movement; actual SQL stays unchanged.
        corrupted = deepcopy(actual)
        corrupted["spending_mandates"][0]["observed_micros"] += 1
        with pytest.raises(AssertionError):
            assert_delta(before, corrupted, self.ids, self.policy, change)


@pytest.fixture
def plan_review_case(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Iterator[PlanReviewCase]:
    name = request.node.originalname
    assert name in {
        "test_approval_rechecks_after_real_postgres_workspace_wait",
        "test_current_role_permissions_and_guard_default",
    }
    if name == "test_approval_rechecks_after_real_postgres_workspace_wait":
        assert request.node.callspec.params["change"] in {"revoked_session", "lost_owner"}
        if customer_engine.dialect.name != "postgresql":
            pytest.skip("PostgreSQL row-lock race")
    else:
        assert request.node.callspec.params["role"] in {"owner", "admin", "analyst", "viewer"}
    root = tmp_path / "current-source"
    assert root.is_absolute() and root.resolve() == root
    assert not root.exists() and all(not p.is_symlink() for p in root.parents)
    root.mkdir()
    if customer_engine.dialect.name == "sqlite":
        file = root / "financial.sqlite"
        file.touch(exist_ok=False)
        assert file.is_file() and not file.is_symlink() and file.resolve() == file
    with financial_source_engine(customer_engine, root) as engine:
        ids = retained_financial_source(engine, root / "original", "source_only")
        physical = schema_snapshot(engine)
        before = graph(engine)
        with Session(engine) as db:
            current_policy(db, ids)
            mandate = db.get(Mandate, ids.simulation_mandate_id)
            user = db.get(CustomerUser, ids.actor_id)
            assert mandate and user and user.issuer == "mock" and user.subject == user.id
            identity = dict(issuer=user.issuer, subject=user.subject, email=user.email)
            policy = simulation.policy(db, mandate)
            simulation.edit(db, mandate, mandate.revision, policy, ids.actor_id, JourneyClock.now())
            goal = goals.owned(db, ids.workspace_id, policy.goal_id)
            definition = goals.current(db, goal).definition
            assert definition is not None
            ceiling = definition["budget_micros"]
            db.commit()
            revision = mandate.revision
        assert_delta(before, graph(engine), ids, policy, "edit")
        clients = cast(
            tuple[TestClient, TestClient, FakeProvider],
            cast(Any, replicas).__wrapped__(engine, monkeypatch),
        )
        try:
            clients[2].issuer, clients[2].email = identity["issuer"], identity["email"]
            clients[0].app.include_router(api.router)  # type: ignore[attr-defined]
            monkeypatch.setattr(api, "datetime", JourneyClock)
            with Session(engine) as db:
                prior = set(db.scalars(select(CustomerSession.digest)))
            assert login(clients[0], ids.actor_id + ":current-review") == ids.actor_id
            with Session(engine) as db:
                user = db.get(CustomerUser, ids.actor_id)
                assert (
                    user
                    and dict(issuer=user.issuer, subject=user.subject, email=user.email) == identity
                )
                token = digest(clients[0].cookies[SESSION_COOKIE])
                session = db.get(CustomerSession, token)
                assert session and session.user_id == ids.actor_id and token not in prior
            frozen = graph(engine)
            case = PlanReviewCase(engine, ids, revision, policy, ceiling, clients)
            yield case
            final = graph(engine)
            for name, rows in frozen.items():
                if name not in {
                    "spending_mandates",
                    "spending_mandate_revisions",
                    "mandate_audits",
                }:
                    assert final[name] == rows
            with Session(engine) as db:
                user = db.get(CustomerUser, ids.actor_id)
                assert (
                    user
                    and dict(issuer=user.issuer, subject=user.subject, email=user.email) == identity
                )
            assert schema_snapshot(engine) == physical
        finally:
            try:
                clients[0].close()
            finally:
                clients[1].close()
