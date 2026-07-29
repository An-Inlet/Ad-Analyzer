"""private CRM gateway tables

Revision ID: 20260729_0007
Revises: 20260720_0006
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0007"
down_revision: str | None = "20260720_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "crm_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("secret_manager_reference", sa.String(512), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_crm_connections_status", "crm_connections", ["status"])
    op.create_table(
        "crm_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "connection_id",
            sa.Integer(),
            sa.ForeignKey("crm_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("crm_lead_id", sa.String(128), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("processing_status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint(
            "connection_id", "external_event_id", name="uq_crm_events_source_event"
        ),
    )
    op.create_index(
        "ix_crm_events_status_created", "crm_events", ["processing_status", "created_at"]
    )
    op.create_index("ix_crm_events_lead", "crm_events", ["crm_lead_id"])
    op.create_table(
        "lead_attribution",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "connection_id",
            sa.Integer(),
            sa.ForeignKey("crm_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("crm_lead_id", sa.String(128), nullable=False),
        sa.Column("crm_opportunity_id", sa.String(128)),
        sa.Column("lifecycle_state", sa.String(64), nullable=False),
        sa.Column("lifecycle_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("attribution_data", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("connection_id", "crm_lead_id", name="uq_lead_attribution_source_lead"),
    )
    op.create_index("ix_lead_attribution_lifecycle", "lead_attribution", ["lifecycle_state"])
    op.create_table(
        "crm_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "connection_id",
            sa.Integer(),
            sa.ForeignKey("crm_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_crm_sync_runs_status_started", "crm_sync_runs", ["status", "started_at"])


def downgrade() -> None:
    op.drop_table("crm_sync_runs")
    op.drop_table("lead_attribution")
    op.drop_table("crm_events")
    op.drop_table("crm_connections")
