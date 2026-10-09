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
from sqlalchemy import create_engine, event, inspect, select, text
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
    from app.campaign_review.models import CampaignRevision
    from app.google_connections.models import GoogleCustomerConnection
    from app.meta.models import MetaConnection
    from tests.google_runtime_fixture import configured_customer
    from tests.meta_runtime_fixture import configured_meta_customer
    from tests.test_customer_identity import replicas
    from tests.test_shopify_sales import configuration

    try:
        with pytest.MonkeyPatch.context() as patch:
            clients = cast(Any, replicas).__wrapped__(engine, patch)
            config = cast(Any, configuration).__wrapped__()
            build = configured_customer if provider == "google_ads" else configured_meta_customer
            result = build(engine, config, Path(output).parent / "media", patch, clients)
            _, _, _, draft_id, revision, server, requests, _ = result
            assert server.posts == server.activations == 0 and not requests
            with Session(engine) as db:
                row = db.get(CampaignRevision, (draft_id, revision))
                assert row and row.approved_by
                definition = row.artifact["definition"]
                native: GoogleCustomerConnection | MetaConnection | None
                if provider == "google_ads":
                    native = db.scalar(
                        select(GoogleCustomerConnection).where(
                            GoogleCustomerConnection.workspace_id == row.workspace_id
                        )
                    )
                else:
                    native = db.scalar(
                        select(MetaConnection).where(
                            MetaConnection.workspace_id == row.workspace_id
                        )
                    )
                assert native
                data = dict(
                    provider=provider,
                    workspace_id=row.workspace_id,
                    actor_id=row.approved_by,
                    account_id=definition["account"]["account_id"],
                    native_connection_id=native.id,
                    draft_id=draft_id,
                    draft_revision=revision,
                    draft_digest=row.digest,
                    simulation_mandate_id=definition["mandate_id"],
                    simulation_mandate_revision=definition["mandate_revision"],
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
