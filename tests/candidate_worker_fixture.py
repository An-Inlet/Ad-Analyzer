"""Closed two-owner source records; current tests enqueue and schedule their own jobs."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from app.database.session import Base
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, func, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.retired_snapshot import PIN, extract, run_bounded

if TYPE_CHECKING:
    from tests.candidate_read_retained_fixture import CandidateReadIds


@contextmanager
def retained_dual_candidate_sources(
    customer_engine: Engine, artifacts: Path
) -> Iterator[tuple[Engine, dict[str, "CandidateReadIds"]]]:
    from app.optimization_candidates.models import CandidateJob, CandidateResult

    from tests.candidate_read_retained_fixture import (
        CandidateReadIds,
        load_candidate_read_fixture,
        no_effects,
    )

    artifacts.mkdir(parents=True)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        url = make_url(validate_disposable_url())
        assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        assert engine.url == url
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        no_effects(engine)
        tables = set(inspect(engine).get_table_names())
        root = Path(__file__).resolve().parents[1]
        snapshot = artifacts / "source"
        extract(root, snapshot)
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        code = run_bounded(
            [
                sys.executable,
                str(root / "tests/fixtures/retired_execution/candidate_worker_seed_driver.py"),
                target,
                str(output),
            ],
            snapshot,
            dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot)),
            log,
            180,
        )
        assert code == 0, log.read_text()[-6000:]
        assert output.stat().st_size <= 8192
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == {"first", "second"}
        values = {}
        for name in ("first", "second"):
            item = raw[name]
            assert type(item) is dict and set(item) == set(CandidateReadIds.__dataclass_fields__)
            for field in ("workspace_id", "mandate_revision", "account_id"):
                assert type(item[field]) is int and item[field] > 0
            assert type(item["provider_posts"]) is int and item["provider_posts"] == 0
            assert item["provider"] == "google_ads"
            for field in (
                "actor_id",
                "mandate_id",
                "consent_id",
                "ledger_id",
                "store_id",
                "publication_id",
            ):
                assert type(item[field]) is str and re.fullmatch(r"[a-f0-9]{32}", item[field])
            for field in ("session_digest", "policy_digest"):
                assert type(item[field]) is str and re.fullmatch(r"[a-f0-9]{64}", item[field])
            values[name] = CandidateReadIds(**item)
        for field in (
            "workspace_id",
            "actor_id",
            "session_digest",
            "account_id",
            "store_id",
            "publication_id",
            "mandate_id",
            "consent_id",
            "ledger_id",
        ):
            assert getattr(values["first"], field) != getattr(values["second"], field)
        assert set(inspect(engine).get_table_names()) == tables
        with Session(engine) as db:
            for model in (CandidateJob, CandidateResult):
                assert db.scalar(select(func.count()).select_from(model)) == 0
            for ids in values.values():
                load_candidate_read_fixture(db, ids)
        no_effects(engine)
        try:
            yield engine, values
        finally:
            no_effects(engine)
    finally:
        if engine is not customer_engine:
            engine.dispose()


@pytest.fixture
def current_dual_candidate_read(
    customer_engine: Engine, tmp_path: Path
) -> Iterator[tuple[Engine, dict[str, "CandidateReadIds"]]]:
    with retained_dual_candidate_sources(
        customer_engine, tmp_path / "dual-candidate-source"
    ) as pair:
        yield pair
