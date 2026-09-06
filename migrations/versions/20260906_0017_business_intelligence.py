"""Add versioned workspace business context and its audit history."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0017"
down_revision = "20260821_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("decision_brief", sa.JSON(), nullable=True))
    op.create_table(
        "intelligence_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("record_key", sa.String(96), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "workspace_id", "kind", "record_key", name="uq_intelligence_record_key"
        ),
        sa.UniqueConstraint("id", "workspace_id", name="uq_intelligence_record_workspace"),
        sa.CheckConstraint("version > 0", name="ck_intelligence_record_version"),
        sa.CheckConstraint(
            "kind IN ('strategy','event','creative','experiment','cost','change','decision')",
            name="ck_intelligence_record_kind",
        ),
    )
    op.create_index(
        "ix_intelligence_records_workspace_kind",
        "intelligence_records",
        ["workspace_id", "kind", "updated_at"],
    )
    op.create_table(
        "intelligence_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("actor_role", sa.String(24), nullable=False),
        sa.Column("before_data", sa.JSON()),
        sa.Column("after_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_id", "workspace_id"],
            ["intelligence_records.id", "intelligence_records.workspace_id"],
            name="fk_intelligence_revision_workspace",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("record_id", "version", name="uq_intelligence_revision_version"),
    )
    op.create_index(
        "ix_intelligence_revisions_workspace_time",
        "intelligence_revisions",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_intelligence_revisions_workspace_time", table_name="intelligence_revisions")
    op.drop_table("intelligence_revisions")
    op.drop_index("ix_intelligence_records_workspace_kind", table_name="intelligence_records")
    op.drop_table("intelligence_records")
    op.drop_column("analysis_runs", "decision_brief")
