"""add keyword and search-term metric scope

Revision ID: 20260815_0013
Revises: 20260808_0012
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0013"
down_revision: str | None = "20260808_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ENTITY_SCOPE_CHECK = (
    "(entity_type = 'campaign' AND entity_id = campaign_id "
    "AND ad_group_id IS NULL AND keyword_id IS NULL AND search_term_id IS NULL) OR "
    "(entity_type = 'ad_group' AND entity_id = ad_group_id "
    "AND ad_group_id IS NOT NULL AND keyword_id IS NULL AND search_term_id IS NULL) OR "
    "(entity_type = 'keyword' AND entity_id = keyword_id "
    "AND ad_group_id IS NOT NULL AND keyword_id IS NOT NULL "
    "AND search_term_id IS NULL) OR "
    "(entity_type = 'search_term' AND entity_id = search_term_id "
    "AND ad_group_id IS NOT NULL AND keyword_id IS NULL "
    "AND search_term_id IS NOT NULL)"
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_keywords_id_ad_group_platform",
        "keywords",
        ["id", "ad_group_id", "platform"],
    )
    op.create_unique_constraint(
        "uq_search_terms_id_ad_group_platform",
        "search_terms",
        ["id", "ad_group_id", "platform"],
    )

    op.add_column("daily_metrics", sa.Column("keyword_id", sa.Integer()))
    op.add_column("daily_metrics", sa.Column("search_term_id", sa.Integer()))
    op.create_foreign_key(
        "fk_daily_metrics_keyword_ad_group_platform",
        "daily_metrics",
        "keywords",
        ["keyword_id", "ad_group_id", "platform"],
        ["id", "ad_group_id", "platform"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_daily_metrics_search_term_ad_group_platform",
        "daily_metrics",
        "search_terms",
        ["search_term_id", "ad_group_id", "platform"],
        ["id", "ad_group_id", "platform"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "ck_daily_metrics_entity_scope",
        "daily_metrics",
        type_="check",
    )
    op.create_check_constraint(
        "ck_daily_metrics_entity_scope",
        "daily_metrics",
        _ENTITY_SCOPE_CHECK,
    )
    op.create_index(
        "ix_daily_metrics_keyword_date",
        "daily_metrics",
        ["keyword_id", "metric_date"],
    )
    op.create_index(
        "ix_daily_metrics_search_term_date",
        "daily_metrics",
        ["search_term_id", "metric_date"],
    )
    op.create_index(
        "ix_daily_metrics_entity_type_entity_date",
        "daily_metrics",
        ["entity_type", "entity_id", "metric_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_metrics_entity_type_entity_date",
        table_name="daily_metrics",
    )
    op.drop_index("ix_daily_metrics_search_term_date", table_name="daily_metrics")
    op.drop_index("ix_daily_metrics_keyword_date", table_name="daily_metrics")
    op.drop_constraint(
        "ck_daily_metrics_entity_scope",
        "daily_metrics",
        type_="check",
    )
    op.execute(
        sa.text(
            "DELETE FROM daily_metrics WHERE entity_type IN ('keyword', 'search_term')"
        )
    )
    op.drop_constraint(
        "fk_daily_metrics_search_term_ad_group_platform",
        "daily_metrics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_daily_metrics_keyword_ad_group_platform",
        "daily_metrics",
        type_="foreignkey",
    )
    op.drop_column("daily_metrics", "search_term_id")
    op.drop_column("daily_metrics", "keyword_id")
    op.create_check_constraint(
        "ck_daily_metrics_entity_scope",
        "daily_metrics",
        "(entity_type = 'campaign' AND entity_id = campaign_id AND ad_group_id IS NULL) OR "
        "(entity_type = 'ad_group' AND entity_id = ad_group_id AND ad_group_id IS NOT NULL)",
    )

    op.drop_constraint(
        "uq_search_terms_id_ad_group_platform",
        "search_terms",
        type_="unique",
    )
    op.drop_constraint(
        "uq_keywords_id_ad_group_platform",
        "keywords",
        type_="unique",
    )
