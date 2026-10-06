"""publication_coordinator

Revision ID: 20261006_0040
Revises: 20261006_0039
Create Date: 2026-10-06 02:44:49.919565

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261006_0040"
down_revision: str | Sequence[str] | None = "20261006_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_mandate_action_scope", "mandate_actions", ["id", "workspace_id"]
    )
    op.create_table(
        "publication_plans",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.String(length=32), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.String(length=32), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activation_digest", sa.String(length=64), nullable=True),
        sa.Column("activation_approved_by", sa.String(length=32), nullable=True),
        sa.Column("request_key", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["action_id", "workspace_id"],
            ["mandate_actions.id", "mandate_actions.workspace_id"],
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_publication_plan_scope"),
        sa.UniqueConstraint("workspace_id", "digest", name="uq_publication_plan_digest"),
    )
    op.create_table(
        "publication_steps",
        sa.Column("plan_id", sa.String(length=32), nullable=False),
        sa.Column("step_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("fence", sa.String(length=32), nullable=True),
        sa.Column("request", sa.JSON(), nullable=True),
        sa.Column("receipt", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["plan_id", "workspace_id"],
            ["publication_plans.id", "publication_plans.workspace_id"],
        ),
        sa.PrimaryKeyConstraint("plan_id", "step_id"),
        sa.UniqueConstraint("plan_id", "step_id", "workspace_id", name="uq_publication_step_scope"),
    )
    op.create_table(
        "publication_receipts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("plan_id", sa.String(length=32), nullable=False),
        sa.Column("step_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("receipt", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id", "step_id", "workspace_id"],
            [
                "publication_steps.plan_id",
                "publication_steps.step_id",
                "publication_steps.workspace_id",
            ],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "step_id", "digest", name="uq_publication_receipt_digest"),
    )


def downgrade() -> None:
    op.drop_table("publication_receipts")
    op.drop_table("publication_steps")
    op.drop_table("publication_plans")
    op.drop_constraint("uq_mandate_action_scope", "mandate_actions", type_="unique")
