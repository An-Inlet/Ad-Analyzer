"""add campaign and ad-group analysis scope

Revision ID: 20260808_0012
Revises: 20260808_0011
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0012"
down_revision: str | None = "20260808_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_ad_groups_id_campaign",
        "ad_groups",
        ["id", "campaign_id"],
    )
    op.create_unique_constraint(
        "uq_ad_groups_id_campaign_platform",
        "ad_groups",
        ["id", "campaign_id", "platform"],
    )

    op.add_column("daily_metrics", sa.Column("ad_group_id", sa.Integer()))
    op.execute(
        sa.text(
            "UPDATE daily_metrics SET campaign_id = entity_id "
            "WHERE entity_type = 'campaign' AND campaign_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE daily_metrics AS metric SET campaign_id = ad_group.campaign_id "
            "FROM ad_groups AS ad_group "
            "WHERE metric.entity_type = 'ad_group' "
            "AND metric.entity_id = ad_group.id AND metric.campaign_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE daily_metrics SET ad_group_id = entity_id "
            "WHERE entity_type = 'ad_group'"
        )
    )
    op.create_foreign_key(
        "fk_daily_metrics_ad_group_campaign_platform",
        "daily_metrics",
        "ad_groups",
        ["ad_group_id", "campaign_id", "platform"],
        ["id", "campaign_id", "platform"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_daily_metrics_entity_scope",
        "daily_metrics",
        "(entity_type = 'campaign' AND entity_id = campaign_id AND ad_group_id IS NULL) OR "
        "(entity_type = 'ad_group' AND entity_id = ad_group_id AND ad_group_id IS NOT NULL)",
    )
    op.create_index(
        "ix_daily_metrics_ad_group_date",
        "daily_metrics",
        ["ad_group_id", "metric_date"],
    )
    op.alter_column("daily_metrics", "campaign_id", nullable=False)

    op.add_column("web_analytics_events", sa.Column("ad_group_id", sa.Integer()))
    op.create_foreign_key(
        "fk_web_events_ad_group_campaign",
        "web_analytics_events",
        "ad_groups",
        ["ad_group_id", "campaign_id"],
        ["id", "campaign_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_web_events_ad_group_requires_campaign",
        "web_analytics_events",
        "ad_group_id IS NULL OR campaign_id IS NOT NULL",
    )
    op.create_index(
        "ix_web_events_workspace_ad_group_occurred",
        "web_analytics_events",
        ["workspace_id", "ad_group_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_events_workspace_ad_group_occurred",
        table_name="web_analytics_events",
    )
    op.drop_constraint(
        "ck_web_events_ad_group_requires_campaign",
        "web_analytics_events",
        type_="check",
    )
    op.drop_constraint(
        "fk_web_events_ad_group_campaign",
        "web_analytics_events",
        type_="foreignkey",
    )
    op.drop_column("web_analytics_events", "ad_group_id")

    op.alter_column("daily_metrics", "campaign_id", nullable=True)
    op.drop_index("ix_daily_metrics_ad_group_date", table_name="daily_metrics")
    op.drop_constraint(
        "ck_daily_metrics_entity_scope",
        "daily_metrics",
        type_="check",
    )
    op.drop_constraint(
        "fk_daily_metrics_ad_group_campaign_platform",
        "daily_metrics",
        type_="foreignkey",
    )
    op.drop_column("daily_metrics", "ad_group_id")

    op.drop_constraint(
        "uq_ad_groups_id_campaign_platform",
        "ad_groups",
        type_="unique",
    )
    op.drop_constraint(
        "uq_ad_groups_id_campaign",
        "ad_groups",
        type_="unique",
    )
