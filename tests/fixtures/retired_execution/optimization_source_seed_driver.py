"""Exact pinned approved-draft producer; no execution operations or exported authority."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def main() -> None:
    target, output, provider = sys.argv[1:]
    assert provider in {"google_ads", "meta_ads"}
    assert os.environ["INLET_RETIRED_EXECUTION_CHILD"] == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]))
    if target.startswith("sqlite:"):
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        assert os.environ["AD_ANALYZER_CI_DISPOSABLE_POSTGRES"] == "true"
        url = make_url(validate_disposable_url())
        assert url.drivername == "postgresql+psycopg"
        assert url.host in {"127.0.0.1", "localhost", "::1"} and not url.query
        assert url.database and re.fullmatch(r"inlet_[a-z0-9_]+_ci", url.database)
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
    tables = set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            assert connection.scalar(text("SELECT current_schema()")) == target
        for table in tables - {"alembic_version"}:
            quoted = engine.dialect.identifier_preparer.quote(table)
            assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from app.production_runtime.optimization_policy_contracts import OptimizationOperatingPolicyV1
    from tests.configured_optimization_fixture import configured
    from tests.test_customer_identity import replicas
    from tests.test_shopify_sales import configuration

    try:
        with pytest.MonkeyPatch.context() as patch:
            clients = cast(Any, replicas).__wrapped__(engine, patch)
            config = cast(Any, configuration).__wrapped__()
            alice, base, query, wire, control = configured(
                engine, config, Path(output).parent / "media", patch, clients, provider
            )
            assert wire.calls == [] and not wire.google.writes and not wire.meta.posts
            assert control["factory"] == control["opened"] == 0
            operating = OptimizationOperatingPolicyV1.model_validate_json(
                (Path(output).parent / "media" / "optimization-policy.json").read_text()
            )
            with Session(engine) as db:
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert session
                data = dict(
                    provider=provider,
                    workspace_id=int(base.split("/workspaces/")[1].split("/")[0]),
                    actor_id=session.user_id,
                    account_id=query["account_id"],
                    goal_id=query["goal_id"],
                    goal_revision=query["goal_revision"],
                    policy_digest=operating.digest(),
                    provider_posts=0,
                )
                for table in (
                    "provider_execution_attempts",
                    "provider_execution_receipts",
                    "provider_execution_reviews",
                    "provider_exposure_reservations",
                    "provider_execution_responses",
                    "provider_execution_consents",
                    "provider_execution_mandates",
                    "provider_execution_runs",
                ):
                    assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
            assert set(inspect(engine).get_table_names()) == tables
            Path(output).write_text(json.dumps(data))
            clients[0].close()
            clients[1].close()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
