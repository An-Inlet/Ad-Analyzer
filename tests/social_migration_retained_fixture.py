"""Two closed producer phases around parent-owned actual migration DDL."""

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.inlet_restore_historical import PIN, extract
from sqlalchemy import Engine, inspect, text

from tests.social_restore_boundary import fresh, owned, read_output, unchanged


@dataclass(frozen=True)
class SocialPreparedIds:
    workspace_id: int
    actor_id: str
    run_id: str
    provider_posts: int


@dataclass(frozen=True)
class SocialConfirmedIds(SocialPreparedIds):
    configuration_review_id: str
    configuration_digest: str
    run_count: int


def wait_child(
    process: subprocess.Popen[bytes], log: Path, started: float, output: Path | None = None
) -> None:
    while True:
        assert time.monotonic() - started <= 180, "social producer deadline"
        assert log.stat().st_size <= 16 * 1024 * 1024, "social producer output bound"
        if output is not None and output.exists():
            return
        code = process.poll()
        if code is not None:
            assert code == 0 and output is None, log.read_text()[-6000:]
            return
        time.sleep(0.05)


def stop_child(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


class SocialPhases:
    def __init__(
        self,
        engine: Engine,
        artifacts: Path,
        process: subprocess.Popen[bytes],
        started: float,
        snapshot: dict[str, list[dict[str, Any]]],
    ) -> None:
        self.engine, self.artifacts, self.process = engine, artifacts, process
        self.started, self.snapshot, self.finished = started, snapshot, False
        self.tables = set(inspect(engine).get_table_names())
        owned(engine, "social", "20261006_0057")
        raw = read_output(artifacts / "prepared.json", set(SocialPreparedIds.__dataclass_fields__))
        self.prepared = SocialPreparedIds(**raw)
        assert self.prepared.provider_posts == 0
        with engine.connect() as db:
            assert db.execute(
                text("SELECT workspace_id,id FROM provider_execution_runs")
            ).one() == (self.prepared.workspace_id, self.prepared.run_id)

    def confirm_after_upgrade(self) -> SocialConfirmedIds:
        assert not self.finished
        owned(self.engine, "social", "20261006_0059")
        assert set(inspect(self.engine).get_table_names()) == self.tables | {
            "customer_social_configuration_reviews",
            "customer_social_configuration_approvals",
        }
        marker = self.artifacts / "continue.json"
        pending = self.artifacts / "continue.tmp"
        pending.write_text(json.dumps({"phase": "confirm0059"}))
        pending.replace(marker)
        wait_child(self.process, self.artifacts / "producer.log", self.started)
        raw = read_output(
            self.artifacts / "confirmed.json", set(SocialConfirmedIds.__dataclass_fields__)
        )
        result = SocialConfirmedIds(**raw)
        assert all(
            getattr(result, k) == getattr(self.prepared, k)
            for k in SocialPreparedIds.__dataclass_fields__
        )
        assert result.run_count == 1
        owned(self.engine, "social", "20261006_0059")
        assert set(inspect(self.engine).get_table_names()) == self.tables | {
            "customer_social_configuration_reviews",
            "customer_social_configuration_approvals",
        }
        unchanged(self.engine, self.snapshot)
        self.finished = True
        return result


@contextmanager
def retained_social_configuration_fixture(
    engine: Engine, artifacts: Path
) -> Iterator[SocialPhases]:
    schema = owned(engine, "social", "20261006_0057")
    snapshot = fresh(engine)
    assert "customer_social_configuration_reviews" not in inspect(engine).get_table_names()
    artifacts.mkdir(parents=True)
    with SourceLifetime.open("social_configuration", artifacts) as lifetime:
        source = lifetime.source
        extract(source)
        lifetime.extracted()
        root = Path(__file__).resolve().parents[1]
        with (artifacts / "producer.log").open("wb") as log:
            lifetime.child_started()
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/social_migration_seed_driver.py"),
                    schema,
                    str(artifacts),
                ],
                cwd=source,
                env=dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(source)),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            started = time.monotonic()
            try:
                wait_child(
                    process, artifacts / "producer.log", started, artifacts / "prepared.json"
                )
                yield SocialPhases(engine, artifacts, process, started, snapshot)
            finally:
                stop_child(process)
                assert process.returncode is not None
                lifetime.after_reaped(process.returncode)
