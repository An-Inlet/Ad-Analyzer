# ruff: noqa: E501
"""Protect exact optimization mandate origin without rebuilding financial parents."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0080"
down_revision = "20261007_0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_mandate_preparations",
        sa.Column("mandate_id", sa.String(32), primary_key=True),
        sa.Column("mandate_revision", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("provider_policy_digest", sa.String(64), nullable=False),
        sa.Column("preparation_digest", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.UniqueConstraint("preparation_digest", name="uq_optimization_preparation_digest"),
        sa.ForeignKeyConstraint(
            ["mandate_id", "mandate_revision", "workspace_id"],
            [
                "provider_execution_revisions.mandate_id",
                "provider_execution_revisions.revision",
                "provider_execution_revisions.workspace_id",
            ],
            name="fk_optimization_preparation_revision",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("mandate_revision > 0", name="ck_optimization_preparation_revision"),
    )
    op.execute(
        "ALTER TABLE provider_execution_revisions ADD COLUMN origin_kind VARCHAR(32) NOT NULL DEFAULT 'legacy'"
    )
    op.execute(
        "ALTER TABLE provider_execution_revisions ADD COLUMN origin_preparation_digest VARCHAR(64) CONSTRAINT fk_optimization_origin_digest REFERENCES optimization_mandate_preparations(preparation_digest) DEFERRABLE INITIALLY DEFERRED CONSTRAINT ck_optimization_origin_kind CHECK((origin_kind='legacy' AND origin_preparation_digest IS NULL) OR (origin_kind='optimization_customer_v1' AND origin_preparation_digest IS NOT NULL))"
    )
    op.create_index(
        "uq_optimization_origin_digest",
        "provider_execution_revisions",
        ["origin_preparation_digest"],
        unique=True,
    )
    for statement in (
        SIDECAR_SQL[op.get_bind().dialect.name] + PARENT_SQL[op.get_bind().dialect.name]
    ):
        op.execute(statement)


def downgrade() -> None:
    db = op.get_bind()
    if db.scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM optimization_mandate_preparations)")
    ) or db.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM provider_execution_revisions WHERE origin_kind!='legacy' OR origin_preparation_digest IS NOT NULL)"
        )
    ):
        raise RuntimeError("cannot discard retained optimization authority")
    if db.dialect.name == "sqlite":
        for name in (
            "omr_insert",
            "omr_update",
            "omr_delete",
            "omp_insert",
            "omp_update",
            "omp_delete",
        ):
            op.execute(f"DROP TRIGGER {name}")
    else:
        op.execute("DROP TRIGGER omr_guard ON provider_execution_revisions")
        op.execute("DROP FUNCTION omr_guard_fn()")
    op.drop_index("uq_optimization_origin_digest", table_name="provider_execution_revisions")
    op.execute("ALTER TABLE provider_execution_revisions DROP COLUMN origin_preparation_digest")
    op.execute("ALTER TABLE provider_execution_revisions DROP COLUMN origin_kind")
    op.drop_table("optimization_mandate_preparations")
    if db.dialect.name == "postgresql":
        op.execute("DROP FUNCTION omp_guard_fn()")


# Frozen historical statements, never import current application guards.
SIDECAR_SQL = {
    "sqlite": (
        "CREATE TRIGGER omp_insert BEFORE INSERT ON optimization_mandate_preparations WHEN NOT EXISTS (SELECT 1 FROM provider_execution_revisions r WHERE r.mandate_id=NEW.mandate_id AND r.revision=NEW.mandate_revision AND r.workspace_id=NEW.workspace_id AND r.digest=NEW.provider_policy_digest AND r.origin_kind='optimization_customer_v1' AND r.origin_preparation_digest=NEW.preparation_digest) BEGIN SELECT RAISE(ABORT,'optimization origin mismatch'); END",
        "CREATE TRIGGER omp_update BEFORE UPDATE ON optimization_mandate_preparations BEGIN SELECT RAISE(ABORT,'immutable optimization origin'); END",
        "CREATE TRIGGER omp_delete BEFORE DELETE ON optimization_mandate_preparations BEGIN SELECT RAISE(ABORT,'immutable optimization origin'); END",
    ),
    "postgresql": (
        "CREATE FUNCTION omp_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP != 'INSERT' THEN RAISE EXCEPTION 'immutable optimization origin'; END IF; IF NOT EXISTS (SELECT 1 FROM provider_execution_revisions r WHERE r.mandate_id=NEW.mandate_id AND r.revision=NEW.mandate_revision AND r.workspace_id=NEW.workspace_id AND r.digest=NEW.provider_policy_digest AND r.origin_kind='optimization_customer_v1' AND r.origin_preparation_digest=NEW.preparation_digest) THEN RAISE EXCEPTION 'optimization origin mismatch'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER omp_guard BEFORE INSERT OR UPDATE OR DELETE ON optimization_mandate_preparations FOR EACH ROW EXECUTE FUNCTION omp_guard_fn()",
    ),
}
PARENT_SQL = {
    "sqlite": (
        "CREATE TRIGGER omr_insert BEFORE INSERT ON provider_execution_revisions WHEN NEW.origin_kind='optimization_customer_v1' AND ((SELECT foreign_keys FROM pragma_foreign_keys)!=1 OR EXISTS (SELECT 1 FROM optimization_mandate_preparations p WHERE p.preparation_digest=NEW.origin_preparation_digest AND (p.mandate_id!=NEW.mandate_id OR p.mandate_revision!=NEW.revision OR p.workspace_id!=NEW.workspace_id OR p.provider_policy_digest!=NEW.digest))) BEGIN SELECT RAISE(ABORT,'optimization origin requires enforced exact foreign key'); END",
        "CREATE TRIGGER omr_update BEFORE UPDATE ON provider_execution_revisions WHEN OLD.origin_kind!='legacy' OR NEW.origin_kind!=OLD.origin_kind OR NEW.origin_preparation_digest IS NOT OLD.origin_preparation_digest BEGIN SELECT RAISE(ABORT,'immutable optimization revision origin'); END",
        "CREATE TRIGGER omr_delete BEFORE DELETE ON provider_execution_revisions WHEN OLD.origin_kind!='legacy' BEGIN SELECT RAISE(ABORT,'immutable optimization revision origin'); END",
    ),
    "postgresql": (
        "CREATE FUNCTION omr_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='INSERT' THEN IF NEW.origin_kind='optimization_customer_v1' AND EXISTS (SELECT 1 FROM optimization_mandate_preparations p WHERE p.preparation_digest=NEW.origin_preparation_digest AND (p.mandate_id!=NEW.mandate_id OR p.mandate_revision!=NEW.revision OR p.workspace_id!=NEW.workspace_id OR p.provider_policy_digest!=NEW.digest)) THEN RAISE EXCEPTION 'optimization origin mismatch'; END IF; RETURN NEW; ELSIF TG_OP='UPDATE' THEN IF OLD.origin_kind!='legacy' OR NEW.origin_kind IS DISTINCT FROM OLD.origin_kind OR NEW.origin_preparation_digest IS DISTINCT FROM OLD.origin_preparation_digest THEN RAISE EXCEPTION 'immutable optimization revision origin'; END IF; RETURN NEW; ELSE IF OLD.origin_kind!='legacy' THEN RAISE EXCEPTION 'immutable optimization revision origin'; END IF; RETURN OLD; END IF; END; $$",
        "CREATE TRIGGER omr_guard BEFORE INSERT OR UPDATE OR DELETE ON provider_execution_revisions FOR EACH ROW EXECUTE FUNCTION omr_guard_fn()",
    ),
}
