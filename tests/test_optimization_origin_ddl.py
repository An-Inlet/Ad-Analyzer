# ruff: noqa: E501
"""No-rebuild origin DDL proof on populated real financial parent/RESTRICT children."""

from pathlib import Path
from typing import Any

import pytest
from app.lifecycle.export_serializers import serialize
from app.production_runtime.optimization_origin_contracts import OptimizationMandatePreparationV1
from app.production_runtime.optimization_policy_contracts import OptimizationCustomerIntentV1
from app.publication import execution_mandates
from app.settings import Settings
from sqlalchemy import JSON, Engine, bindparam, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_commerce_measurement import NOW
from tests.test_optimization_runtime_contracts import policy as operating_policy
from tests.test_provider_execution_mandates import setup
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def customer_engine(migration_customer_engine: Engine) -> Engine:
    # SQLite's common fixture is ORM-created. Only its EMPTY fixture table is
    # normalized to pre0080 shape before running the actual additive migration.
    # Production0080 never rebuilds a parent; the populated roundtrip below checks it.
    if migration_customer_engine.dialect.name == "sqlite":
        from importlib import import_module

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with migration_customer_engine.begin() as c:
            assert c.scalar(text("SELECT count(*) FROM provider_execution_revisions")) == 0
            with Operations.context(MigrationContext.configure(c)) as op:
                triggers = c.execute(
                    text("SELECT name,sql FROM sqlite_master WHERE type='trigger'")
                ).all()
                for name, _ in triggers:
                    c.exec_driver_sql(f'DROP TRIGGER "{name}"')
                op.drop_index(
                    "uq_optimization_origin_digest", table_name="provider_execution_revisions"
                )
                with op.batch_alter_table("provider_execution_revisions") as batch:
                    batch.drop_constraint("fk_optimization_origin_digest", type_="foreignkey")
                    batch.drop_constraint("ck_optimization_origin_kind", type_="check")
                    batch.drop_column("origin_preparation_digest")
                    batch.drop_column("origin_kind")
                op.drop_table("optimization_mandate_preparations")
                for name, sql in triggers:
                    if not name.startswith(("omr_", "omp_")):
                        c.exec_driver_sql(sql)
                import_module("migrations.versions.20261007_0080_optimization_origin").upgrade()
    return migration_customer_engine


def test_additive_deferred_digest_fk_preserves_populated_authority(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
    with Session(customer_engine) as db:
        policy, actor = setup(db, configuration, tmp_path)
        mandate = execution_mandates.revise(db, policy.workspace_id, policy, actor, lambda: NOW)
        execution_mandates.consent(
            db, policy.workspace_id, mandate.id, 1, policy.digest(), actor, lambda: NOW
        )
        mid, wid = mandate.id, policy.workspace_id
    # Existing actual immutable-policy bytes and real RESTRICT consent child survive.
    with customer_engine.connect() as connection:
        original = connection.execute(
            text("SELECT digest, policy FROM provider_execution_revisions WHERE mandate_id=:m"),
            {"m": mid},
        ).one()
        if customer_engine.dialect.name == "sqlite":
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    from importlib import import_module

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = import_module("migrations.versions.20261007_0080_optimization_origin")
    # Exercise actual0080 DDL on populated financial authority, without stamping
    # invented migration history or rebuilding the parent/RESTRICT children.
    with customer_engine.begin() as c, Operations.context(MigrationContext.configure(c)):
        migration.downgrade()
        migration.upgrade()
    side = "optimization_mandate_preparations"
    parent = text(
        "INSERT INTO provider_execution_revisions (mandate_id,revision,workspace_id,goal_id,goal_revision,policy,digest,actor,created_at,origin_kind,origin_preparation_digest) SELECT mandate_id,:r,workspace_id,goal_id,goal_revision,policy,digest,actor,created_at,'optimization_customer_v1',:d FROM provider_execution_revisions WHERE mandate_id=:m AND revision=1"
    )
    child = text(
        f"INSERT INTO {side} (mandate_id,mandate_revision,workspace_id,preparation_digest,provider_policy_digest,document) VALUES (:m,:r,:w,:d,:p,:doc)"
    )
    child = child.bindparams(bindparam("doc", type_=JSON))
    operating = operating_policy()
    document = OptimizationMandatePreparationV1(
        workspace_id=wid,
        mandate_id=mid,
        mandate_revision=2,
        environment="contract_test",
        provider_policy_digest=original.digest,
        goal_digest="a" * 64,
        intent=OptimizationCustomerIntentV1.model_validate(
            {
                "selection": {
                    "goal_id": policy.goal_id,
                    "goal_revision": policy.goal_revision,
                    "account_id": policy.accounts[0].account.account_id,
                    "option_id": "b" * 64,
                },
                "total_cap_micros": 10000,
                "aggressiveness": "balanced",
            }
        ),
        account_scope_digest="c" * 64,
        target_set_digest="d" * 64,
        inventory_request_digest="e" * 64,
        inventory_digest="f" * 64,
        native_state_digest="1" * 64,
        qualification_id="3" * 32,
        qualification_revision=1,
        qualification_digest="2" * 64,
        evidence_profile_digest=operating.evidence_profile_digest,
        operating_policy=operating,
        operating_policy_digest=operating.digest(),
    )
    args: dict[str, Any] = {
        "m": mid,
        "r": 2,
        "w": wid,
        "d": document.digest(),
        "p": original.digest,
        "doc": document.model_dump(mode="json"),
    }
    # Deferred FK permits parent insertion but missing sidecar cannot COMMIT.
    with pytest.raises(DBAPIError), customer_engine.begin() as c:
        c.execute(parent, args)
    with customer_engine.begin() as c:
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM provider_execution_revisions WHERE mandate_id=:m AND revision=2"
                ),
                args,
            )
            == 0
        )
        c.execute(parent, args)
        c.execute(child, args)
    # Digest uniqueness alone is insufficient: immediate parent guard forbids borrowing.
    with pytest.raises(DBAPIError), customer_engine.begin() as c:
        c.execute(parent, {**args, "r": 3})
    with pytest.raises(DBAPIError), customer_engine.begin() as c:
        c.execute(parent, {**args, "r": 3, "d": "b" * 64})
        c.execute(child, {**args, "r": 3, "d": "b" * 64, "w": wid + 1})
    with pytest.raises(DBAPIError), customer_engine.begin() as c:
        c.execute(parent, {**args, "r": 3, "d": "b" * 64})
        c.execute(child, {**args, "r": 3, "d": "b" * 64, "p": "f" * 64})
    # A later local admission failure rolls back both writes, not merely the proof.
    next_document = document.model_copy(update={"mandate_revision": 3})
    next_args = {
        **args,
        "r": 3,
        "d": next_document.digest(),
        "doc": next_document.model_dump(mode="json"),
    }
    with pytest.raises(RuntimeError, match="final admission failed"), customer_engine.begin() as c:
        c.execute(parent, next_args)
        c.execute(child, next_args)
        raise RuntimeError("final admission failed")
    with customer_engine.connect() as c:
        assert (
            c.scalar(text("SELECT count(*) FROM provider_execution_revisions WHERE revision=3"))
            == 0
        )
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM optimization_mandate_preparations WHERE mandate_revision=3"
                )
            )
            == 0
        )
    # Two parents cannot reserve the same digest before its sidecar exists either.
    with pytest.raises(DBAPIError), customer_engine.begin() as c:
        c.execute(parent, {**args, "r": 3, "d": "c" * 64})
        c.execute(parent, {**args, "r": 4, "d": "c" * 64})
        c.execute(child, {**args, "r": 3, "d": "c" * 64})
    # Reverse order cannot leave an orphan/differently bound sidecar.
    with pytest.raises(DBAPIError), customer_engine.begin() as c:
        c.execute(child, {**args, "r": 3, "d": "d" * 64})
        c.execute(parent, {**args, "r": 3, "d": "d" * 64})
    with customer_engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT digest,policy FROM provider_execution_revisions WHERE mandate_id=:m AND revision=1"
                ),
                args,
            ).one()
            == original
        )
        assert (
            c.scalar(
                text("SELECT count(*) FROM provider_execution_consents WHERE mandate_id=:m"), args
            )
            == 1
        )
        if customer_engine.dialect.name == "sqlite":
            assert c.scalar(text("PRAGMA foreign_keys")) == 1
            assert c.execute(text("PRAGMA foreign_key_check")).all() == []

    with customer_engine.connect() as c:
        row = dict(
            c.execute(text("SELECT * FROM optimization_mandate_preparations")).mappings().one()
        )
        # SQLite text results do not apply SQLAlchemy's JSON result processor.
        row["document"] = document.model_dump(mode="json")
        exported, omitted = serialize(side, row)
        assert exported["document"] == row["document"] and not omitted
        for invalid in (
            {**row, "workspace_id": wid + 1},
            {**row, "document": {**row["document"], "raw_response": "forbidden"}},
        ):
            exported, omitted = serialize(side, invalid)
            assert "document" not in exported and "document" in omitted
    for statement in (
        "UPDATE provider_execution_revisions SET digest=digest WHERE revision=2",
        "DELETE FROM provider_execution_revisions WHERE revision=2",
        "UPDATE provider_execution_revisions SET origin_kind='optimization_customer_v1',origin_preparation_digest='x' WHERE revision=1",
        "UPDATE optimization_mandate_preparations SET document=document",
        "DELETE FROM optimization_mandate_preparations",
    ):
        with pytest.raises(DBAPIError), customer_engine.begin() as c:
            c.execute(text(statement))
    with customer_engine.begin() as c:
        c.execute(text("UPDATE provider_execution_revisions SET digest=digest WHERE revision=1"))
    with (
        pytest.raises(RuntimeError, match="cannot discard retained"),
        customer_engine.begin() as c,
        Operations.context(MigrationContext.configure(c)),
    ):
        migration.downgrade()


def test_marked_origin_denied_when_sqlite_foreign_keys_are_not_enabled(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    if customer_engine.dialect.name != "sqlite":
        pytest.skip("SQLite connection integrity setting")
    with customer_engine.connect() as c:
        assert c.scalar(text("PRAGMA foreign_keys")) == 0
    with Session(customer_engine) as db:
        policy, actor = setup(db, configuration, tmp_path)
        mandate = execution_mandates.revise(db, policy.workspace_id, policy, actor, lambda: NOW)
        mid = mandate.id
    with (
        pytest.raises(DBAPIError, match="requires enforced exact foreign key"),
        customer_engine.begin() as c,
    ):
        c.execute(
            text(
                "INSERT INTO provider_execution_revisions (mandate_id,revision,workspace_id,goal_id,goal_revision,policy,digest,actor,created_at,origin_kind,origin_preparation_digest) SELECT mandate_id,2,workspace_id,goal_id,goal_revision,policy,digest,actor,created_at,'optimization_customer_v1',:d FROM provider_execution_revisions WHERE mandate_id=:m AND revision=1"
            ),
            {"m": mid, "d": "a" * 64},
        )
    with (
        pytest.raises(DBAPIError, match="immutable optimization revision origin"),
        customer_engine.begin() as c,
    ):
        c.execute(
            text(
                "UPDATE provider_execution_revisions SET origin_kind='optimization_customer_v1',origin_preparation_digest=:d WHERE mandate_id=:m"
            ),
            {"m": mid, "d": "a" * 64},
        )
