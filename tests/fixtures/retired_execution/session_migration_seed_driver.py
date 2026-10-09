"""Fixed original Start only, into a parent-owned current migration schema."""

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
from app.session_automation import service
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_session_automation import automatic_fixture
from tests.test_shopify_sales import configuration

ZERO_TABLES = (
    "optimization_candidate_jobs",
    "optimization_candidate_results",
    "provider_automatic_decisions",
    "provider_execution_reviews",
    "provider_execution_approvals",
    "provider_execution_runs",
    "provider_execution_steps",
    "provider_execution_attempts",
    "provider_execution_receipts",
    "provider_execution_responses",
    "provider_exposure_reservations",
)


def main() -> None:
    target, output = sys.argv[1:]
    assert re.fullmatch(r"inlet_auto_[a-f0-9]{32}", target)
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    url = make_url(validate_disposable_url())
    assert url.host in {"127.0.0.1", "localhost", "::1"} and not url.query
    engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
    patch = pytest.MonkeyPatch()
    try:
        tables = set(inspect(engine).get_table_names())
        expected = {}
        if engine.dialect.name == "postgresql" and "alembic_version" in tables:
            module = runpy.run_path(
                str(Path(__file__).resolve().parents[3] / "scripts/inlet_restore_bootstrap.py")
            )
            expected = module["expected_bootstrap"]()
        bootstrap = {}
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                assert connection.scalar(text("SELECT current_schema()")) == target
                root = Path(__file__).resolve().parents[3]
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
                normalized = [
                    {k: v for k, v in row.items() if k not in {"created_at", "updated_at"}}
                    for row in rows
                ]

                def key(row: dict[str, Any]) -> str:
                    return json.dumps(row, sort_keys=True, default=str)

                assert sorted(map(key, normalized)) == sorted(map(key, expected[name]))
                bootstrap[name] = rows
        with Session(engine) as db:
            principal, wid, intent, runtime, server = automatic_fixture(
                db,
                cast(Any, configuration).__wrapped__(),
                Path(output).parent / "media",
                "google_ads",
                patch,
            )
            run = service.start(db, principal, wid, intent, runtime)
            result = {
                name: getattr(run, name)
                for name in (
                    "workspace_id",
                    "actor_id",
                    "mandate_id",
                    "mandate_revision",
                    "consent_id",
                    "ledger_id",
                    "policy_id",
                    "policy_revision",
                    "mandate_digest",
                    "policy_digest",
                )
            }
            result.update(run_id=run.id, provider_posts=len(server.writes))
            assert result["provider_posts"] == 0
            db.commit()
            for name in ZERO_TABLES:
                assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0
        with engine.connect() as connection:
            for name, rows in bootstrap.items():
                table = Table(name, MetaData(), autoload_with=connection, resolve_fks=False)
                for before in rows:
                    statement = select(table).where(
                        *(c == before[c.name] for c in table.primary_key.columns)
                    )
                    assert dict(connection.execute(statement).mappings().one()) == before
        Path(output).write_text(json.dumps(result))
    finally:
        patch.undo()
        engine.dispose()


if __name__ == "__main__":
    main()
