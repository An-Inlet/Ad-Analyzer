"""Coherent closed original and exact draft-only current confirmation delta."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, inspect, text
from sqlalchemy.engine import make_url

from tests.reported_original_fixture import RetainedReportedOriginalIds, effect_graph
from tests.reported_planning_original_fixture import ExpectedPlanningConfirmation
from tests.retired_snapshot import PIN, extract, run_bounded


@contextmanager
def retained_reported_planning_relative_fixture(
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
    with SourceLifetime.open("reported_planning_relative_original", artifacts) as lifetime:
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
                    / "tests/fixtures/retired_execution/reported_planning_relative_seed_driver.py"
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
