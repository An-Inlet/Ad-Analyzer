"""Bind customer Meta grants to explicit single-use authorization phases."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0045"
down_revision = "20261006_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meta_oauth_states",
        sa.Column("phase", sa.String(16), server_default="pending", nullable=False),
    )
    op.add_column(
        "meta_pending_grants", sa.Column("oauth_state_digest", sa.String(64), nullable=True)
    )

    with op.batch_alter_table("meta_oauth_states") as batch:
        batch.create_check_constraint(
            "ck_meta_oauth_phase", "phase IN ('pending','exchanging','failed')"
        )


def downgrade() -> None:
    with op.batch_alter_table("meta_oauth_states") as batch:
        batch.drop_constraint("ck_meta_oauth_phase", type_="check")
    op.drop_column("meta_pending_grants", "oauth_state_digest")
    op.drop_column("meta_oauth_states", "phase")
