"""Three fixed original operations at restored current schema; no DDL or dispatch."""

import json
import os
import runpy
import sys
from pathlib import Path

import app
from app.campaign_review.storage import LocalMediaStore
from app.publication import execution_mandates, provider_service
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tests.test_commerce_measurement import NOW
from tests.test_provider_qualification import prepare


def main() -> None:
    schema, directory = sys.argv[1:]
    assert (
        os.environ.get("INLET_RETIRED_EXECUTION_CHILD")
        == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    root = Path(__file__).resolve().parents[3]
    b = runpy.run_path(str(root / "tests/provider_ddl_boundary.py"))
    artifacts = Path(directory)
    b["directory"](artifacts)
    value = b["read"](artifacts / "input.json")
    assert set(value) == {"mode", "source", "mandate_id", "schema_digest", "rows_digest"}
    mode, ids = value["mode"], value["source"]
    b["source_ids"](ids)
    source = artifacts.parent / "original"
    b["directory"](source)
    assert b["read"](source / "ids.json") == ids
    b["directory"](source / "media")
    # Validate exact schema spelling before construction; owned() then checks the connected schema.
    import re

    assert re.fullmatch(r"inlet_(test|migration_fixture)_[a-f0-9]{32}", schema)
    from sqlalchemy.engine import make_url

    url = make_url(validate_disposable_url())
    assert url.drivername == "postgresql+psycopg" and not url.query
    assert url.host in {"localhost", "127.0.0.1", "::1"}
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        assert b["owned"](engine, mode, root) == schema
        rows = b["snapshot"](engine)
        assert b["shape"](engine) == value["schema_digest"]
        assert b["digest"](rows) == value["rows_digest"]
        b["before_phase"](rows, ids, mode, value["mandate_id"], schema)
        with Session(engine) as db:
            if mode == "execution_consent":
                _, mandate = execution_mandates.owned(db, ids["workspace_id"], value["mandate_id"])
                policy = execution_mandates.policy(db, mandate)
                assert policy.digest() == ids["provider_policy_digest"]
                binding = execution_mandates.consent(
                    db,
                    ids["workspace_id"],
                    mandate.id,
                    1,
                    policy.digest(),
                    ids["actor_id"],
                    lambda: NOW,
                )
                result = dict(
                    mode=mode,
                    workspace_id=ids["workspace_id"],
                    actor_id=ids["actor_id"],
                    provider_mandate_id=mandate.id,
                    revision=1,
                    provider_policy_digest=policy.digest(),
                    provider_consent_id=binding.consent_id,
                    ledger_id=binding.ledger_id,
                )
            else:
                store = LocalMediaStore(source / "media")
                row = prepare(
                    db, ids["workspace_id"], ids["source_draft_id"], ids["actor_id"], store
                )
                if mode == "qualification_approved":
                    provider_service.approve(
                        db,
                        ids["workspace_id"],
                        row.id,
                        row.review_digest,
                        row.plan_digest,
                        ids["actor_id"],
                        store,
                        lambda: NOW,
                    )
                result = dict(
                    mode=mode,
                    workspace_id=ids["workspace_id"],
                    actor_id=ids["actor_id"],
                    source_draft_id=row.draft_id,
                    source_revision=row.source_revision,
                    qualification_id=row.qualification_id,
                    review_id=row.id,
                    review_digest=row.review_digest,
                    plan_digest=row.plan_digest,
                )
            db.commit()
        assert b["owned"](engine, mode, root) == schema
        assert b["shape"](engine) == value["schema_digest"]
        raw = json.dumps(result)
        assert len(raw.encode()) <= 8192
        (artifacts / "ids.json").write_text(raw)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
