"""Coherent closed original and exact draft-only current confirmation delta."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.customers.access import CustomerPrincipal
from app.initial_planning.budget_mandate_models import BudgetMandatePreparationRow
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.initial_planning.planning_consents import checked_planning_limits
from app.initial_planning.runtime import InitialPlanningRuntime
from app.publication.execution_models import (
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionRevision,
)
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.reported_original_fixture import RetainedReportedOriginalIds, effect_graph
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_customer_identity import FakeProvider


def row_values(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


class ExpectedPlanningConfirmation:
    """One checked new planning reference; no arbitrary rows or callback supplied."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] | None = None
        self._ids: RetainedReportedOriginalIds | None = None

    def bind(
        self,
        db: Session,
        ids: RetainedReportedOriginalIds,
        principal: CustomerPrincipal,
        runtime: InitialPlanningRuntime,
        mandate_id: str,
        revision: int,
    ) -> None:
        assert self._rows is None and mandate_id != ids.mandate_id and revision == 1
        policy = checked_planning_limits(
            db, principal, FakeProvider(), ids.workspace_id, mandate_id, revision, runtime
        )
        assert (policy.goal_id, policy.goal_revision) == (ids.goal_id, ids.goal_revision)
        assert len(policy.accounts) == 1 and policy.accounts[0].account.account_id == ids.account_id
        original = db.get(ProviderExecutionMandate, ids.mandate_id)
        mandate = db.get(ProviderExecutionMandate, mandate_id)
        assert original and mandate and mandate.ledger_id == original.ledger_id
        assert mandate.state == "draft" and mandate.revision == revision
        assert (
            db.scalar(
                select(ProviderExecutionConsent).where(
                    ProviderExecutionConsent.mandate_id == mandate_id,
                    ProviderExecutionConsent.revision == revision,
                )
            )
            is None
        )
        stored = db.get(ProviderExecutionRevision, (mandate_id, revision))
        preparation = db.get(BudgetMandatePreparationRow, (mandate_id, revision))
        consent = db.get(PlanningConsentRow, (mandate_id, revision))
        assert stored and preparation and consent
        self._rows = {
            row.__tablename__: deepcopy(row_values(row))
            for row in (mandate, stored, preparation, consent)
        }
        self._ids = ids

    def assert_delta(
        self,
        engine: Engine,
        ids: RetainedReportedOriginalIds,
        before: dict[str, list[dict[str, Any]]],
    ) -> None:
        after = effect_graph(engine)
        if self._rows is None:
            assert after == before
            with Session(engine) as db:
                for model in (BudgetMandatePreparationRow, PlanningConsentRow):
                    assert db.scalar(select(func.count()).select_from(model)) == 0
            return
        assert self._ids == ids
        expected = deepcopy(before)
        for table in ("provider_execution_mandates", "provider_execution_revisions"):
            expected[table].append(self._rows[table])
        # Compare canonical primary-key query order, including every original row.
        for table in expected:
            assert len(after[table]) == len(expected[table])
            assert all(row in after[table] for row in expected[table])
        with Session(engine) as db:
            for model in (BudgetMandatePreparationRow, PlanningConsentRow):
                rows = list(db.scalars(select(model)))
                assert len(rows) == 1 and row_values(rows[0]) == self._rows[model.__tablename__]


@contextmanager
def retained_reported_planning_original_fixture(
    engine: Engine,
    artifacts: Path,
    *,
    expectation: ExpectedPlanningConfirmation,
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
    with engine.connect() as empty_check:
        for table in sorted(tables - {"alembic_version"}):
            quoted = engine.dialect.identifier_preparer.quote(table)
            assert empty_check.execute(text(f"SELECT 1 FROM {quoted} LIMIT 1")).first() is None
    root = Path(__file__).resolve().parents[1]
    with SourceLifetime.open("reported_planning_original", artifacts) as lifetime:
        snapshot = lifetime.source
        extract(root, snapshot)
        lifetime.extracted()
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        lifetime.child_started()
        code = run_bounded(
            [
                sys.executable,
                str(
                    root
                    / "tests/fixtures/retired_execution/reported_planning_original_seed_driver.py"
                ),
                target,
                str(output),
            ],
            snapshot,
            dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot)),
            log,
            180,
        )
        lifetime.after_reaped(code)
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
    try:
        yield engine, ids
    finally:
        expectation.assert_delta(engine, ids, before)
