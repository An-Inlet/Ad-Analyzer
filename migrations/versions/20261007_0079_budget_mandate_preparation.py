# ruff: noqa: E501
"""Retain exact server policy origin for conditional customer mandate consent."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0079"
down_revision = "20261007_0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "initial_budget_mandate_preparations",
        sa.Column("mandate_id", sa.String(32), primary_key=True),
        sa.Column("mandate_revision", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mandate_id", "mandate_revision", "workspace_id"],
            [
                "provider_execution_revisions.mandate_id",
                "provider_execution_revisions.revision",
                "provider_execution_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
            name="fk_initial_budget_preparation_revision",
        ),
        sa.CheckConstraint("mandate_revision > 0", name="ck_initial_budget_preparation_revision"),
    )
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM initial_budget_mandate_preparations)")
    ):
        raise RuntimeError("cannot discard retained mandate preparation authority")
    op.drop_table("initial_budget_mandate_preparations")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION ibmp_guard_fn()")


# Frozen statements; historical migration never imports current application logic.
SQL = {
    "sqlite": (
        "CREATE TRIGGER ibmp_insert BEFORE INSERT ON initial_budget_mandate_preparations WHEN NOT EXISTS (SELECT 1 FROM provider_execution_revisions r WHERE r.mandate_id=NEW.mandate_id AND r.revision=NEW.mandate_revision AND r.workspace_id=NEW.workspace_id AND r.digest=NEW.policy_digest) BEGIN SELECT RAISE(ABORT,'mandate preparation policy mismatch'); END",
        "CREATE TRIGGER ibmp_update BEFORE UPDATE ON initial_budget_mandate_preparations BEGIN SELECT RAISE(ABORT,'immutable mandate preparation'); END",
        "CREATE TRIGGER ibmp_delete BEFORE DELETE ON initial_budget_mandate_preparations BEGIN SELECT RAISE(ABORT,'immutable mandate preparation'); END",
    ),
    "postgresql": (
        "CREATE FUNCTION ibmp_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP != 'INSERT' THEN RAISE EXCEPTION 'immutable mandate preparation'; END IF; IF NOT EXISTS (SELECT 1 FROM provider_execution_revisions r WHERE r.mandate_id=NEW.mandate_id AND r.revision=NEW.mandate_revision AND r.workspace_id=NEW.workspace_id AND r.digest=NEW.policy_digest) THEN RAISE EXCEPTION 'mandate preparation policy mismatch'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER ibmp_guard BEFORE INSERT OR UPDATE OR DELETE ON initial_budget_mandate_preparations FOR EACH ROW EXECUTE FUNCTION ibmp_guard_fn()",
    ),
}
