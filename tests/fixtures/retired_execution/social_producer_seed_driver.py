"""Closed original social compiler source; no dispatch or runtime serialization."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from app.campaign_review.contracts import MAX_VIDEO_BYTES
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests import test_social_customer_producer as original
from tests.test_shopify_sales import configuration
from tests.test_social_coordinator_journeys import SocialServer


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


def main() -> None:
    target, output, provider = sys.argv[1:]
    assert provider in {"meta_ads", "tiktok_ads"}
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    artifacts = Path(output).parent
    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink() and all(not p.is_symlink() for p in artifacts.parents)
    video = None
    source_video = artifacts / "input.mp4"
    if provider == "tiktok_ads":
        assert source_video.is_file() and not source_video.is_symlink()
        assert 0 < source_video.stat().st_size <= MAX_VIDEO_BYTES
        video = source_video.read_bytes()
    else:
        assert not source_video.exists()
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
        captured: list[Any] = []
        ready = cast(Any, original).ready

        def record(*args: Any, **kwargs: Any) -> Any:
            value = ready(*args, **kwargs)
            assert isinstance(args[5], SocialServer) and args[5].posts == 0
            captured.append((value, args[5]))
            return value

        with pytest.MonkeyPatch.context() as patch, Session(engine) as db:
            patch.setattr(original, "ready", record)
            plan, account, _, _, actor, _, _, native = original.fixture(
                db, cast(Any, configuration).__wrapped__(), artifacts / "media", provider, video
            )
            assert len(captured) == 1
            value, server = captured[0]
            wid, run_id, captured_actor, _, _, captured_native = value
            assert actor == captured_actor and native is captured_native
            run = db.scalars(select(ProviderExecutionRun)).one()
            review = db.get(ProviderExecutionReview, run.review_id)
            assert run.id == run_id and review and run.workspace_id == wid == account.workspace_id
            assert review.plan_digest == plan.digest()
            for table in (
                "provider_execution_attempts",
                "provider_execution_responses",
                "provider_execution_receipts",
            ):
                assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
            assert server.posts == 0
            data = dict(
                workspace_id=wid,
                actor_id=actor,
                run_id=run_id,
                review_id=review.id,
                account_id=account.account.account_id,
                provider=provider,
                native_id=str(native.id),
                plan_digest=plan.digest(),
                native_posts=server.posts,
            )
            db.commit()
        Path(output).write_text(json.dumps(data))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
