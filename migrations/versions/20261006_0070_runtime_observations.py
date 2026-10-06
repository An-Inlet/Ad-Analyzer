"""Bounded global runtime observations; no customer data or recovery authority."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import CheckConstraint

revision = "20261006_0070"
down_revision = "20261006_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_observations",
        sa.Column("component", sa.String(32), primary_key=True),
        sa.Column("slot", sa.String(24), primary_key=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_next_at", sa.DateTime(timezone=True)),
        sa.Column("process_epoch", sa.String(32)),
        sa.Column("epoch_started_at", sa.DateTime(timezone=True)),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        CheckConstraint(
            "component IN ('scheduler_loop','private_media_local','private_media_gcs')",
            name="ck_observation_component",
        ),
        CheckConstraint(
            "slot IN ('latest_start','latest_completion','latest_failure')",
            name="ck_observation_slot",
        ),
        CheckConstraint("occurrence_count BETWEEN 1 AND 2147483647", name="ck_observation_count"),
        CheckConstraint(
            "expected_next_at IS NULL OR expected_next_at >= observed_at",
            name="ck_observation_next",
        ),
        CheckConstraint(
            "(component = 'scheduler_loop' AND process_epoch IS NOT NULL AND epoch_started_at "
            "IS NOT NULL AND epoch_started_at <= observed_at) OR (component != "
            "'scheduler_loop' AND process_epoch IS NULL AND epoch_started_at IS NULL AND "
            "expected_next_at IS NULL)",
            name="ck_observation_epoch",
        ),
        CheckConstraint(
            "(component = 'scheduler_loop' AND ((slot = 'latest_start' AND outcome = "
            "'scheduler_cycle_started') OR (slot = 'latest_completion' AND outcome = "
            "'scheduler_cycle_completed') OR (slot = 'latest_failure' AND outcome IN "
            "('scheduler_cycle_failed','scheduler_stage_failed','scheduler_interrupted')))) "
            "OR (component != 'scheduler_loop' AND ((slot = 'latest_start' AND outcome IN "
            "('media_read_started','media_write_started')) OR (slot = 'latest_completion' AND "
            "outcome IN ('media_initialized','media_read_completed','media_write_completed')) "
            "OR (slot = 'latest_failure' AND outcome IN "
            "('media_init_failed','media_read_failed','media_write_failed'))))",
            name="ck_observation_outcome",
        ),
    )


def downgrade() -> None:
    op.drop_table("operational_observations")
