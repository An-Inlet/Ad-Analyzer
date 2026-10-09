"""A registered feedback dependency cannot be omitted at the final derived-write fence."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from app.optimization_candidates import service as s
from app.optimization_candidates.models import CandidateResult
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.candidate_current_fixture import current_candidate_read as current_candidate_read
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("mode", ["missing", "retracted", "current"])
@pytest.mark.planning_boundary
def test_required_feedback_reader_is_checked_before_result_insert(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    mode: str,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_candidate_read
    calls = []

    def check(db, work, observation):  # type: ignore[no-untyped-def]
        assert db.in_transaction()
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0
        calls.append(observation.evidence.source_digest)
        if mode == "retracted":
            raise HTTPException(409, "feedback dependency retracted")

    with Session(customer_engine) as db:
        principal, work, observation, _, runtime, _ = load_candidate_read_fixture(db, ids)
        runtime = replace(
            runtime,
            feedback_dependent_schemas=frozenset({observation.evidence.source_schema}),
            final_evidence_current=None if mode == "missing" else check,
        )
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
    assert s.process(customer_engine, wid, identifier, runtime) == (
        "completed" if mode == "current" else "blocked"
    )
    assert len(calls) == (0 if mode == "missing" else 1)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == (
            1 if mode == "current" else 0
        )
