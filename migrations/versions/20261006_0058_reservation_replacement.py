"""Retained exposure replacement audit; never erase inherited obligations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0058"
down_revision: str | Sequence[str] | None = "20261006_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("provider_exposure_reservations") as batch:
        batch.drop_constraint("ck_provider_reservation_bounds", type_="check")
        batch.create_check_constraint(
            "ck_provider_reservation_bounds",
            "amount_micros >= 0 AND state IN ('held','settled','superseded')",
        )
    op.create_table(
        "provider_reservation_replacements",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.String(32), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("budget_owner_key", sa.String(256), nullable=False),
        sa.Column("predecessor_id", sa.String(32), nullable=False),
        sa.Column("successor_id", sa.String(32), nullable=False),
        sa.Column("successor_run_id", sa.String(32), nullable=False),
        sa.Column("review_id", sa.String(32), nullable=False),
        sa.Column("old_amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("new_amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column(
            "actor",
            sa.String(),
            sa.ForeignKey("customer_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_provider_replacement_scope"),
        sa.UniqueConstraint("predecessor_id", name="uq_provider_replacement_predecessor"),
        sa.UniqueConstraint("successor_id", name="uq_provider_replacement_successor"),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "workspace_id"],
            ["provider_exposure_reservations.id", "provider_exposure_reservations.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["successor_id", "workspace_id"],
            ["provider_exposure_reservations.id", "provider_exposure_reservations.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["successor_run_id", "workspace_id"],
            ["provider_execution_runs.id", "provider_execution_runs.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ledger_id", "workspace_id", "environment"],
            [
                "provider_period_ledgers.id",
                "provider_period_ledgers.workspace_id",
                "provider_period_ledgers.environment",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "predecessor_id <> successor_id AND old_amount_micros >= 0 AND new_amount_micros >= 0",
            name="ck_provider_replacement_bounds",
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT count(*) FROM provider_reservation_replacements")
    ) or connection.scalar(
        sa.text("SELECT count(*) FROM provider_exposure_reservations WHERE state = 'superseded'")
    ):
        raise RuntimeError("replacement audit and inherited obligations cannot be discarded")
    op.drop_table("provider_reservation_replacements")
    with op.batch_alter_table("provider_exposure_reservations") as batch:
        batch.drop_constraint("ck_provider_reservation_bounds", type_="check")
        batch.create_check_constraint(
            "ck_provider_reservation_bounds", "amount_micros >= 0 AND state IN ('held','settled')"
        )
