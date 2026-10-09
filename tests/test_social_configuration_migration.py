"""Only generated schemas on explicitly disposable PostgreSQL are modified."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
from app.publication.social_review_models import SocialConfigurationReview
from app.settings import settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    func,
    insert,
    inspect,
    make_url,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, make_transient_to_detached


class HistoricalFixtureSession(Session):
    """Insert reviews using the actual pre0059 schema, never newer ORM defaults."""

    def add(self, instance: object, _warn: bool = True) -> None:
        if isinstance(instance, ProviderExecutionReview):
            table = Table("provider_execution_reviews", MetaData(), autoload_with=self.connection())
            later = {
                "initial_preview_origin_id",
                "initial_preview_provenance_required",
                "candidate_provenance_required",
                "automatic_authority_required",
            }
            assert not later.intersection(table.c.keys())
            assert all(not instance.__dict__.get(name) for name in later)
            values = {
                column.name: instance.__dict__[column.name]
                for column in table.columns
                if column.name in instance.__dict__
            }
            self.execute(insert(table).values(values))
            make_transient_to_detached(instance)
        super().add(instance, _warn=_warn)


def test_populated_no_dsa_review_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL") or (
        os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_social_config_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0057")
        from tests.social_migration_retained_fixture import retained_social_configuration_fixture

        with retained_social_configuration_fixture(
            engine, tmp_path / "retained-social"
        ) as producer:
            command.upgrade(config, "20261006_0059")
            result = producer.confirm_after_upgrade()
        identifier = result.configuration_review_id
        with Session(engine) as db:
            row = db.get(SocialConfigurationReview, identifier)
            assert row and row.workspace_id == result.workspace_id
            assert row.digest == result.configuration_digest
            mapping = {column.name: getattr(row, column.name) for column in row.__table__.columns}
            with pytest.raises(IntegrityError), db.begin_nested():
                db.execute(
                    insert(SocialConfigurationReview).values(
                        **{
                            **mapping,
                            "id": uuid4().hex,
                            "workspace_id": result.workspace_id + 9999,
                        }
                    )
                )
        command.downgrade(config, "20261006_0057")
        assert "customer_social_configuration_reviews" not in inspect(engine).get_table_names()
        with Session(engine) as db:
            # Historical schemas have the row identity, not later ORM authority columns.
            assert db.scalar(select(func.count(ProviderExecutionRun.id))) == 1
        command.upgrade(config, "20261006_0059")
        with Session(engine) as db:
            assert db.get(SocialConfigurationReview, identifier) is None
            assert db.scalar(select(func.count(ProviderExecutionRun.id))) == 1
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
