"""Untouched original Meta review-lock setup in an empty owned PostgreSQL schema."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
from app.meta.models import MetaConnection
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_meta_review_locks import meta_configuration, review_fixture
from tests.test_shopify_sales import configuration


def main() -> None:
    schema, output = sys.argv[1:]
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", schema)
    url = make_url(validate_disposable_url())
    assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            for name in set(inspect(engine).get_table_names()) - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        with Session(engine) as db:
            wid, body = review_fixture(
                db, cast(Any, configuration).__wrapped__(),
                cast(Any, meta_configuration).__wrapped__(),
            )
            native = db.scalars(select(MetaConnection)).one()
            assert native.workspace_id == wid
            data = dict(
                workspace_id=wid, mandate_id=body.mandate_id,
                mandate_revision=body.mandate_revision, account_id=body.account.account_id,
                integration_id=body.account.connection_id, native_id=native.id,
            )
        raw = json.dumps(data)
        assert len(raw.encode()) <= 8192
        Path(output).write_text(raw)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
