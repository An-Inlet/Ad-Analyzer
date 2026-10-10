"""Current physical DDL retained; only literal historical producer runs in child."""

import os
import re
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.database.models import register_models
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url

from tests.financial_origin_retained_fixture import schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.two_brand_receipt_contracts import TwoBrandReceiptSourceV1, parse_source


@contextmanager
def source_engine(original: Engine, root: Path) -> Iterator[Engine]:
    assert root.is_absolute() and not root.exists()
    assert all(not p.is_symlink() for p in root.parents)
    root.mkdir()
    if original.dialect.name == "sqlite":
        path = root / "current.sqlite"
        path.touch(exist_ok=False)
        engine = create_engine(f"sqlite:///{path}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        register_models().create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()
    else:
        assert original.url == make_url(validate_disposable_url())
        yield original


def produce(engine: Engine, root: Path) -> TwoBrandReceiptSourceV1:
    assert root.is_dir() and root.resolve() == root
    assert shutil.disk_usage(root).free >= 500 * 1024**2, "500MiB heavy-run preflight"
    artifacts = root / "original"
    artifacts.mkdir()
    if engine.dialect.name == "sqlite":
        assert engine.url.database == str(root / "current.sqlite")
        target = str(engine.url)
    else:
        url = make_url(validate_disposable_url())
        assert engine.url == url and url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        with engine.connect() as db:
            target = str(db.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    before = schema_snapshot(engine)
    with engine.connect() as db:
        for name in inspect(engine).get_table_names():
            if name != "alembic_version":
                quoted = db.dialect.identifier_preparer.quote(name)
                assert db.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
    repo = Path(__file__).resolve().parents[1]
    with SourceLifetime.open("two_brand_receipt", artifacts) as lifetime:
        extract(repo, lifetime.source)
        lifetime.extracted()
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        lifetime.child_started()
        code = run_bounded(
            [
                sys.executable,
                str(repo / "tests/fixtures/retired_execution/two_brand_receipt_seed_driver.py"),
                target,
                str(output),
            ],
            lifetime.source,
            dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)),
            log,
            180,
        )
        lifetime.after_reaped(code)
    assert schema_snapshot(engine) == before
    assert code == 0, log.read_text()[-6000:]
    assert output.is_file() and not output.is_symlink() and output.stat().st_size <= 16384
    return parse_source(output.read_text())
