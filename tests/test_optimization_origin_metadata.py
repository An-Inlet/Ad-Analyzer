"""Reusing actual metadata across dialects must retain the deferred authority FK."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from app.database.models import register_models
from app.publication import execution_mandates
from app.settings import Settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import current_policy, retained_financial_source
from tests.test_commerce_measurement import NOW
from tests.test_shopify_sales import configuration as configuration


def assert_owned_fk(engine: Engine) -> None:
    fk = next(
        item
        for item in inspect(engine).get_foreign_keys("provider_execution_revisions")
        if item["name"] == "fk_optimization_origin_digest"
    )
    assert fk["constrained_columns"] == ["origin_preparation_digest"]
    assert fk["referred_table"] == "optimization_mandate_preparations"
    assert fk["referred_columns"] == ["preparation_digest"]
    assert fk["options"]["deferrable"] is True
    assert fk["options"]["initially"] == "DEFERRED"


def test_actual_metadata_sqlite_postgres_sqlite_keeps_deferred_origin(
    configuration: Settings,
    tmp_path: Path,
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL configuration required")
    url = validate_disposable_url()
    metadata = register_models()
    before = create_engine("sqlite://")
    after = create_engine(f"sqlite:///{tmp_path / 'after.sqlite'}")
    admin = create_engine(url)
    schema = "inlet_origin_metadata_" + uuid4().hex
    pg = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        metadata.create_all(before)
        assert_owned_fk(before)
        metadata.create_all(pg)
        assert_owned_fk(pg)
        metadata.create_all(after)
        assert_owned_fk(after)
        with after.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        ids = retained_financial_source(after, tmp_path / "retained", "source_only")
        with Session(after) as db:
            policy, actor = current_policy(db, ids), ids.actor_id
            mandate = execution_mandates.revise(db, policy.workspace_id, policy, actor, lambda: NOW)
            mid = mandate.id
        # INSERT is allowed by the deferred constraint; COMMIT must fail without proof.
        with after.connect() as connection:
            transaction = connection.begin()
            connection.execute(
                text(
                    "INSERT INTO provider_execution_revisions "
                    "(mandate_id,revision,workspace_id,goal_id,goal_revision,policy,digest,actor,"
                    "created_at,origin_kind,origin_preparation_digest) "
                    "SELECT mandate_id,2,workspace_id,goal_id,goal_revision,policy,digest,actor,"
                    "created_at,'optimization_customer_v1',:digest "
                    "FROM provider_execution_revisions WHERE mandate_id=:mid AND revision=1"
                ),
                {"mid": mid, "digest": "a" * 64},
            )
            with pytest.raises(IntegrityError, match="FOREIGN KEY"):
                transaction.commit()
            connection.rollback()
    finally:
        before.dispose()
        after.dispose()
        pg.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.parametrize("trigger_source", ["orm", "migration"])
def test_sqlite_marked_insert_denied_if_physical_origin_fk_is_absent(
    configuration: Settings,
    tmp_path: Path,
    trigger_source: str,
) -> None:
    from sqlalchemy import event
    from sqlalchemy.schema import AddConstraint

    metadata = register_models()
    table = metadata.tables["provider_execution_revisions"]
    constraint = next(c for c in table.constraints if c.name == "fk_optimization_origin_digest")
    engine = create_engine(f"sqlite:///{tmp_path / 'malformed.sqlite'}")

    def simulate_ddl_suppression(*args: object, **kwargs: object) -> None:
        # Reproduce the library suppression after the repair callback, to prove
        # the insert guard independently rejects a physically malformed schema.
        AddConstraint(constraint)

    event.listen(table, "before_create", simulate_ddl_suppression)
    try:
        metadata.create_all(engine)
    finally:
        event.remove(table, "before_create", simulate_ddl_suppression)
    try:
        assert not any(
            fk["name"] == "fk_optimization_origin_digest"
            for fk in inspect(engine).get_foreign_keys(table.name)
        )
        with engine.begin() as connection:
            if trigger_source == "migration":
                from importlib import import_module

                migration = import_module("migrations.versions.20261007_0080_optimization_origin")
                for name in ("omr_insert", "omr_update", "omr_delete"):
                    connection.exec_driver_sql(f'DROP TRIGGER "{name}"')
                for statement in migration.PARENT_SQL["sqlite"]:
                    connection.exec_driver_sql(statement)
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        ids = retained_financial_source(engine, tmp_path / "retained", "source_only")
        with Session(engine) as db:
            policy, actor = current_policy(db, ids), ids.actor_id
            mandate = execution_mandates.revise(db, policy.workspace_id, policy, actor, lambda: NOW)
            mid = mandate.id
        with (
            pytest.raises(IntegrityError, match="requires enforced exact foreign key"),
            engine.begin() as connection,
        ):
            connection.execute(
                text(
                    "INSERT INTO provider_execution_revisions "
                    "(mandate_id,revision,workspace_id,goal_id,goal_revision,policy,digest,actor,"
                    "created_at,origin_kind,origin_preparation_digest) "
                    "SELECT mandate_id,2,workspace_id,goal_id,goal_revision,policy,digest,actor,"
                    "created_at,'optimization_customer_v1',:digest "
                    "FROM provider_execution_revisions WHERE mandate_id=:mid AND revision=1"
                ),
                {"mid": mid, "digest": "a" * 64},
            )
    finally:
        engine.dispose()
