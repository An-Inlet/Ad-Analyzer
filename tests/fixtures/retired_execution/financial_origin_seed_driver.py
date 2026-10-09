"""Two fixed historical financial source modes; never schema DDL or dispatch."""

import json
import os
import re
import runpy
import sys
from pathlib import Path
from typing import Any, cast

import app
from app.campaign_review.models import CampaignRevision
from app.mandates.models import Mandate
from app.publication import execution_mandates as service
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import MetaData, Table, create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_commerce_measurement import NOW
from tests.test_provider_execution_mandates import setup
from tests.test_shopify_sales import configuration


def main() -> None:
    target, output, mode = sys.argv[1:]
    assert mode in {"source_only", "consented_origin"}
    assert (
        os.environ.get("INLET_RETIRED_EXECUTION_CHILD")
        == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    artifacts = Path(output).resolve().parent
    if target.startswith("sqlite:"):
        url = make_url(target)
        assert url.database and not url.query
        assert Path(url.database).resolve().is_relative_to(artifacts.parent)
        assert Path(url.database).is_file()
        engine = create_engine(url)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_(test|migration_fixture)_[a-f0-9]{32}", target)
        url = make_url(validate_disposable_url())
        assert url.host in {"127.0.0.1", "localhost", "::1"} and not url.query
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
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
            policy, actor = setup(db, cast(Any, configuration).__wrapped__(), artifacts / "media")
            simulation = db.scalars(select(Mandate)).one()
            source = db.scalars(select(CampaignRevision)).one()
            result = dict(
                workspace_id=policy.workspace_id,
                actor_id=actor,
                simulation_mandate_id=simulation.id,
                goal_id=policy.goal_id,
                goal_revision=policy.goal_revision,
                account_id=policy.accounts[0].account.account_id,
                native_connection_id=policy.accounts[0].connection_version.split(":")[1],
                source_draft_id=source.draft_id,
                source_draft_revision=source.revision,
                source_draft_digest=source.digest,
                provider_policy_digest=policy.digest(),
            )
            if mode == "consented_origin":
                mandate = service.revise(db, policy.workspace_id, policy, actor, lambda: NOW)
                binding = service.consent(
                    db, policy.workspace_id, mandate.id, 1, policy.digest(), actor, lambda: NOW
                )
                result.update(
                    provider_mandate_id=mandate.id,
                    provider_mandate_revision=1,
                    provider_consent_id=binding.consent_id,
                    ledger_id=binding.ledger_id,
                )
            db.commit()
            for table_name in (
                "provider_execution_attempts",
                "provider_execution_receipts",
                "provider_exposure_reservations",
            ):
                assert db.scalar(text(f"SELECT count(*) FROM {table_name}")) == 0
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
        engine.dispose()


if __name__ == "__main__":
    main()
