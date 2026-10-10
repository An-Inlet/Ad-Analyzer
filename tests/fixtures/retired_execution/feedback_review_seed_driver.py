"""Two fixed original candidate-review checkpoints, before current erasure."""

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from app.optimization_candidates import review_bridge as bridge
from app.optimization_candidates.models import CandidateResult
from app.optimization_candidates.review_models import CandidateReviewLink
from app.publication import optimization
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExposureReservation,
)
from app.publication.optimization_contracts import GoogleBudgetSetV1, GoogleCurrentState
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_candidate_review_bridge import assembled
from tests.test_commerce_measurement import NOW
from tests.test_google_optimization_http import Server
from tests.test_shopify_sales import configuration


def owned_sqlite_target(target: str, expected: Path) -> str:
    """Reject aliases and non-owned URL shapes before any database access."""
    url = make_url(target)
    assert url.drivername == "sqlite" and not url.query
    assert url.username is None and url.password is None and url.host is None and url.port is None
    assert url.database is not None and url.database != ":memory:"
    path = Path(url.database)
    assert path.is_absolute() and expected.is_absolute() and path == expected
    assert not path.is_symlink() and all(not parent.is_symlink() for parent in path.parents)
    assert path.resolve() == path and stat.S_ISREG(path.lstat().st_mode)
    return str(url)


def main() -> None:
    target, output, stage = sys.argv[1:]
    assert stage in {"claimed_final_context", "completed"}
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    path = Path(output).parent
    if target.startswith("sqlite:"):
        target = owned_sqlite_target(target, path / "current.sqlite")
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        url = make_url(validate_disposable_url())
        assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                assert connection.scalar(text("SELECT current_schema()")) == target
            for name in set(inspect(engine).get_table_names()) - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        with pytest.MonkeyPatch.context() as patch, Session(engine) as db:
            principal, wid, intent, runtime, server = assembled(
                db, cast(Any, configuration).__wrapped__(), path / "media", "google_ads", patch
            )
            actor, session_digest = principal.user.id, principal.session.digest
            review = bridge.prepare_candidate_review(db, principal, wid, intent, runtime)
            execution = bridge.bind_execution(runtime, principal)
            optimization.approve_optimization(
                db,
                wid,
                review.review_id,
                review.review_digest,
                review.plan_digest,
                actor,
                execution,
                lambda: NOW,
            )
            run = optimization.create_run(db, wid, review.review_id, actor, execution, lambda: NOW)
            claim = optimization.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
            assert claim
            link = db.get(CandidateReviewLink, review.review_id)
            assert link and link.candidate_result_id
            result = db.get(CandidateResult, link.candidate_result_id)
            assert result
            job_id, result_id = result.job_id, result.id
            if stage == "completed":
                receipt = optimization.execute_claim(db, claim, actor, execution, lambda: NOW)
                assert receipt.outcome == "verified_target_state"
                assert db.get(GoogleOriginalCompletion, claim.attempt_id) is not None
            assert isinstance(server, Server)
            baseline = Server()
            amount = int(server.budget["amountMicros"])
            assert server.account == baseline.account and server.campaign == baseline.campaign
            assert server.subscriptions == baseline.subscriptions
            budget = dict(server.budget)
            budget["amountMicros"] = baseline.budget["amountMicros"]
            assert budget == baseline.budget
            for key in (
                "pages",
                "cycle",
                "hidden_owner",
                "duplicate_owner",
                "timeout",
                "ignore",
                "partial_failure",
                "bad_ack",
                "error",
            ):
                assert getattr(server, key) == getattr(baseline, key)
            assert isinstance(claim.request.intent.action, GoogleBudgetSetV1)
            assert isinstance(claim.request.before, GoogleCurrentState)
            assert claim.request.before.native_budget_resource == server.budget["resourceName"]
            assert amount == (
                claim.request.intent.action.amount_micros
                if stage == "completed"
                else claim.request.before.budget_amount_micros
            )
            assert len(server.writes) == (1 if stage == "completed" else 0)
            attempt = db.scalars(select(ProviderExecutionAttempt)).one()
            response = db.scalars(select(ProviderExecutionResponse)).one_or_none()
            stored_receipt = db.scalars(select(ProviderExecutionReceipt)).one_or_none()
            completion = db.scalars(select(GoogleOriginalCompletion)).one_or_none()
            hold = db.scalars(select(ProviderExposureReservation)).one()
            assert hold.id == run.reservation_id and hold.state == "held"
            assert attempt.id == claim.attempt_id
            assert (
                (response is not None)
                == (stored_receipt is not None)
                == (completion is not None)
                == (stage == "completed")
            )
            data = dict(
                stage=stage,
                workspace_id=wid,
                actor_id=actor,
                session_digest=session_digest,
                job_id=job_id,
                result_id=result_id,
                review_id=review.review_id,
                run_id=run.id,
                attempt_id=attempt.id,
                fence=attempt.fence,
                reservation_id=hold.id,
                review_digest=review.review_digest,
                plan_digest=review.plan_digest,
                request_digest=attempt.request_digest,
                reservation_amount_micros=hold.amount_micros,
                native_budget_amount_micros=amount,
                provider_posts=len(server.writes),
                response_digest=response.digest if response else None,
                receipt_id=stored_receipt.id if stored_receipt else None,
                receipt_digest=stored_receipt.digest if stored_receipt else None,
                receipt_sequence=stored_receipt.sequence if stored_receipt else None,
                completion_digest=completion.digest if completion else None,
            )
            db.commit()
        Path(output).write_text(json.dumps(data))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
