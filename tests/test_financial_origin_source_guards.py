"""Exact URL allowlist and parent fresh-row checks precede child extraction."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.financial_origin_retained_fixture import fresh_rows, validate_pg_url

BASE = make_url("postgresql+psycopg://postgres@127.0.0.1:55432/inlet_guard_ci")
SCHEMA = "inlet_migration_fixture_" + "a" * 32


@pytest.mark.parametrize("query", [{}, {"options": f"-csearch_path={SCHEMA}"}])
def test_exact_parent_pg_url_accepts_only_frozen_shapes(query: dict[str, str]) -> None:
    validate_pg_url(BASE.set(query=query), BASE)
    validate_pg_url(BASE.set(query=query), BASE, SCHEMA)


@pytest.mark.parametrize(
    "query",
    [
        {"sslmode": "disable"},
        {"options": f"-csearch_path={SCHEMA}", "sslmode": "disable"},
        {"options": f"-csearch_path={SCHEMA} -cstatement_timeout=0"},
        {"options": "-csearch_path=public"},
        {"options": f"-csearch_path=inlet_test_{'a' * 32}"},
    ],
)
def test_parent_pg_url_rejects_extra_settings(query: dict[str, str]) -> None:
    with pytest.raises(AssertionError):
        validate_pg_url(BASE.set(query=query), BASE)


def test_parent_pg_url_binds_actual_schema_and_base() -> None:
    candidate = BASE.set(query={"options": f"-csearch_path={SCHEMA}"})
    with pytest.raises(AssertionError):
        validate_pg_url(candidate, BASE, "inlet_migration_fixture_" + "b" * 32)
    with pytest.raises(AssertionError):
        validate_pg_url(BASE.set(database="other"), BASE)
    with pytest.raises(AssertionError):
        validate_pg_url(BASE.set(query={"options": (f"-csearch_path={SCHEMA}", "other")}), BASE)


def test_parent_sqlite_rejects_nonempty_rows_without_bootstrap_exception(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'guard.sqlite'}")
    try:
        with engine.begin() as db:
            db.execute(text("CREATE TABLE workspaces (id INTEGER PRIMARY KEY)"))
            db.execute(text("CREATE TABLE alembic_version (version_num TEXT)"))
        assert fresh_rows(engine) == {}
        with engine.begin() as db:
            db.execute(text("INSERT INTO workspaces VALUES (1)"))
        with pytest.raises(AssertionError):
            fresh_rows(engine)
    finally:
        engine.dispose()
