"""add unified web analytics outcome data

Revision ID: 20260808_0010
Revises: 20260806_0009
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0010"
down_revision: str | None = "20260806_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "web_analytics_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_system", sa.String(16), nullable=False),
        sa.Column("external_event_id", sa.String(128), nullable=False),
        sa.Column("event_fingerprint", sa.String(64), nullable=False),
        sa.Column("event_name", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_pseudo_id_digest", sa.String(64), nullable=False),
        sa.Column("subject_id_digest", sa.String(64)),
        sa.Column("session_id_digest", sa.String(64), nullable=False),
        sa.Column("click_id_kind", sa.String(16)),
        sa.Column("click_id_digest", sa.String(64)),
        sa.Column("account_id", sa.Integer()),
        sa.Column("campaign_id", sa.Integer()),
        sa.Column("source", sa.String(64)),
        sa.Column("medium", sa.String(64)),
        sa.Column("device_category", sa.String(16), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("region_code", sa.String(64)),
        sa.Column("landing_page_path", sa.String(1024)),
        sa.Column("is_paid_touchpoint", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            name="fk_web_events_account_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            name="fk_web_events_campaign_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "source_system",
            "external_event_id",
            name="uq_web_events_workspace_source_external",
        ),
        sa.CheckConstraint(
            "source_system = 'ga4'",
            name="ck_web_events_source_system",
        ),
        sa.CheckConstraint(
            "event_name = lower(event_name) AND event_name NOT LIKE '% %'",
            name="ck_web_events_name_canonical",
        ),
        sa.CheckConstraint(
            "length(event_fingerprint) = 64",
            name="ck_web_events_fingerprint_length",
        ),
        sa.CheckConstraint(
            "length(user_pseudo_id_digest) = 64",
            name="ck_web_events_user_digest_length",
        ),
        sa.CheckConstraint(
            "length(session_id_digest) = 64",
            name="ck_web_events_session_digest_length",
        ),
        sa.CheckConstraint(
            "subject_id_digest IS NULL OR length(subject_id_digest) = 64",
            name="ck_web_events_subject_digest_length",
        ),
        sa.CheckConstraint(
            "(click_id_digest IS NULL AND click_id_kind IS NULL) OR "
            "(length(click_id_digest) = 64 AND click_id_kind IN ('gclid', 'gbraid', 'wbraid'))",
            name="ck_web_events_click_digest_pair",
        ),
        sa.CheckConstraint(
            "campaign_id IS NULL OR account_id IS NOT NULL",
            name="ck_web_events_campaign_requires_account",
        ),
        sa.CheckConstraint(
            "NOT is_paid_touchpoint OR "
            "(account_id IS NOT NULL AND campaign_id IS NOT NULL)",
            name="ck_web_events_paid_touchpoint_campaign",
        ),
        sa.CheckConstraint(
            "country_code IS NULL OR "
            "(country_code = upper(country_code) AND length(country_code) = 2)",
            name="ck_web_events_country_code",
        ),
    )
    op.create_index(
        "ix_web_events_workspace_occurred",
        "web_analytics_events",
        ["workspace_id", "occurred_at"],
    )
    op.create_index(
        "ix_web_events_workspace_subject_occurred",
        "web_analytics_events",
        ["workspace_id", "subject_id_digest", "occurred_at"],
    )
    op.create_index(
        "ix_web_events_workspace_click_occurred",
        "web_analytics_events",
        ["workspace_id", "click_id_digest", "occurred_at"],
    )
    op.create_index(
        "ix_web_events_workspace_campaign_occurred",
        "web_analytics_events",
        ["workspace_id", "campaign_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_events_workspace_campaign_occurred",
        table_name="web_analytics_events",
    )
    op.drop_index(
        "ix_web_events_workspace_click_occurred",
        table_name="web_analytics_events",
    )
    op.drop_index(
        "ix_web_events_workspace_subject_occurred",
        table_name="web_analytics_events",
    )
    op.drop_index(
        "ix_web_events_workspace_occurred",
        table_name="web_analytics_events",
    )
    op.drop_table("web_analytics_events")
