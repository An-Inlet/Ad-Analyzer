# ruff: noqa: E501
"""Prospective owned planning aggregates and correction-retractable derived reports."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0075"
down_revision = "20261006_0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "initial_observations",
        sa.Column("environment", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("completion_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("generation", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("privacy_revision", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("cohort_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column(
            "retention_policy_digest", sa.String(length=64), primary_key=False, nullable=False
        ),
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("account_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("campaign_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("document", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("document_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["completion_id", "account_id", "workspace_id"],
            [
                "campaign_performance_completions.id",
                "campaign_performance_completions.account_id",
                "campaign_performance_completions.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            *["id", "workspace_id", "account_id", "campaign_id"],
            name="uq_initial_observation_scope",
        ),
        sa.UniqueConstraint(
            *["completion_id", "campaign_id", "environment"], name="uq_initial_capture"
        ),
    )
    op.create_index(
        "ix_initial_observations_cohort_digest", "initial_observations", ["cohort_digest"]
    )
    op.create_index("ix_initial_observations_expires_at", "initial_observations", ["expires_at"])
    op.create_table(
        "initial_calibration_runs",
        sa.Column("environment", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("objective", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("objective_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("policy_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("input_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("account_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("campaign_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("document", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("document_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            *["id", "workspace_id", "account_id", "campaign_id"],
            name="uq_initial_calibration_scope",
        ),
    )
    op.create_index(
        "ix_initial_calibration_runs_expires_at", "initial_calibration_runs", ["expires_at"]
    )
    op.create_table(
        "initial_calibration_dependencies",
        sa.Column("calibration_id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("observation_id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("account_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("campaign_id", sa.Integer(), primary_key=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_observations.id",
                "initial_observations.workspace_id",
                "initial_observations.account_id",
                "initial_observations.campaign_id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["calibration_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_calibration_runs.id",
                "initial_calibration_runs.workspace_id",
                "initial_calibration_runs.account_id",
                "initial_calibration_runs.campaign_id",
            ],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "initial_plan_previews",
        sa.Column("calibration_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("observation_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("intent", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("original_actor_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column(
            "original_session_digest", sa.String(length=64), primary_key=False, nullable=False
        ),
        sa.Column("goal_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("source_generation", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("privacy_revision", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("completion_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("native_state_digest", sa.String(length=64), primary_key=False, nullable=True),
        sa.Column("mandate_digest", sa.String(length=64), primary_key=False, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("account_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("campaign_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("document", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("document_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_observations.id",
                "initial_observations.workspace_id",
                "initial_observations.account_id",
                "initial_observations.campaign_id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["calibration_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_calibration_runs.id",
                "initial_calibration_runs.workspace_id",
                "initial_calibration_runs.account_id",
                "initial_calibration_runs.campaign_id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            *["id", "workspace_id", "account_id", "campaign_id"], name="uq_initial_preview_scope"
        ),
    )
    op.create_index("ix_initial_plan_previews_expires_at", "initial_plan_previews", ["expires_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION initial_observations_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial planning evidence'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_observations_immutable BEFORE UPDATE ON initial_observations FOR EACH ROW EXECUTE FUNCTION initial_observations_immutable_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_observations_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_observations_guard BEFORE DELETE ON initial_observations FOR EACH ROW EXECUTE FUNCTION initial_observations_guard_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_observations_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND OLD.expires_at > clock_timestamp(); RETURN NULL; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_observations_erase AFTER DELETE ON initial_observations FOR EACH ROW EXECUTE FUNCTION initial_observations_erase_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_calibration_runs_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial planning evidence'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_runs_immutable BEFORE UPDATE ON initial_calibration_runs FOR EACH ROW EXECUTE FUNCTION initial_calibration_runs_immutable_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_calibration_runs_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_runs_guard BEFORE DELETE ON initial_calibration_runs FOR EACH ROW EXECUTE FUNCTION initial_calibration_runs_guard_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_calibration_runs_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND OLD.expires_at > clock_timestamp(); RETURN NULL; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_runs_erase AFTER DELETE ON initial_calibration_runs FOR EACH ROW EXECUTE FUNCTION initial_calibration_runs_erase_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_calibration_dependencies_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial planning evidence'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_dependencies_immutable BEFORE UPDATE ON initial_calibration_dependencies FOR EACH ROW EXECUTE FUNCTION initial_calibration_dependencies_immutable_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_calibration_dependencies_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_dependencies_guard BEFORE DELETE ON initial_calibration_dependencies FOR EACH ROW EXECUTE FUNCTION initial_calibration_dependencies_guard_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_calibration_dependencies_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN DELETE FROM initial_calibration_runs WHERE id=OLD.calibration_id AND workspace_id=OLD.workspace_id; RETURN NULL; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_dependencies_erase AFTER DELETE ON initial_calibration_dependencies FOR EACH ROW EXECUTE FUNCTION initial_calibration_dependencies_erase_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_plan_previews_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial planning evidence'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_plan_previews_immutable BEFORE UPDATE ON initial_plan_previews FOR EACH ROW EXECUTE FUNCTION initial_plan_previews_immutable_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_plan_previews_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_plan_previews_guard BEFORE DELETE ON initial_plan_previews FOR EACH ROW EXECUTE FUNCTION initial_plan_previews_guard_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_plan_previews_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND OLD.expires_at > clock_timestamp(); RETURN NULL; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_plan_previews_erase AFTER DELETE ON initial_plan_previews FOR EACH ROW EXECUTE FUNCTION initial_plan_previews_erase_fn()"
        )
    else:
        op.execute(
            "CREATE TRIGGER initial_observations_immutable BEFORE UPDATE ON initial_observations BEGIN SELECT RAISE(ABORT, 'immutable initial planning evidence'); END"
        )
        op.execute(
            "CREATE TRIGGER initial_observations_erase AFTER DELETE ON initial_observations BEGIN UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND julianday(OLD.expires_at) > julianday('now'); END"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_runs_immutable BEFORE UPDATE ON initial_calibration_runs BEGIN SELECT RAISE(ABORT, 'immutable initial planning evidence'); END"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_runs_erase AFTER DELETE ON initial_calibration_runs BEGIN UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND julianday(OLD.expires_at) > julianday('now'); END"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_dependencies_immutable BEFORE UPDATE ON initial_calibration_dependencies BEGIN SELECT RAISE(ABORT, 'immutable initial planning evidence'); END"
        )
        op.execute(
            "CREATE TRIGGER initial_calibration_dependencies_erase AFTER DELETE ON initial_calibration_dependencies BEGIN DELETE FROM initial_calibration_runs WHERE id=OLD.calibration_id AND workspace_id=OLD.workspace_id; END"
        )
        op.execute(
            "CREATE TRIGGER initial_plan_previews_immutable BEFORE UPDATE ON initial_plan_previews BEGIN SELECT RAISE(ABORT, 'immutable initial planning evidence'); END"
        )
        op.execute(
            "CREATE TRIGGER initial_plan_previews_erase AFTER DELETE ON initial_plan_previews BEGIN UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND julianday(OLD.expires_at) > julianday('now'); END"
        )


def downgrade() -> None:
    op.drop_table("initial_plan_previews")
    op.drop_table("initial_calibration_dependencies")
    op.drop_table("initial_calibration_runs")
    op.drop_table("initial_observations")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION initial_observations_immutable_fn()")
        op.execute("DROP FUNCTION initial_observations_guard_fn()")
        op.execute("DROP FUNCTION initial_observations_erase_fn()")
        op.execute("DROP FUNCTION initial_calibration_runs_immutable_fn()")
        op.execute("DROP FUNCTION initial_calibration_runs_guard_fn()")
        op.execute("DROP FUNCTION initial_calibration_runs_erase_fn()")
        op.execute("DROP FUNCTION initial_calibration_dependencies_immutable_fn()")
        op.execute("DROP FUNCTION initial_calibration_dependencies_guard_fn()")
        op.execute("DROP FUNCTION initial_calibration_dependencies_erase_fn()")
        op.execute("DROP FUNCTION initial_plan_previews_immutable_fn()")
        op.execute("DROP FUNCTION initial_plan_previews_guard_fn()")
        op.execute("DROP FUNCTION initial_plan_previews_erase_fn()")
