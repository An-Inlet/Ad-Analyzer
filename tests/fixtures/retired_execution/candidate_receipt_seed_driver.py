"""Closed original Google receipt producer; current parent only reconciles evidence."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, make_url, text
from sqlalchemy.orm import Session
from tests.test_optimization_candidates import fixture
from tests.test_shopify_sales import configuration


def main() -> None:
    target, output = sys.argv[1:]
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    if target.startswith("sqlite:"):
        engine = create_engine(target)
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
        with Session(engine) as db:
            principal, work, _, _, _, server = fixture(db, config, Path(output).parent, True)
            assert len(server.writes) == 1
            scope = work.scope
            result = dict(
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
        assert set(inspect(engine).get_table_names()) == tables
        Path(output).write_text(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
