"""One authentic pinned effect; only current reporting consumes retained scalar IDs."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from app import advertising_capabilities
from app.ads.models import Campaign
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import Base
from app.initial_planning.runtime import InitialPlanningRuntime
from app.meta.models import MetaConnection
from app.meta.security import utc
from app.publication import execution_mandates, optimization
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionMandate,
    ProviderExecutionReceipt,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.reported_feedback.contracts import ComparisonIntentV1, ComparisonProgressV1
from app.reported_feedback.models import (
    ReportedActionComparison,
    ReportedFeedbackJob,
    ReportedFeedbackSlot,
    ReportedWindowCapsule,
)
from app.reported_feedback.runtime import ReportedFeedbackRuntime
from app.reported_feedback.service import request_comparison
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.reported_feedback_fixture import window_policy
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_customer_identity import FakeProvider


@dataclass(frozen=True)
class RetainedReportedOriginalIds:
    workspace_id: int
    actor_id: str
    session_digest: str
    account_id: int
    campaign_id: int
    source_id: int
    goal_id: str
    goal_revision: int
    mandate_id: str
    review_id: str
    run_id: str
    attempt_id: str
    receipt_id: str
    reservation_id: str
    original_post_count: int


def effect_graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    """Full persisted financial/effect rows, independent of source/session drift tests."""
    assert advertising_capabilities.advertising_writes_enabled() is False
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
            if table.name.startswith("provider_") or table.name == "mandate_actions"
        }


class ExpectedUnknownReadback:
    """One explicit current GET time; never a supplied expected receipt or authority."""

    def __init__(self) -> None:
        self._observed_at: datetime | None = None

    def arm(self, observed_at: datetime) -> None:
        assert self._observed_at is None
        assert isinstance(observed_at, datetime) and observed_at.utcoffset() == UTC.utcoffset(None)
        self._observed_at = observed_at

    @property
    def observed_at(self) -> datetime:
        assert self._observed_at is not None
        return self._observed_at


def assert_no_attempt_derivatives(db: Session) -> None:
    from app.optimization_candidates.models import CandidateJob
    from app.outcome_feedback.models import V3Assessment

    for model in (CandidateJob, V3Assessment):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def assert_unknown_readback_delta(
    engine: Engine,
    ids: RetainedReportedOriginalIds,
    before: dict[str, list[dict[str, Any]]],
    expected_unknown: ExpectedUnknownReadback,
) -> None:
    after = effect_graph(engine)
    original = before["provider_execution_receipts"]
    assert len(original) == 1 and original[0]["id"] == ids.receipt_id
    appended = [r for r in after["provider_execution_receipts"] if r["id"] != ids.receipt_id]
    assert len(appended) == 1 and len(after["provider_execution_receipts"]) == 2
    new = appended[0]
    assert (new["workspace_id"], new["attempt_id"], new["sequence"], new["supersedes_id"]) == (
        ids.workspace_id,
        ids.attempt_id,
        2,
        ids.receipt_id,
    )
    assert utc(new["observed_at"]) == expected_unknown.observed_at
    with Session(engine) as db:
        run, _, _, request = optimization.evidence_lock(db, ids.workspace_id, ids.attempt_id)
        assert run.id == ids.run_id
        receipt = optimization.unknown(request, lambda: expected_unknown.observed_at)
        assert new["receipt"] == receipt.model_dump(mode="json")
        latest = optimization.read_owned_outcome_receipt(
            db, ids.workspace_id, ids.attempt_id, ids.actor_id
        )
        assert latest and latest.receipt_id == new["id"] and latest.sequence == 2
        assert latest.outcome == "unknown" and latest.model_dump(mode="json") == new["projection"]
        assert db.get(ProviderExecutionReceipt, ids.receipt_id)
        assert_no_attempt_derivatives(db)
    expected = deepcopy(before)
    expected["provider_execution_receipts"].append(new)
    expected["provider_execution_receipts"].sort(key=lambda r: r["id"])
    for table in ("provider_execution_runs", "provider_execution_steps"):
        assert len(expected[table]) == 1
        row = expected[table][0]
        assert (row["id"] if table == "provider_execution_runs" else row["run_id"]) == ids.run_id
        assert row["state"] == "verified_target_state"
        row["state"] = "unknown"
    assert after == expected


@pytest.fixture
def customer_engine(base_customer_engine: Engine, tmp_path: Path) -> Iterator[Engine]:
    if base_customer_engine.dialect.name != "sqlite":
        yield base_customer_engine
        return
    engine = create_engine(f"sqlite:///{tmp_path / 'current.sqlite'}")
    event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@contextmanager
def retained_reported_original_fixture(
    engine: Engine,
    artifacts: Path,
    *,
    expected_unknown: ExpectedUnknownReadback | None = None,
) -> Iterator[tuple[Engine, RetainedReportedOriginalIds]]:
    artifacts.mkdir(parents=True)
    if engine.dialect.name == "sqlite":
        assert engine.url.database and engine.url.database != ":memory:"
        target = str(engine.url)
    else:
        safe_url = make_url(validate_disposable_url())
        assert safe_url.host in {"localhost", "127.0.0.1", "::1"} and not safe_url.query
        assert engine.url == safe_url
        with engine.connect() as connection:
            target = str(connection.scalar(text("select current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    assert all(not rows for rows in effect_graph(engine).values())
    tables = set(inspect(engine).get_table_names())
    root = Path(__file__).resolve().parents[1]
    snapshot = artifacts / "source"
    extract(root, snapshot)
    output, log = artifacts / "ids.json", artifacts / "producer.log"
    code = run_bounded(
        [
            sys.executable,
            str(root / "tests/fixtures/retired_execution/reported_original_seed_driver.py"),
            target,
            str(output),
        ],
        snapshot,
        dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot)),
        log,
        180,
    )
    assert code == 0, log.read_text()[-6000:]
    assert 0 < output.stat().st_size <= 4096
    raw = json.loads(output.read_text())
    assert type(raw) is dict
    assert set(raw) == set(RetainedReportedOriginalIds.__dataclass_fields__)
    integer_fields = {
        "workspace_id",
        "account_id",
        "campaign_id",
        "source_id",
        "goal_revision",
        "original_post_count",
    }
    for key, value in raw.items():
        if key in integer_fields:
            assert type(value) is int and value > 0
        else:
            assert isinstance(value, str) and re.fullmatch(
                r"[a-f0-9]{64}" if key == "session_digest" else r"[a-f0-9]{32}", value
            )
    ids = RetainedReportedOriginalIds(**raw)
    assert ids.original_post_count == 1
    assert set(inspect(engine).get_table_names()) == tables
    before = effect_graph(engine)
    assert len(before["provider_execution_attempts"]) == 1
    assert len(before["provider_execution_responses"]) == 1
    assert len(before["provider_execution_receipts"]) == 1
    assert len(before["provider_exposure_reservations"]) == 1
    if expected_unknown is not None:
        with Session(engine) as db:
            assert_no_attempt_derivatives(db)
    try:
        yield engine, ids
    finally:
        if expected_unknown is None:
            assert effect_graph(engine) == before
        else:
            assert_unknown_readback_delta(engine, ids, before, expected_unknown)


@pytest.fixture
def reported_original(
    customer_engine: Engine, tmp_path: Path
) -> Iterator[RetainedReportedOriginalIds]:
    with retained_reported_original_fixture(customer_engine, tmp_path / "original") as (_, ids):
        yield ids


class PreparedReportedRead(NamedTuple):
    workspace_id: int
    principal: CustomerPrincipal
    provider: FakeProvider
    runtime: ReportedFeedbackRuntime
    intent: ComparisonIntentV1
    progress: ComparisonProgressV1
    clock: list[datetime]
    original: RetainedReportedOriginalIds


def prepare_reported_read(db: Session, ids: RetainedReportedOriginalIds) -> PreparedReportedRead:
    user, session = db.get(CustomerUser, ids.actor_id), db.get(CustomerSession, ids.session_digest)
    source, campaign = db.get(MetaConnection, ids.source_id), db.get(Campaign, ids.campaign_id)
    mandate = db.get(ProviderExecutionMandate, ids.mandate_id)
    attempt, receipt = (
        db.get(ProviderExecutionAttempt, ids.attempt_id),
        db.get(ProviderExecutionReceipt, ids.receipt_id),
    )
    run, reservation = (
        db.get(ProviderExecutionRun, ids.run_id),
        db.get(ProviderExposureReservation, ids.reservation_id),
    )
    assert user and session and session.user_id == user.id
    assert source and campaign and source.workspace_id == ids.workspace_id
    assert source.account_id == campaign.account_id == ids.account_id
    assert campaign.external_campaign_id == "5" and source.conversion_action_type == "purchase"
    assert mandate and mandate.workspace_id == ids.workspace_id
    assert attempt and receipt and run and reservation
    assert (
        attempt.workspace_id
        == receipt.workspace_id
        == run.workspace_id
        == reservation.workspace_id
        == ids.workspace_id
    )
    assert receipt.attempt_id == attempt.id and attempt.run_id == run.id
    assert run.review_id == ids.review_id and run.reservation_id == reservation.id
    assert reservation.state == "held"
    policy = execution_mandates.policy(db, mandate)
    assert (policy.goal_id, policy.goal_revision) == (ids.goal_id, ids.goal_revision)
    for model in (
        ReportedFeedbackJob,
        ReportedWindowCapsule,
        ReportedActionComparison,
        ReportedFeedbackSlot,
    ):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    principal, provider = CustomerPrincipal(user, session), FakeProvider()
    clock = [datetime.now(UTC)]
    engine = db.get_bind()
    runtime = ReportedFeedbackRuntime(
        initial=InitialPlanningRuntime(
            session_factory=lambda: Session(engine), clock=lambda: clock[0]
        ),
        window_policy=window_policy(),
    )
    intent = ComparisonIntentV1(
        attempt_id=ids.attempt_id,
        goal_id=ids.goal_id,
        goal_revision=ids.goal_revision,
        maximum_reported_cpa_micros=100_000_000,
    )
    progress = request_comparison(db, principal, provider, ids.workspace_id, intent, runtime)
    db.commit()
    return PreparedReportedRead(
        ids.workspace_id, principal, provider, runtime, intent, progress, clock, ids
    )
