"""SQL-only boundary shared by current parent and fixed original provider phases."""

import hashlib
import json
import re
import runpy
from pathlib import Path
from typing import Any, Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, MetaData, Table, inspect, select, text
from sqlalchemy.engine import make_url

Mode = Literal["qualification_only", "qualification_approved", "execution_consent"]
MODES = {"qualification_only", "qualification_approved", "execution_consent"}
SOURCE_FIELDS = {
    "workspace_id",
    "actor_id",
    "simulation_mandate_id",
    "goal_id",
    "goal_revision",
    "account_id",
    "native_connection_id",
    "source_draft_id",
    "source_draft_revision",
    "source_draft_digest",
    "provider_policy_digest",
}
ZERO = {
    "provider_execution_reviews",
    "provider_execution_approvals",
    "provider_execution_runs",
    "provider_execution_steps",
    "provider_execution_attempts",
    "provider_execution_responses",
    "provider_execution_receipts",
    "provider_exposure_reservations",
}
QUAL = {"provider_qualifications", "provider_reviews", "provider_review_approvals"}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read(path: Path) -> dict[str, Any]:
    assert not path.is_symlink() and path.is_file() and path.stat().st_size <= 8192
    value = json.loads(path.read_bytes())
    assert type(value) is dict
    return value


def source_ids(value: dict[str, Any]) -> None:
    assert set(value) == SOURCE_FIELDS
    for key, item in value.items():
        if key in {"workspace_id", "account_id", "goal_revision", "source_draft_revision"}:
            assert type(item) is int and item > 0
        else:
            assert type(item) is str
            assert re.fullmatch(
                r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", item
            )


def directory(path: Path) -> None:
    assert path.is_absolute() and path.resolve() == path and not path.is_symlink()
    assert all(not p.is_symlink() for p in path.parents)


def owned(engine: Engine, mode: str, root: Path) -> str:
    assert mode in MODES and engine.dialect.name == "postgresql"
    base = make_url(validate_disposable_url())
    assert base.drivername == "postgresql+psycopg" and not base.query
    assert base.host in {"localhost", "127.0.0.1", "::1"}
    assert engine.url.set(query={}) == base
    if engine.url.query:
        assert set(engine.url.query) == {"options"}
        option = engine.url.query["options"]
        assert type(option) is str
        assert re.fullmatch(r"-csearch_path=inlet_migration_fixture_[a-f0-9]{32}", option)
    with engine.connect() as db:
        schema = str(db.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_(test|migration_fixture)_[a-f0-9]{32}", schema)
        if engine.url.query:
            assert engine.url.query["options"] == f"-csearch_path={schema}"
        tables = set(inspect(db).get_table_names())
        if schema.startswith("inlet_migration_fixture_"):
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "migrations"))
            assert set(db.scalars(text("SELECT version_num FROM alembic_version"))) == set(
                ScriptDirectory.from_config(config).get_heads()
            )
        else:
            assert mode == "qualification_only" and "alembic_version" not in tables
    return schema


def snapshot(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    result = {}
    with engine.connect() as db:
        for name in sorted(inspect(db).get_table_names()):
            table = Table(name, MetaData(), autoload_with=db, resolve_fks=False)
            rows = [dict(row) for row in db.execute(select(table)).mappings()]
            result[name] = sorted(rows, key=canonical)
    return result


def shape(engine: Engine) -> str:
    i = inspect(engine)
    tables = {
        name: dict(
            columns=[{**col, "type": str(col["type"])} for col in i.get_columns(name)],
            fks=i.get_foreign_keys(name),
            checks=i.get_check_constraints(name),
            indexes=i.get_indexes(name),
            pk=i.get_pk_constraint(name),
        )
        for name in sorted(i.get_table_names())
    }
    with engine.connect() as db:
        triggers = db.execute(
            text(
                "SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=current_schema() AND NOT t.tgisinternal "
                "ORDER BY c.relname,t.tgname"
            )
        ).all()
    return digest(dict(tables=tables, triggers=[list(row) for row in triggers]))


def before_phase(
    rows: dict[str, list[dict[str, Any]]],
    ids: dict[str, Any],
    mode: str,
    mandate_id: str | None,
    schema: str,
) -> None:
    source_ids(ids)
    assert mode in MODES
    for name in ZERO | QUAL:
        assert rows[name] == []
    assert re.fullmatch(r"inlet_(test|migration_fixture)_[a-f0-9]{32}", schema)
    owned_rows = [row for row in rows["workspaces"] if row["id"] == ids["workspace_id"]]
    assert len(owned_rows) == 1
    if schema.startswith("inlet_migration_fixture_"):
        bootstrap = runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "scripts/inlet_restore_bootstrap.py")
        )["expected_bootstrap"]()
        assert ids["workspace_id"] != 1 and len(rows["workspaces"]) == 2
        for table, expected in bootstrap.items():
            for original in expected:
                matches = [
                    row
                    for row in rows[table]
                    if all(row.get(key) == value for key, value in original.items())
                ]
                assert len(matches) == 1
    else:
        assert len(rows["workspaces"]) == 1
    assert any(row["id"] == ids["actor_id"] for row in rows["customer_users"])
    assert any(
        row["user_id"] == ids["actor_id"]
        and row["workspace_id"] == ids["workspace_id"]
        and row["role"] == "owner"
        and row["status"] == "active"
        for row in rows["customer_memberships"]
    )
    draft = [
        row
        for row in rows["customer_campaign_revisions"]
        if row["draft_id"] == ids["source_draft_id"]
        and row["revision"] == ids["source_draft_revision"]
    ]
    assert len(draft) == 1 and draft[0]["workspace_id"] == ids["workspace_id"]
    assert draft[0]["digest"] == ids["source_draft_digest"]
    assert draft[0]["approved_by"] == ids["actor_id"]
    if mode != "execution_consent":
        assert mandate_id is None
        for table in (
            "provider_execution_mandates",
            "provider_execution_revisions",
            "provider_execution_consents",
            "provider_period_ledgers",
        ):
            assert rows[table] == []
    else:
        assert type(mandate_id) is str and re.fullmatch(r"[a-f0-9]{32}", mandate_id)
        mandates, revisions, ledgers = (
            rows[name]
            for name in (
                "provider_execution_mandates",
                "provider_execution_revisions",
                "provider_period_ledgers",
            )
        )
        assert len(mandates) == len(revisions) == len(ledgers) == 1
        mandate, revision, ledger = mandates[0], revisions[0], ledgers[0]
        assert mandate["id"] == mandate_id and mandate["workspace_id"] == ids["workspace_id"]
        assert mandate["state"] == "draft" and mandate["revision"] == 1
        assert revision["mandate_id"] == mandate_id and revision["revision"] == 1
        assert revision["digest"] == ids["provider_policy_digest"]
        assert revision["origin_kind"] == "legacy" and revision["origin_preparation_digest"] is None
        assert (
            ledger["id"] == mandate["ledger_id"] and ledger["workspace_id"] == ids["workspace_id"]
        )
        assert rows["provider_execution_consents"] == []
