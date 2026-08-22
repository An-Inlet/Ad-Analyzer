"""add audited master and workspace automation controls

Revision ID: 20260820_0015
Revises: 20260816_0014
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0015"
down_revision: str | None = "20260816_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_automation_controls",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "workspace_automation_controls",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "key"),
    )
    op.create_index(
        "ix_workspace_automation_controls_key",
        "workspace_automation_controls",
        ["key"],
    )
    op.create_table(
        "automation_control_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("workspace_id", sa.Integer()),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("actor", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(scope = 'platform' AND workspace_id IS NULL) OR "
            "(scope = 'workspace' AND workspace_id IS NOT NULL)",
            name="ck_automation_control_audits_scope",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_automation_control_audits_scope_created",
        "automation_control_audits",
        ["scope", "workspace_id", "created_at"],
    )
    platform_controls = sa.table(
        "platform_automation_controls",
        sa.column("key", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("updated_by", sa.String()),
    )
    op.bulk_insert(
        platform_controls,
        [
            {
                "key": "github_hourly_production_audit",
                "enabled": False,
                "updated_by": "migration",
            },
            {"key": "post_sync_analysis", "enabled": True, "updated_by": "migration"},
            {"key": "nightly_analysis", "enabled": True, "updated_by": "migration"},
            {"key": "weekly_analysis", "enabled": True, "updated_by": "migration"},
            {
                "key": "automatic_recommendation_drafts",
                "enabled": True,
                "updated_by": "migration",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_automation_control_audits_scope_created",
        table_name="automation_control_audits",
    )
    op.drop_table("automation_control_audits")
    op.drop_index(
        "ix_workspace_automation_controls_key",
        table_name="workspace_automation_controls",
    )
    op.drop_table("workspace_automation_controls")
    op.drop_table("platform_automation_controls")
