"""Fixed Google historical review-link producer; no approval or dispatch."""

import json
import os
import re
import runpy
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from alembic.script import ScriptDirectory
from app.optimization_candidates import review_bridge
from app.optimization_candidates.models import CandidateResult
from app.optimization_candidates.review_models import CandidateReviewLink
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import MetaData, Table, create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_candidate_review_bridge import assembled
from tests.test_shopify_sales import configuration

ZERO = (
    "provider_execution_approvals",
    "provider_execution_attempts",
    "provider_execution_receipts",
    "provider_execution_responses",
    "provider_exposure_reservations",
    "provider_execution_runs",
    "provider_execution_steps",
)
DIGESTS = (
    "candidate_digest",
    "input_digest",
    "selection_digest",
    "policy_digest",
    "evidence_digest",
    "source_digest",
    "review_digest",
    "plan_digest",
)


def main() -> None:
    target, output = sys.argv[1:]
    assert (
        os.environ.get("INLET_RETIRED_EXECUTION_CHILD")
        == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    artifacts = Path(output).resolve().parent
    root = Path(__file__).resolve().parents[3]
    if target.startswith("sqlite:"):
        url = make_url(target)
        assert url.database and not url.query
        assert Path(url.database).resolve() == artifacts / "current.sqlite"
        assert Path(url.database).is_file()
        engine = create_engine(url)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_(test|candidates)_[a-f0-9]{32}", target)
        url = make_url(validate_disposable_url())
        assert (
            url.drivername == "postgresql+psycopg"
            and url.host in {"localhost", "127.0.0.1", "::1"}
            and not url.query
        )
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
    try:
        tables = set(inspect(engine).get_table_names())
        expected = {}
        if engine.dialect.name == "postgresql" and "alembic_version" in tables:
            expected = runpy.run_path(str(root / "scripts/inlet_restore_bootstrap.py"))[
                "expected_bootstrap"
            ]()
        bootstrap = {}
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                assert connection.scalar(text("SELECT current_schema()")) == target
                if target.startswith("inlet_candidates_"):
                    assert set(
                        connection.scalars(text("SELECT version_num FROM alembic_version"))
                    ) == set(ScriptDirectory(str(root / "migrations")).get_heads())
            assert set(expected) <= tables
            for name in tables - {"alembic_version"}:
                if name not in expected:
                    quoted = engine.dialect.identifier_preparer.quote(name)
                    assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
                    continue
                table = Table(name, MetaData(), autoload_with=connection, resolve_fks=False)
                rows = [dict(row) for row in connection.execute(select(table)).mappings()]
                stripped = [
                    {k: v for k, v in row.items() if k not in {"created_at", "updated_at"}}
                    for row in rows
                ]

                def key(row: dict[str, Any]) -> str:
                    return json.dumps(row, sort_keys=True, default=str)

                assert sorted(map(key, stripped)) == sorted(map(key, expected[name]))
                bootstrap[name] = rows
        with pytest.MonkeyPatch.context() as patch, Session(engine) as db:
            principal, wid, intent, runtime, server = assembled(
                db, cast(Any, configuration).__wrapped__(), artifacts / "media", "google_ads", patch
            )
            prepared = review_bridge.prepare_candidate_review(db, principal, wid, intent, runtime)
            assert prepared.status == "review_required" and len(server.writes) == 0
            link = db.get(CandidateReviewLink, prepared.review_id)
            assert link and link.candidate_result_id
            result = db.get(CandidateResult, link.candidate_result_id)
            assert result
            data = dict(
                workspace_id=wid,
                actor_id=principal.user.id,
                job_id=result.job_id,
                result_id=result.id,
                review_id=link.review_id,
                provider_posts=len(server.writes),
            )
            data.update({name: getattr(link, name) for name in DIGESTS})
            db.commit()
            for name in ZERO:
                assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0
        with engine.connect() as connection:
            for name, rows in bootstrap.items():
                table = Table(name, MetaData(), autoload_with=connection, resolve_fks=False)
                for before in rows:
                    statement = select(table).where(
                        *(c == before[c.name] for c in table.primary_key.columns)
                    )
                    assert dict(connection.execute(statement).mappings().one()) == before
        Path(output).write_text(json.dumps(data))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
