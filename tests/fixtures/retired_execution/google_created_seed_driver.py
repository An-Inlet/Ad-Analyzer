"""Actual original configured creation, with one completed or timed-out attempt."""

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
from app.publication import coordinator, customer_intents
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_customer_identity import replicas
from tests.test_google_execution_completion import first_attempt
from tests.test_google_total_envelope_api import created
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
    target, output, mode = sys.argv[1:]
    assert mode in {"daily_completed", "daily_unknown", "total_created"}
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
    clients = None
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                assert connection.scalar(text("SELECT current_schema()")) == target
            for name in set(inspect(engine).get_table_names()) - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        (path / "media").mkdir()
        with pytest.MonkeyPatch.context() as patch:
            clients = cast(Any, replicas).__wrapped__(engine, patch)
            if mode == "total_created":
                alice, _, _, server = created(
                    engine, cast(Any, configuration).__wrapped__(), path / "media", patch, clients
                )
                with Session(engine) as db:
                    budget = db.scalars(
                        select(ProviderExecutionAttempt).where(
                            ProviderExecutionAttempt.step_id == "budget"
                        )
                    ).one()
                    attempt_id, wid = budget.id, budget.workspace_id
            else:
                alice, _, attempt_id, wid, _, server, _ = first_attempt(
                    engine,
                    cast(Any, configuration).__wrapped__(),
                    path / "media",
                    patch,
                    clients,
                    timeout=mode == "daily_unknown",
                )
            count = 2 if mode == "total_created" else 1
            assert server.posts == count
            with Session(engine) as db:
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert session
                run, document, attempt, request = coordinator.evidence_lock(db, wid, attempt_id)
                review = db.get(ProviderExecutionReview, run.review_id)
                assert review
                binding = customer_intents.binding(
                    db, wid, document.mandate.mandate_id, document.mandate.revision
                )
                hold = db.scalars(select(ProviderExposureReservation)).one()
                assert hold.id == run.reservation_id and hold.state == "held"
                attempts = list(
                    db.scalars(
                        select(ProviderExecutionAttempt).order_by(ProviderExecutionAttempt.step_id)
                    )
                )
                assert [row.step_id for row in attempts] == (
                    ["budget", "campaign"] if mode == "total_created" else ["budget"]
                )
                pins = []
                for row in attempts:
                    response = db.scalars(
                        select(ProviderExecutionResponse).where(
                            ProviderExecutionResponse.attempt_id == row.id
                        )
                    ).one()
                    receipt = db.scalars(
                        select(ProviderExecutionReceipt).where(
                            ProviderExecutionReceipt.attempt_id == row.id
                        )
                    ).one()
                    completion = db.get(GoogleOriginalCompletion, row.id)
                    assert (completion is None) == (mode == "daily_unknown")
                    resource = receipt.receipt.get("resource_name")
                    if mode == "total_created":
                        assert resource in server.rows
                    pins.append(
                        dict(
                            step_id=row.step_id,
                            attempt_id=row.id,
                            fence=row.fence,
                            request_digest=row.request_digest,
                            response_digest=response.digest,
                            latest_receipt_id=receipt.id,
                            latest_receipt_digest=receipt.digest,
                            latest_receipt_sequence=receipt.sequence,
                            completion_digest=None if completion is None else completion.digest,
                            resource_name=resource,
                        )
                    )
                data = dict(
                    mode=mode,
                    workspace_id=wid,
                    actor_id=session.user_id,
                    account_id=request.scope.account.account_id,
                    run_id=run.id,
                    review_id=run.review_id,
                    mandate_id=binding.mandate_id,
                    mandate_revision=binding.revision,
                    consent_id=binding.consent_id,
                    ledger_id=binding.ledger_id,
                    reservation_id=hold.id,
                    native_connection_id=request.scope.connection_version.split(":")[1],
                    policy_digest=binding.policy_digest,
                    review_digest=review.digest,
                    plan_digest=review.plan_digest,
                    reservation_amount_micros=hold.amount_micros,
                    provider_posts=server.posts,
                    attempts=pins,
                )
                db.commit()
        raw = json.dumps(data)
        assert len(raw.encode()) <= 8192
        Path(output).write_text(raw)
    finally:
        if clients:
            clients[0].close()
            clients[1].close()
        engine.dispose()


if __name__ == "__main__":
    main()
