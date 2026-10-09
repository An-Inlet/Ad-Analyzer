"""Closed historical producers; current caller owns physical migration assertions."""

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import Engine, inspect, text

from tests.retired_budget_snapshot import BUDGET_PIN, extract_budget
from tests.retired_snapshot import PIN, extract, run_bounded

Mode = Literal["budget_preparation_0079", "candidate_result_0062", "replacement_0058"]
PROFILES = {
    "budget_preparation_0079": ("inlet_migration_fixture_", "20261007_0079",
                                ("initial_budget_mandate_preparations",)),
    "candidate_result_0062": ("inlet_candidates_", "20261006_0062",
                              ("optimization_candidate_jobs", "optimization_candidate_results")),
    "replacement_0058": ("inlet_replace_", "20261006_0058",
                          ("provider_reservation_replacements",)),
}


@dataclass(frozen=True)
class RetainedBudgetPreparationIds:
    workspace_id: int
    mandate_id: str
    mandate_revision: int
    preparation_digest: str
    policy_digest: str
    response_status: int
    provider_posts: int


def _seed(engine: Engine, artifacts: Path, mode: Mode) -> dict[str, Any]:
    assert engine.dialect.name == "postgresql"
    assert os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
    prefix, revision, required = PROFILES[mode]
    with engine.connect() as db:
        target = str(db.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(prefix + r"[a-f0-9]{32}", target)
        assert set(db.scalars(text("SELECT version_num FROM alembic_version"))) == {revision}
        for table in required:
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    tables = set(inspect(engine).get_table_names())
    assert set(required) <= tables
    assert not {"meta_presence_stage_contexts", "planning_input_revisions",
                "optimization_mandate_preparations"} & tables
    columns = {c["name"] for c in inspect(engine).get_columns("provider_execution_revisions")}
    assert not {"origin_kind", "origin_preparation_digest"} & columns
    artifacts.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    snapshot = artifacts / "historical-source"
    if mode == "budget_preparation_0079":
        extract_budget(root, snapshot)
        source_pin = BUDGET_PIN
    else:
        extract(root, snapshot)
        source_pin = PIN
    output, log = artifacts / "producer-ids.json", artifacts / "producer.log"
    assert not output.exists()
    code = run_bounded(
        [sys.executable, str(root / "tests/fixtures/retired_execution/migration_seed_driver.py"),
         target, str(output), mode], snapshot,
        dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=source_pin, PYTHONPATH=str(snapshot)),
        log, 180,
    )
    assert code == 0, log.read_text()[-6000:]
    assert set(inspect(engine).get_table_names()) == tables
    with engine.connect() as db:
        assert set(db.scalars(text("SELECT version_num FROM alembic_version"))) == {revision}
    raw = json.loads(output.read_text())
    assert type(raw) is dict
    return raw


def retained_budget_preparation_fixture(
    engine: Engine, artifacts: Path,
) -> RetainedBudgetPreparationIds:
    raw = _seed(engine, artifacts, "budget_preparation_0079")
    assert set(raw) == set(RetainedBudgetPreparationIds.__dataclass_fields__)
    for name in ("workspace_id", "mandate_revision", "response_status", "provider_posts"):
        assert type(raw[name]) is int
    assert raw["workspace_id"] > 0 and raw["mandate_revision"] > 0
    assert raw["response_status"] == 201 and raw["provider_posts"] == 0
    assert type(raw["mandate_id"]) is str and re.fullmatch(r"[a-f0-9]{32}", raw["mandate_id"])
    for name in ("preparation_digest", "policy_digest"):
        assert type(raw[name]) is str and re.fullmatch(r"[a-f0-9]{64}", raw[name])
    result = RetainedBudgetPreparationIds(**raw)
    with engine.connect() as db:
        row = db.execute(text(
            "SELECT workspace_id,mandate_id,mandate_revision,digest,policy_digest "
            "FROM initial_budget_mandate_preparations"
        )).one()
        assert tuple(row) == (result.workspace_id, result.mandate_id, result.mandate_revision,
                              result.preparation_digest, result.policy_digest)
    return result


@dataclass(frozen=True)
class RetainedCandidateResultIds:
    workspace_id: int
    job_id: str
    result_id: str
    mandate_ids: tuple[str, ...]
    job_count: int
    result_count: int
    provider_posts: int


def retained_candidate_result_fixture(
    engine: Engine, artifacts: Path,
) -> RetainedCandidateResultIds:
    raw = _seed(engine, artifacts, "candidate_result_0062")
    assert set(raw) == set(RetainedCandidateResultIds.__dataclass_fields__)
    assert type(raw["workspace_id"]) is int and raw["workspace_id"] > 0
    for name in ("job_count", "result_count", "provider_posts"):
        assert type(raw[name]) is int and raw[name] == (0 if name == "provider_posts" else 1)
    for name in ("job_id", "result_id"):
        assert type(raw[name]) is str and re.fullmatch(r"[a-f0-9]{32}", raw[name])
    ids = raw["mandate_ids"]
    assert type(ids) is list and 0 < len(ids) <= 64
    assert all(type(x) is str and re.fullmatch(r"[a-f0-9]{32}", x) for x in ids)
    assert ids == sorted(set(ids))
    result = RetainedCandidateResultIds(**{**raw, "mandate_ids": tuple(ids)})
    with engine.connect() as db:
        assert db.execute(text(
            "SELECT workspace_id,job_id,id FROM optimization_candidate_results"
        )).one() == (result.workspace_id, result.job_id, result.result_id)
        assert db.execute(text(
            "SELECT workspace_id,id FROM optimization_candidate_jobs"
        )).one() == (
            result.workspace_id, result.job_id
        )
        assert tuple(sorted(db.scalars(text("SELECT id FROM provider_execution_mandates")))) == (
            result.mandate_ids
        )
    return result


@dataclass(frozen=True)
class RetainedReplacementIds:
    workspace_id: int
    run_id: str
    predecessor_id: str
    successor_id: str
    replacement_ids: tuple[str, ...]
    provider_posts: int


def retained_replacement_fixture(engine: Engine, artifacts: Path) -> RetainedReplacementIds:
    raw = _seed(engine, artifacts, "replacement_0058")
    assert set(raw) == set(RetainedReplacementIds.__dataclass_fields__)
    assert type(raw["workspace_id"]) is int and raw["workspace_id"] > 0
    assert type(raw["provider_posts"]) is int and raw["provider_posts"] == 1
    for name in ("run_id", "predecessor_id", "successor_id"):
        assert type(raw[name]) is str and re.fullmatch(r"[a-f0-9]{32}", raw[name])
    ids = raw["replacement_ids"]
    assert type(ids) is list and 0 < len(ids) <= 64
    assert all(type(x) is str and re.fullmatch(r"[a-f0-9]{32}", x) for x in ids)
    assert ids == sorted(set(ids))
    result = RetainedReplacementIds(**{**raw, "replacement_ids": tuple(ids)})
    with engine.connect() as db:
        row = db.execute(text(
            "SELECT workspace_id,successor_run_id,predecessor_id,successor_id "
            "FROM provider_reservation_replacements"
        )).one()
        assert tuple(row) == (result.workspace_id, result.run_id, result.predecessor_id,
                              result.successor_id)
        assert tuple(sorted(db.scalars(text(
            "SELECT id FROM provider_reservation_replacements"
        )))) == (
            result.replacement_ids
        )
    return result
