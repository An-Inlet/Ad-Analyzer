"""Two closed original Meta history phases; scalar output, no runtime export."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
from app.publication import activation, coordinator
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_commerce_measurement import NOW
from tests.test_shopify_sales import configuration
from tests.test_social_activation_journeys import Server, approved
from tests.test_social_coordinator_journeys import SocialServer, ready


def owned_sqlite_target(target: str, expected: Path) -> str:
    url = make_url(target)
    assert url.drivername == "sqlite" and not url.query
    assert url.username is None and url.password is None and url.host is None and url.port is None
    assert url.database is not None
    path = Path(url.database)
    assert path.is_absolute() and path == expected and path.resolve() == path
    assert path.is_file() and not path.is_symlink()
    assert all(not parent.is_symlink() for parent in path.parents)
    return str(url)


def creation(db: Session, config: Any, path: Path) -> tuple[int, str, str, Any]:
    server = SocialServer("meta_ads")
    wid, run_id, actor, media, runtime, native = ready(db, config, path, "meta_ads", None, server)
    count = 0
    while claim := coordinator.claim_creation_step(
        db, wid, run_id, actor, media, runtime, lambda: NOW
    ):
        receipt = coordinator.execute_claim(db, claim, actor, media, runtime, lambda: NOW)
        assert receipt.outcome == "verified_effect"
        count += 1
    assert count == 5
    assert server.posts == 5
    return wid, run_id, actor, native


def activated(db: Session, config: Any, path: Path) -> tuple[int, str, str, Any]:
    server = Server("meta_ads")
    wid, run, actor, store, runtime, native = approved(db, config, path, "meta_ads", None, server)
    steps = 0
    while claim := activation.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW):
        receipt = activation.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        assert receipt.outcome == "verified_target_state"
        steps += 1
    assert steps == 3
    assert server.posts == 5 and server.activations == 3
    return wid, run.id, actor, native


def main() -> None:
    target, output, mode = sys.argv[1:]
    assert mode in {"creation", "activation"}
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    artifacts = Path(output).parent
    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink() and all(not p.is_symlink() for p in artifacts.parents)
    assert Path(output).name == "ids.json" and not Path(output).exists()
    if target.startswith("sqlite"):
        target = owned_sqlite_target(target, artifacts / "current.sqlite")
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
            config = cast(Any, configuration).__wrapped__()
            wid, run_id, actor, native = (creation if mode == "creation" else activated)(
                db, config, artifacts / "media"
            )
            run = db.get(ProviderExecutionRun, run_id)
            assert run and run.reservation_id
            row = db.get(ProviderExecutionReview, run.review_id)
            parent = db.get(ProviderExecutionRun, run.parent_run_id) if run.parent_run_id else None
            base = db.get(ProviderExecutionReview, parent.review_id) if parent else row
            assert row and base
            document = CreationExecutionReview.model_validate(base.document)
            data = dict(
                mode=mode,
                provider="meta_ads",
                workspace_id=wid,
                account_id=document.plan.review.scope.account.account_id,
                actor_id=actor,
                run_id=run.id,
                review_id=row.id,
                reservation_id=run.reservation_id,
                parent_run_id=parent.id if parent else None,
                parent_review_id=parent.review_id if parent else None,
                native_id=str(native.id),
                plan_digest=row.plan_digest,
                review_digest=row.digest,
                creation_posts=5,
                activation_posts=3 if mode == "activation" else 0,
            )
            db.commit()
        with Path(output).open("x") as stream:
            json.dump(data, stream)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
