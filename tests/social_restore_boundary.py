"""Closed loopback schema checks shared with isolated original-source children."""

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, MetaData, Table, inspect, make_url, select, text

ROOT = Path(__file__).resolve().parents[1]
Mode = Literal["social", "reported"]


def load_file(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def heads() -> set[str]:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return set(ScriptDirectory.from_config(config).get_heads())


def owned(engine: Engine, mode: Mode, revision: str | None = None) -> str:
    from scripts.reset_disposable_postgres import validate_disposable_url

    assert mode in {"social", "reported"}
    url = make_url(validate_disposable_url())
    assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
    assert engine.url.set(query={}) == url
    with engine.connect() as db:
        schema = str(db.scalar(text("SELECT current_schema()")))
        prefix = "inlet_social_config_" if mode == "social" else "inlet_migration_fixture_"
        assert re.fullmatch(prefix + r"[a-f0-9]{32}", schema)
        assert dict(engine.url.query) == {"options": f"-csearch_path={schema}"}
        expected = {revision} if revision else heads()
        assert set(db.scalars(text("SELECT version_num FROM alembic_version"))) == expected
    return schema


def fresh(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    module = load_file("_closed_bootstrap", ROOT / "scripts/inlet_restore_bootstrap.py")
    expected = module.expected_bootstrap()
    tables = set(inspect(engine).get_table_names())
    assert set(expected) <= tables
    snapshot = {}
    with engine.connect() as db:
        for name in sorted(tables - {"alembic_version"}):
            quoted = db.dialect.identifier_preparer.quote(name)
            if name not in expected:
                assert db.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
                continue
            table = Table(name, MetaData(), autoload_with=db, resolve_fks=False)
            rows = [dict(r) for r in db.execute(select(table)).mappings()]
            stripped = [
                {k: v for k, v in row.items() if k not in {"created_at", "updated_at"}}
                for row in rows
            ]
            assert sorted(json.dumps(r, sort_keys=True, default=str) for r in stripped) == sorted(
                json.dumps(r, sort_keys=True, default=str) for r in expected[name]
            )
            snapshot[name] = rows
    return snapshot


def unchanged(engine: Engine, snapshot: dict[str, list[dict[str, Any]]]) -> None:
    with engine.connect() as db:
        for name, rows in snapshot.items():
            table = Table(name, MetaData(), autoload_with=db, resolve_fks=False)
            for before in rows:
                query = select(table).where(*(c == before[c.name] for c in table.primary_key))
                after = dict(db.execute(query).mappings().one())
                assert json.dumps(after, sort_keys=True, default=str) == json.dumps(
                    before, sort_keys=True, default=str
                )


def read_output(path: Path, fields: set[str]) -> dict[str, Any]:
    assert path.stat().st_size <= 4096
    value = json.loads(path.read_text())
    assert type(value) is dict and set(value) == fields
    for key, item in value.items():
        if key in {
            "workspace_id",
            "source_id",
            "run_count",
            "provider_posts",
            "receipt_count",
            "hold_count",
        }:
            assert type(item) is int and item >= (0 if key == "provider_posts" else 1)
        elif key != "observed_at":
            assert type(item) is str and re.fullmatch(
                r"[a-f0-9]{64}" if "digest" in key else r"[a-f0-9]{32}", item
            )
    return value
