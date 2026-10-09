"""Run only in the pinned interpreter against one explicitly owned fixture schema."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from app.initial_planning.review_bridge import prepare_preview_review
from app.publication import customer_optimization, optimization
from app.publication.execution_models import ProviderExposureReservation
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from tests.test_customer_identity import replicas
from tests.test_initial_preview_review import ready
from tests.test_shopify_sales import configuration


def main() -> None:
    target, result_path, mode, *extra = sys.argv[1:]
    assert mode in {"review", "initial_rule", "native_diagnostic"}
    if mode == "native_diagnostic":
        assert len(extra) == 1 and extra[0] in {"google_ads", "meta_ads", "tiktok_ads"}
    else:
        assert not extra
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    if os.environ.get("INLET_RETIRED_EXECUTION_CHILD") != (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    ):
        raise AssertionError("Pinned subprocess only")
    if target.startswith("sqlite:"):
        engine = create_engine(target, connect_args={"check_same_thread": False})
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        if not re.fullmatch(r"(?:inlet_test_|inlet_migration_fixture_)[a-f0-9]{32}", target):
            raise AssertionError("Only one owned fixture schema")
        if os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true":
            raise AssertionError("Disposable database authorization required")
        engine = create_engine(
            os.environ["AD_ANALYZER_TEST_POSTGRES_URL"],
            connect_args={"options": f"-csearch_path={target}"},
        )
        with engine.connect() as connection:
            assert connection.scalar(text("select current_schema()")) == target
    try:
        with pytest.MonkeyPatch.context() as patch:
            config = cast(Any, configuration).__wrapped__()
            if mode == "native_diagnostic":
                from app.publication.execution_models import (
                    ProviderExecutionAttempt,
                    ProviderExecutionReceipt,
                    ProviderExecutionResponse,
                )
                from sqlalchemy import func, select
                from tests.test_durable_optimization import ready as ready_native

                with Session(engine) as db:
                    wid, actor, binding, scope, _, _, _, server = ready_native(
                        db, config, Path(result_path).parent, extra[0]
                    )
                    db.commit()
                    writes = server.writes if extra[0] == "google_ads" else server.posts
                    assert not writes
                    for model in (
                        ProviderExecutionAttempt, ProviderExecutionResponse,
                        ProviderExecutionReceipt, ProviderExposureReservation,
                    ):
                        assert db.scalar(select(func.count()).select_from(model)) == 0
                    output = dict(
                        workspace_id=wid, actor_id=actor, account_id=scope.account.account_id,
                        mandate_id=binding.mandate_id, revision=binding.revision,
                        consent_id=binding.consent_id, policy_digest=binding.policy_digest,
                        ledger_id=binding.ledger_id, environment=binding.environment,
                        provider_posts=0,
                    )
                    Path(result_path).write_text(json.dumps(output))
                return
            clients = cast(Any, replicas).__wrapped__(engine, patch)
            if mode == "initial_rule":
                from app.initial_planning.start_models import InitialRuleSessionStart
                from app.session_automation import service
                from tests.test_initial_rule_acceptance import initial_start_case

                with initial_start_case(
                    engine, config, Path(result_path).parent, patch, clients
                ) as (case, runtime, intent, wid):
                    started = service.start(case.db, case.principal, wid, intent, runtime)
                    case.db.commit()
                    row = case.db.get(InitialRuleSessionStart, started.id)
                    assert row and row.candidate_job_id
                    assert not case.server.posts
                    output = dict(
                        workspace_id=wid,
                        preview_id=intent.preview_id,
                        mandate_id=intent.mandate.mandate_id,
                        session_run_id=started.id,
                        candidate_job_id=row.candidate_job_id,
                        provider_posts=0,
                    )
                    Path(result_path).write_text(json.dumps(output))
                return
            wid, preview, principal, provider, runtime, server, _ = ready(
                engine, config, patch, clients
            )
            result = prepare_preview_review(
                runtime, principal, provider, wid, preview.id, preview.digest()
            )
            bound = customer_optimization.bind(runtime.optimization, principal, provider)
            clock = runtime.planning.clock
            with Session(engine) as db:
                optimization.approve_optimization(
                    db,
                    wid,
                    result.review_id,
                    result.review_digest,
                    result.plan_digest,
                    principal.user.id,
                    bound.execution,
                    clock,
                )
                run = optimization.create_run(
                    db, wid, result.review_id, principal.user.id, bound.execution, clock
                )
                claim = optimization.claim_step(
                    db, wid, run.id, principal.user.id, bound.execution, clock
                )
                assert claim
                receipt = optimization.execute_claim(
                    db, claim, principal.user.id, bound.execution, clock
                )
                assert receipt.outcome == "verified_target_state" and len(server.posts) == 1
                reservation = db.get(ProviderExposureReservation, run.reservation_id)
                assert reservation is not None and reservation.state == "held"
                output = dict(
                    workspace_id=wid,
                    preview_id=preview.id,
                    review_id=result.review_id,
                    actor_id=principal.user.id,
                    run_id=run.id,
                    attempt_id=claim.attempt_id,
                    reservation_id=reservation.id,
                    provider_posts=len(server.posts),
                )
            Path(result_path).write_text(json.dumps(output))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
