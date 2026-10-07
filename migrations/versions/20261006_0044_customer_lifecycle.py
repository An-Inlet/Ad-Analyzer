"""Workspace lifecycle receipts; disposition deliberately unset, no deletion actions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0044"
down_revision: str | Sequence[str] | None = "20261006_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_lifecycle_requests",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            sa.String(32),
            sa.ForeignKey("customer_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("key_digest", sa.String(64), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("fence", sa.String(32), nullable=False),
        sa.Column("disposition_policy", sa.String(64), nullable=True),
        sa.Column("blockers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_lifecycle_request_scope"),
        sa.UniqueConstraint(
            "workspace_id",
            "requested_by",
            "operation",
            "key_digest",
            name="uq_lifecycle_request_replay",
        ),
        sa.CheckConstraint("operation IN ('export','close')", name="ck_lifecycle_operation"),
        sa.CheckConstraint("revision > 0", name="ck_lifecycle_revision"),
        sa.CheckConstraint("disposition_policy IS NULL", name="ck_lifecycle_policy_unset_v1"),
    )
    op.create_table(
        "customer_lifecycle_steps",
        sa.Column("request_id", sa.String(32), primary_key=True),
        sa.Column("step_key", sa.String(48), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("request_revision", sa.Integer(), nullable=False),
        sa.Column("fence", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_digest", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id", "workspace_id"],
            ["customer_lifecycle_requests.id", "customer_lifecycle_requests.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND request_revision > 0", name="ck_lifecycle_step_attempt"
        ),
    )


def downgrade() -> None:
    op.drop_table("customer_lifecycle_steps")
    op.drop_table("customer_lifecycle_requests")
