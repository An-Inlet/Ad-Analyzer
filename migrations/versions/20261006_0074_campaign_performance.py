"""Current campaign reporting completion commitments; no historical metric snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0074"
down_revision = "20261006_0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_performance_completions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("source_connection_ref", sa.String(32), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("privacy_revision", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column("query_version", sa.String(100), nullable=False),
        sa.Column("semantics", sa.String(40), nullable=False),
        sa.Column("selected_event", sa.String(64)),
        sa.Column("reporting_basis", sa.String(64), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "id", "account_id", "workspace_id", name="uq_performance_completion_scope"
        ),
    )
    op.create_table(
        "campaign_performance_current",
        sa.Column("account_id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("completion_id", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["completion_id", "account_id", "workspace_id"],
            [
                "campaign_performance_completions.id",
                "campaign_performance_completions.account_id",
                "campaign_performance_completions.workspace_id",
            ],
            ondelete="CASCADE",
        ),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION reject_performance_completion_update() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'immutable campaign performance completion';
        END; $$ LANGUAGE plpgsql""")
        op.execute("""CREATE TRIGGER performance_completion_immutable BEFORE UPDATE ON
        campaign_performance_completions FOR EACH ROW
        EXECUTE FUNCTION reject_performance_completion_update()""")
    else:
        op.execute("""CREATE TRIGGER performance_completion_immutable BEFORE UPDATE ON
        campaign_performance_completions BEGIN
        SELECT RAISE(ABORT, 'immutable campaign performance completion'); END""")


def downgrade() -> None:
    op.drop_table("campaign_performance_current")
    op.drop_table("campaign_performance_completions")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION reject_performance_completion_update()")
