# ruff: noqa: E501
"""Erasable reported-rule candidate dependencies; no financial authority."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0083"
down_revision = "20261007_0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reported_rule_candidate_dependencies",
        sa.Column("candidate_job_id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("comparison_id", sa.String(32), nullable=False),
        sa.Column("acquisition_job_id", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_job_id", "workspace_id"],
            ["optimization_candidate_jobs.id", "optimization_candidate_jobs.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["comparison_id", "workspace_id", "account_id", "campaign_id"],
            [
                "reported_action_comparisons.id",
                "reported_action_comparisons.workspace_id",
                "reported_action_comparisons.account_id",
                "reported_action_comparisons.campaign_id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_job_id", "workspace_id", "account_id", "campaign_id"],
            [
                "reported_feedback_jobs.id",
                "reported_feedback_jobs.workspace_id",
                "reported_feedback_jobs.account_id",
                "reported_feedback_jobs.campaign_id",
            ],
            ondelete="CASCADE",
        ),
    )
    for field in ("comparison_id", "acquisition_job_id"):
        op.create_index(
            "ix_reported_rule_candidate_dependencies_" + field,
            "reported_rule_candidate_dependencies",
            [field],
        )
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM reported_rule_candidate_dependencies)")
    ):
        raise RuntimeError("cannot discard retained reported rule dependencies")
    for name in (
        "reported_rule_dependency_owner",
        "reported_rule_dependency_immutable",
        "reported_rule_dependency_erase",
    ):
        suffix = (
            " ON reported_rule_candidate_dependencies"
            if connection.dialect.name == "postgresql"
            else ""
        )
        op.execute("DROP TRIGGER IF EXISTS " + name + suffix)
        if connection.dialect.name == "postgresql":
            op.execute("DROP FUNCTION IF EXISTS " + name + "_fn()")
    op.drop_table("reported_rule_candidate_dependencies")


# Frozen strings; never import evolving application trigger builders.
SQL = {
    "sqlite": (
        "CREATE TRIGGER reported_rule_dependency_owner BEFORE INSERT ON reported_rule_candidate_dependencies WHEN NOT EXISTS(SELECT 1 FROM reported_action_comparisons c JOIN reported_feedback_jobs r ON r.id=c.job_id JOIN optimization_candidate_jobs j ON j.id=NEW.candidate_job_id WHERE c.id=NEW.comparison_id AND c.job_id=NEW.acquisition_job_id AND c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id AND c.campaign_id=NEW.campaign_id AND j.workspace_id=c.workspace_id AND j.environment=c.environment AND j.actor_id=r.original_actor_id AND j.auth_session_digest=r.original_session_digest AND j.attempt_id=c.original_attempt_id) BEGIN SELECT RAISE(ABORT, 'owned reported rule lineage required'); END",
        "CREATE TRIGGER reported_rule_dependency_immutable BEFORE UPDATE ON reported_rule_candidate_dependencies BEGIN SELECT RAISE(ABORT, 'immutable reported rule lineage'); END",
        "CREATE TRIGGER reported_rule_dependency_erase AFTER DELETE ON reported_rule_candidate_dependencies BEGIN DELETE FROM optimization_candidate_jobs WHERE id=OLD.candidate_job_id AND workspace_id=OLD.workspace_id; END",
    ),
    "postgresql": (
        "CREATE FUNCTION reported_rule_dependency_owner_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NOT EXISTS(SELECT 1 FROM reported_action_comparisons c JOIN reported_feedback_jobs r ON r.id=c.job_id JOIN optimization_candidate_jobs j ON j.id=NEW.candidate_job_id WHERE c.id=NEW.comparison_id AND c.job_id=NEW.acquisition_job_id AND c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id AND c.campaign_id=NEW.campaign_id AND j.workspace_id=c.workspace_id AND j.environment=c.environment AND j.actor_id=r.original_actor_id AND j.auth_session_digest=r.original_session_digest AND j.attempt_id=c.original_attempt_id) THEN RAISE EXCEPTION 'owned reported rule lineage required'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER reported_rule_dependency_owner BEFORE INSERT ON reported_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION reported_rule_dependency_owner_fn()",
        "CREATE FUNCTION reported_rule_dependency_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable reported rule lineage'; END; $$",
        "CREATE TRIGGER reported_rule_dependency_immutable BEFORE UPDATE ON reported_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION reported_rule_dependency_immutable_fn()",
        "CREATE FUNCTION reported_rule_dependency_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN DELETE FROM optimization_candidate_jobs WHERE id=OLD.candidate_job_id AND workspace_id=OLD.workspace_id; RETURN NULL; END; $$",
        "CREATE TRIGGER reported_rule_dependency_erase AFTER DELETE ON reported_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION reported_rule_dependency_erase_fn()",
    ),
}
