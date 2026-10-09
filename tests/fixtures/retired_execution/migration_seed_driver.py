"""One closed producer in pinned imports; no schema DDL or external provider IO."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from tests.optimization_origin_historical_schema import install_legacy_origin
from tests.test_shopify_sales import configuration


def budget(engine: Any, patch: pytest.MonkeyPatch, output_path: str) -> dict[str, Any]:
    from app.initial_planning.budget_mandate_models import BudgetMandatePreparationRow
    from tests.budget_mandate_fixture import first_customer
    from tests.test_customer_identity import replicas
    from tests.test_customer_optimization_api import headers

    config = cast(Any, configuration).__wrapped__()
    clients = cast(Any, replicas).__wrapped__(engine, patch)
    alice, root, body, _, requests, _, _, server = first_customer(
        engine, config, Path(output_path).parent, patch, clients
    )
    response = alice.post(root + "/budget-mandates", headers=headers(alice), json=body)
    assert response.status_code == 201, response.text
    assert requests and all(request.method == "GET" for request in requests)
    assert not server.posts
    with Session(engine) as db:
        row = db.scalars(select(BudgetMandatePreparationRow)).one()
        output = dict(workspace_id=row.workspace_id, mandate_id=row.mandate_id,
                      mandate_revision=row.mandate_revision,
                      preparation_digest=row.digest, policy_digest=row.policy_digest,
                      response_status=response.status_code,
                      provider_posts=len(server.posts))
        db.commit()
    return output


def candidate(engine: Any, patch: pytest.MonkeyPatch, output_path: str) -> dict[str, Any]:
    from app.optimization_candidates.models import CandidateResult
    from app.optimization_candidates.service import enqueue, process
    from app.publication.execution_models import ProviderExecutionMandate
    from tests.candidate_historical_schema import (
        without_candidate_reviews,
        without_initial_planning,
    )
    from tests.feedback_historical_schema import without_feedback
    from tests.test_optimization_candidates import fixture

    without_feedback(patch, engine)
    without_candidate_reviews(patch, engine)
    without_initial_planning(patch, engine)
    config = cast(Any, configuration).__wrapped__()
    with Session(engine) as db:
        principal, work, _, _, runtime, server = fixture(db, config, Path(output_path).parent)
        row = enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
        db.commit()
    assert process(engine, wid, identifier, runtime) == "completed"
    assert not server.writes
    with Session(engine) as db:
        result = db.scalars(select(CandidateResult)).one()
        assert result.job_id == identifier and result.workspace_id == wid
        return dict(workspace_id=wid, job_id=identifier, result_id=result.id,
                    mandate_ids=sorted(db.scalars(select(ProviderExecutionMandate.id))),
                    job_count=db.scalar(text("SELECT count(*) FROM optimization_candidate_jobs")),
                    result_count=db.scalar(text(
                        "SELECT count(*) FROM optimization_candidate_results")),
                    provider_posts=len(server.writes))


def replacement(engine: Any, patch: pytest.MonkeyPatch, output_path: str) -> dict[str, Any]:
    from app.publication import replacement as service
    from app.publication.execution_models import ProviderReservationReplacement
    from app.publication.replacement_contracts import RepeatOptimizationReview
    from tests.candidate_historical_schema import without_candidates
    from tests.test_commerce_measurement import NOW
    from tests.test_repeat_optimization import prepared
    from tests.test_replacement_migration import ReplacementHistoricalSession

    without_candidates(patch, engine)
    config = cast(Any, configuration).__wrapped__()
    with ReplacementHistoricalSession(engine) as db:
        wid, actor, old, run, row, runtime, server = prepared(
            db, config, Path(output_path).parent
        )
        service.transfer(db, wid, run, RepeatOptimizationReview.model_validate(row.document),
                         actor, runtime, lambda: NOW)
        rows = list(db.scalars(select(ProviderReservationReplacement)))
        assert len(rows) == 1 and len(server.writes) == 1
        retained = rows[0]
        assert retained.workspace_id == wid and retained.successor_run_id == run.id
        assert retained.predecessor_id == old.reservation_id
        assert retained.successor_id == run.reservation_id
        output = dict(workspace_id=wid, run_id=run.id, predecessor_id=retained.predecessor_id,
                      successor_id=retained.successor_id,
                      replacement_ids=sorted(x.id for x in rows),
                      provider_posts=len(server.writes))
        db.commit()
    return output


def main() -> None:
    target, output_path, mode = sys.argv[1:]
    profiles = {
        "budget_preparation_0079": ("inlet_migration_fixture_", "20261007_0079",
                                    "initial_budget_mandate_preparations"),
        "candidate_result_0062": ("inlet_candidates_", "20261006_0062",
                                  "optimization_candidate_results"),
        "replacement_0058": ("inlet_replace_", "20261006_0058",
                              "provider_reservation_replacements"),
    }
    assert mode in profiles
    prefix, revision, table = profiles[mode]
    assert re.fullmatch(prefix + r"[a-f0-9]{32}", target)
    source_pin = ("745acee533638f6f937339110944454cd8ce2a83"
                  if mode == "budget_preparation_0079"
                  else "2155ff3e3ab00cd62057dd86cb49d45359d4f49f")
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == source_pin
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    assert os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
    engine = create_engine(os.environ["AD_ANALYZER_TEST_POSTGRES_URL"],
                           connect_args={"options": f"-csearch_path={target}"})
    try:
        with engine.connect() as db:
            assert db.scalar(text("SELECT current_schema()")) == target
            assert set(db.scalars(text("SELECT version_num FROM alembic_version"))) == {
                revision
            }
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        tables = set(inspect(engine).get_table_names())
        assert not {"optimization_mandate_preparations", "meta_presence_stage_contexts"} & tables
        with pytest.MonkeyPatch.context() as patch:
            cleanup = install_legacy_origin(patch, engine)
            try:
                if mode == "budget_preparation_0079":
                    output = budget(engine, patch, output_path)
                elif mode == "candidate_result_0062":
                    output = candidate(engine, patch, output_path)
                else:
                    output = replacement(engine, patch, output_path)
            finally:
                cleanup()
        assert set(inspect(engine).get_table_names()) == tables
        Path(output_path).write_text(json.dumps(output))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
