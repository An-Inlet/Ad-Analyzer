"""phase 2 read-only ads schema

Revision ID: 20260714_0001
Revises:
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

platform_enum = sa.Enum("google_ads", "meta_ads", name="advertising_platform", native_enum=False)
job_status_enum = sa.Enum(
    "pending", "running", "succeeded", "failed", name="job_run_status", native_enum=False
)


def upgrade() -> None:
    op.create_table(
        "advertising_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_account_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("time_zone", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "platform", name="uq_ad_accounts_id_platform"),
        sa.UniqueConstraint(
            "platform", "external_account_id", name="uq_ad_accounts_platform_external"
        ),
    )
    op.create_index("ix_ad_accounts_platform", "advertising_accounts", ["platform"])

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_campaign_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("channel_type", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "platform"],
            ["advertising_accounts.id", "advertising_accounts.platform"],
            name="fk_campaigns_account_platform",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "platform", name="uq_campaigns_id_platform"),
        sa.UniqueConstraint(
            "account_id",
            "platform",
            "external_campaign_id",
            name="uq_campaigns_account_platform_external",
        ),
    )
    op.create_index("ix_campaigns_account_platform", "campaigns", ["account_id", "platform"])

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("status", job_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["advertising_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_runs_platform_started", "job_runs", ["platform", "started_at"])

    op.create_table(
        "ad_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_ad_group_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id", "platform"],
            ["campaigns.id", "campaigns.platform"],
            name="fk_ad_groups_campaign_platform",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "platform",
            "external_ad_group_id",
            name="uq_ad_groups_campaign_platform_external",
        ),
        sa.UniqueConstraint("id", "platform", name="uq_ad_groups_id_platform"),
    )
    op.create_index("ix_ad_groups_campaign_platform", "ad_groups", ["campaign_id", "platform"])
    op.create_table(
        "ad_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_ad_set_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id", "platform"],
            ["campaigns.id", "campaigns.platform"],
            name="fk_ad_sets_campaign_platform",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "platform",
            "external_ad_set_id",
            name="uq_ad_sets_campaign_platform_external",
        ),
        sa.UniqueConstraint("id", "platform", name="uq_ad_sets_id_platform"),
    )
    op.create_index("ix_ad_sets_campaign_platform", "ad_sets", ["campaign_id", "platform"])
    op.create_table(
        "ads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_ad_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64)),
        sa.Column("ad_group_id", sa.Integer()),
        sa.Column("ad_set_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(ad_group_id IS NOT NULL AND ad_set_id IS NULL) OR "
            "(ad_group_id IS NULL AND ad_set_id IS NOT NULL)",
            name="ck_ads_exactly_one_parent",
        ),
        sa.ForeignKeyConstraint(
            ["ad_group_id", "platform"],
            ["ad_groups.id", "ad_groups.platform"],
            name="fk_ads_ad_group_platform",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ad_set_id", "platform"],
            ["ad_sets.id", "ad_sets.platform"],
            name="fk_ads_ad_set_platform",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("platform", "external_ad_id", name="uq_ads_platform_external"),
    )
    op.create_index("ix_ads_platform", "ads", ["platform"])
    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ad_group_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_keyword_id", sa.String(128), nullable=False),
        sa.Column("text", sa.String(512), nullable=False),
        sa.Column("match_type", sa.String(64)),
        sa.Column("status", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ad_group_id", "platform"],
            ["ad_groups.id", "ad_groups.platform"],
            name="fk_keywords_ad_group_platform",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "ad_group_id",
            "platform",
            "external_keyword_id",
            name="uq_keywords_ad_group_platform_external",
        ),
    )
    op.create_index("ix_keywords_ad_group_platform", "keywords", ["ad_group_id", "platform"])
    op.create_table(
        "search_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ad_group_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("term", sa.String(512), nullable=False),
        sa.Column("match_type", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ad_group_id", "platform"],
            ["ad_groups.id", "ad_groups.platform"],
            name="fk_search_terms_ad_group_platform",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "ad_group_id", "platform", "term", name="uq_search_terms_ad_group_platform_term"
        ),
    )
    op.create_index(
        "ix_search_terms_ad_group_platform", "search_terms", ["ad_group_id", "platform"]
    )
    op.create_table(
        "daily_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer()),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("conversions", sa.Numeric(18, 6), nullable=False),
        sa.Column("conversion_value_micros", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cost_micros >= 0", name="ck_daily_metrics_cost_nonnegative"),
        sa.ForeignKeyConstraint(
            ["campaign_id", "platform"],
            ["campaigns.id", "campaigns.platform"],
            name="fk_daily_metrics_campaign_platform",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "platform",
            "metric_date",
            "entity_type",
            "entity_id",
            name="uq_daily_metrics_platform_date_entity",
        ),
    )
    op.create_index("ix_daily_metrics_platform_date", "daily_metrics", ["platform", "metric_date"])
    op.create_table(
        "conversion_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_conversion_id", sa.String(128), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="SET NULL")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action_name", sa.String(255), nullable=False),
        sa.Column("value_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "platform", "external_conversion_id", name="uq_conversion_events_platform_external"
        ),
    )
    op.create_index(
        "ix_conversion_events_platform_occurred", "conversion_events", ["platform", "occurred_at"]
    )


def downgrade() -> None:
    for table in (
        "conversion_events",
        "daily_metrics",
        "search_terms",
        "keywords",
        "ads",
        "ad_sets",
        "ad_groups",
        "job_runs",
        "campaigns",
        "advertising_accounts",
    ):
        op.drop_table(table)
