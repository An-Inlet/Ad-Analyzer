"""Closed original Google receipt producer; current parent only reconciles evidence."""

import json
import os
import re
import select as readiness
import signal
import stat
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import app
import pytest
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, make_url, text
from sqlalchemy.orm import Session
from tests.test_optimization_candidates import fixture
from tests.test_shopify_sales import configuration


def main() -> None:
    target, output = sys.argv[1:]
    first_path = Path(output)
    assert first_path.is_absolute() and ".." not in first_path.parts
    assert not first_path.is_symlink()
    assert all(not parent.is_symlink() for parent in first_path.parents)
    assert first_path.name == "first.json"
    assert first_path.parent.is_dir() and first_path.parent.resolve() == first_path.parent
    for name in ("first.json", "first.tmp", "second.json", "second.tmp"):
        assert not (first_path.parent / name).exists()
        assert not (first_path.parent / name).is_symlink()
    started = time.monotonic()
    signal.alarm(180)
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    if target.startswith("sqlite:"):
        url = make_url(target)
        assert url.drivername == "sqlite" and not url.query and url.database
        assert (
            url.host is None and url.username is None and url.password is None and url.port is None
        )
        database = Path(url.database)
        expected = Path(output).parent / "current.sqlite"
        assert database.is_absolute() and ".." not in database.parts
        assert database == expected and database.resolve() == database
        assert all(not parent.is_symlink() for parent in database.parents)
        assert stat.S_ISREG(database.lstat().st_mode)
        assert database.is_file() and not database.is_symlink()
        assert expected.is_file() and not expected.is_symlink()
        engine = create_engine(url)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        url = make_url(validate_disposable_url())
        assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == target
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            for table in tables - {"alembic_version"}:
                quoted = connection.dialect.identifier_preparer.quote(table)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        config = cast(Any, configuration).__wrapped__()
        from app.publication import optimization, replacement
        from app.publication.execution_models import ProviderExposureReservation
        from app.publication.optimization_contracts import GoogleBudgetSetV1
        from sqlalchemy import select
        from tests import test_optimization_candidates as candidate_fixtures
        from tests.test_commerce_measurement import NOW
        from tests.test_repeat_optimization import reader

        captured = []
        original = cast(Any, candidate_fixtures).ready
        patch = pytest.MonkeyPatch()

        def capture(*args: Any, **kwargs: Any) -> Any:
            value = original(*args, **kwargs)
            captured.append(value[6])
            return value

        patch.setattr(candidate_fixtures, "ready", capture)
        with Session(engine) as db:
            principal, work, _, _, _, server = fixture(db, config, Path(output).parent, True)
            assert len(server.writes) == 1
            scope = work.scope
            result: dict[str, Any] = dict(
                workspace_id=scope.account.workspace_id,
                actor_id=principal.user.id,
                session_digest=principal.session.digest,
                mandate_id=scope.mandate.mandate_id,
                mandate_revision=scope.mandate.revision,
                consent_id=scope.mandate.consent_id,
                policy_digest=scope.mandate.policy_digest,
                ledger_id=scope.mandate.ledger_id,
                account_id=scope.account.account.account_id,
                store_id=scope.source.store_id,
                publication_id=scope.source.publication_id,
                provider="google_ads",
                provider_posts=len(server.writes),
                attempt_id=scope.source.attempt_id,
                receipt_id=scope.source.receipt_id,
            )
            db.commit()
        patch.undo()
        first = Path(output)
        assert first.name == "first.json" and not first.exists()
        pending = first.with_suffix(".tmp")
        pending.write_text(json.dumps(result))
        pending.replace(first)
        # No Session/transaction remains open while the parent performs its current read.
        assert readiness.select([sys.stdin], [], [], max(0, 180 - (time.monotonic() - started)))[0]
        assert sys.stdin.read(17) == "claim\n"
        assert time.monotonic() - started < 180
        execution = replace(captured[0], replacement_reader=reader(captured[0]))
        with Session(engine) as db:
            held = db.scalar(
                select(ProviderExposureReservation).where(
                    ProviderExposureReservation.state == "held"
                )
            )
            assert held
            wid, actor = result["workspace_id"], result["actor_id"]
            reviewed = replacement.prepare_repeat_optimization(
                db,
                wid,
                work.scope.mandate,
                work.scope.account,
                held.id,
                work.scope.target,
                GoogleBudgetSetV1(amount_micros=46_000_000),
                "a" * 64,
                actor,
                execution,
                lambda: NOW,
            )
            optimization.approve_optimization(
                db,
                wid,
                reviewed.id,
                reviewed.digest,
                reviewed.plan_digest,
                actor,
                execution,
                lambda: NOW,
            )
            run = optimization.create_run(db, wid, reviewed.id, actor, execution, lambda: NOW)
            claim = optimization.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
            assert claim and claim.attempt_id != result["attempt_id"]
            assert len(server.writes) == 1
            from app.publication.execution_models import ProviderReservationReplacement

            audit = db.scalar(
                select(ProviderReservationReplacement).where(
                    ProviderReservationReplacement.successor_run_id == run.id
                )
            )
            assert audit
            result = dict(
                workspace_id=wid,
                first_attempt_id=result["attempt_id"],
                attempt_id=claim.attempt_id,
                run_id=run.id,
                review_id=run.review_id,
                predecessor_id=audit.predecessor_id,
                successor_id=audit.successor_id,
                replacement_id=audit.id,
            )
            db.commit()
        assert set(inspect(engine).get_table_names()) == tables
        second = Path(output).with_name("second.json")
        assert not second.exists()
        pending = second.with_suffix(".tmp")
        pending.write_text(json.dumps(result))
        pending.replace(second)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
