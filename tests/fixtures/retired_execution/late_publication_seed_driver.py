"""Fixed original two claims and one unrecorded local fixture receipt."""

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, cast

import app
from app.publication import service as publication
from app.publication.contracts import PublishReceipt, fingerprint
from app.publication.fixture import FixturePublicationTransport
from app.publication.models import (
    PublicationPlanRecord,
    PublicationReceiptRecord,
    PublicationStepRecord,
)
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_commerce_measurement import NOW
from tests.test_publication_core import approved
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
    target, output = sys.argv[1:]
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
        with Session(engine) as db:
            pid, wid, actor, authority = approved(
                db, cast(Any, configuration).__wrapped__(), path / "media"
            )
            first = publication.claim_next(db, wid, pid, "publication-one", actor, authority, NOW)
            assert first is not None
            publication.record_receipt(
                db,
                wid,
                pid,
                PublishReceipt(
                    scope=first.scope,
                    plan_id=pid,
                    step_id=first.step.step_id,
                    fence=first.fence,
                    request_digest=first.digest(),
                    outcome="verified_no_effect",
                    observed_at=NOW,
                ),
                NOW,
            )
            second = publication.claim_next(db, wid, pid, "publication-one", actor, authority, NOW)
            assert second is not None
            assert first.fence != second.fence and first.digest() != second.digest()
            transport = FixturePublicationTransport()
            receipt = transport.apply_once(second, NOW)
            assert transport.calls == 1 and receipt.outcome == "verified_effect"
            plan = db.get(PublicationPlanRecord, pid)
            step = db.get(PublicationStepRecord, (pid, second.step.step_id))
            old = db.scalars(select(PublicationReceiptRecord)).one()
            assert plan and step and step.attempt == 2 and step.state == "dispatching"
            assert (
                old.receipt["outcome"] == "verified_no_effect"
                and old.receipt["fence"] == first.fence
            )
            data = dict(
                workspace_id=wid,
                actor_id=actor,
                plan_id=pid,
                mandate_id=second.scope.mandate_id,
                mandate_revision=second.scope.mandate_revision,
                action_id=plan.action_id,
                first_receipt_id=old.id,
                fence=second.fence,
                step_id=second.step.step_id,
                plan_digest=plan.digest,
                request_digest=second.digest(),
                late_receipt_digest=fingerprint(
                    "inlet.publication-receipt.v1", receipt.model_dump(mode="json")
                ),
                fixture_calls=transport.calls,
                late_receipt=receipt.model_dump(mode="json"),
            )
            db.commit()
        raw = json.dumps(data)
        assert len(raw.encode()) <= 16384
        Path(output).write_text(raw)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
