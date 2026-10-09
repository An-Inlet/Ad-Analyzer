"""Two genuine original Google sources; no candidate jobs, receipts or provider writes."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, make_url, text
from sqlalchemy.orm import Session
from tests import test_google_action_plans as fixtures
from tests.test_mandates import seed
from tests.test_optimization_candidates import fixture
from tests.test_shopify_sales import configuration


def main() -> None:
    target, filename = sys.argv[1:]
    output = Path(filename)
    assert os.environ["INLET_RETIRED_EXECUTION_CHILD"] == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
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
    patch = pytest.MonkeyPatch()
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            for name in tables - {"alembic_version"}:
                quoted = connection.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        config = cast(Any, configuration).__wrapped__()
        results = {}
        for name in ("first", "second"):
            patch.setattr(
                fixtures, "seed", lambda db, config, name=name, **kw: seed(db, config, name, **kw)
            )
            with Session(engine) as db:
                principal, work, _, _, _, server = fixture(
                    db, config, output.parent / name, with_receipt=False, provider="google_ads"
                )
                scope = work.scope
                assert not server.writes
                results[name] = dict(
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
                )
                db.commit()
        assert set(inspect(engine).get_table_names()) == tables
        with engine.connect() as connection:
            for table in ("optimization_candidate_jobs", "optimization_candidate_results"):
                assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        output.write_text(json.dumps(results))
    finally:
        patch.undo()
        engine.dispose()


if __name__ == "__main__":
    main()
