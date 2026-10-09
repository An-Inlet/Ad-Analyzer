"""Original reported acquisition lineage, then current native restore assertions."""

import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.inlet_restore_historical import PIN, extract
from sqlalchemy import Engine, inspect, text

from tests.retired_snapshot import run_bounded
from tests.social_restore_boundary import fresh, owned, read_output, unchanged


@dataclass(frozen=True)
class RetainedReportedRestoreIds:
    workspace_id: int
    source_id: int
    job_id: str
    comparison_id: str
    slot_id: str
    session_digest: str
    slot_digest: str
    observed_at: str
    receipt_count: int
    hold_count: int
    provider_posts: int


def retained_reported_restore_fixture(
    engine: Engine, artifacts: Path
) -> RetainedReportedRestoreIds:
    schema = owned(engine, "reported")
    snapshot = fresh(engine)
    tables = set(inspect(engine).get_table_names())
    artifacts.mkdir(parents=True)
    source = artifacts / "source"
    extract(source)
    output, log = artifacts / "ids.json", artifacts / "producer.log"
    root = Path(__file__).resolve().parents[1]
    code = run_bounded(
        [
            sys.executable,
            str(root / "tests/fixtures/retired_execution/reported_restore_seed_driver.py"),
            schema,
            str(artifacts),
        ],
        source,
        dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(source)),
        log,
        180,
    )
    assert code == 0, log.read_text()[-6000:]
    raw = read_output(output, set(RetainedReportedRestoreIds.__dataclass_fields__))
    assert type(raw["observed_at"]) is str
    when = datetime.fromisoformat(raw["observed_at"])
    assert when.tzinfo == UTC and when.isoformat() == raw["observed_at"]
    result = RetainedReportedRestoreIds(**raw)
    assert result.provider_posts == 1
    assert set(inspect(engine).get_table_names()) == tables
    owned(engine, "reported")
    unchanged(engine, snapshot)
    with engine.connect() as db:
        row = db.execute(
            text(
                "SELECT workspace_id,document_digest,document "
                "FROM reported_feedback_slots WHERE id=:id"
            ),
            {"id": result.slot_id},
        ).one()
        assert row.workspace_id == result.workspace_id and row.document_digest == result.slot_digest
        assert row.document["proposed_budget_micros"] == 47000000
        job = db.execute(
            text(
                "SELECT workspace_id,source_connection_id,original_session_digest "
                "FROM reported_feedback_jobs WHERE id=:id"
            ),
            {"id": result.job_id},
        ).one()
        assert tuple(job) == (result.workspace_id, result.source_id, result.session_digest)
        assert (
            db.scalar(
                text("SELECT workspace_id FROM reported_action_comparisons WHERE id=:id"),
                {"id": result.comparison_id},
            )
            == result.workspace_id
        )
        for table, count in (
            ("provider_execution_receipts", result.receipt_count),
            ("provider_exposure_reservations", result.hold_count),
        ):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == count
    return result
