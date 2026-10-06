"""Migration-test schemas built by Alembic, never stamped from ORM metadata."""

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.database.models import register_models
from app.settings import settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.pool import StaticPool


@pytest.fixture(params=["sqlite", "postgres"])
def migration_customer_engine(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Generator[Engine, None, None]:
    if request.param == "sqlite":
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        register_models().create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()
        return
    url = os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
    if not url or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true":
        pytest.skip("explicit disposable PostgreSQL configuration required")
    url = validate_disposable_url()
    schema = "inlet_migration_fixture_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    try:
        # All current branches are real migrations. This also works while independent
        # branches await a merge revision; the tests downgrade explicit predecessors.
        command.upgrade(Config("alembic.ini"), "heads")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
