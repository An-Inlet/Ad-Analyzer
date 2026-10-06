"""meta_child_metrics

Revision ID: 20261006_0029
Revises: 20261005_0028
Create Date: 2026-10-06 00:05:33.301077

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261006_0029"
down_revision: str | Sequence[str] | None = "20261005_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_ad_sets_id_campaign_platform", "ad_sets", ["id", "campaign_id", "platform"]
    )
    op.add_column("ads", sa.Column("creative_external_id", sa.String(length=128), nullable=True))
    op.add_column("ads", sa.Column("creative_name", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_ads_id_group_platform", "ads", ["id", "ad_group_id", "platform"]
    )
    op.create_unique_constraint("uq_ads_id_set_platform", "ads", ["id", "ad_set_id", "platform"])
    op.add_column("daily_metrics", sa.Column("ad_set_id", sa.Integer(), nullable=True))
    op.add_column("daily_metrics", sa.Column("ad_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_metric_ad_set",
        "daily_metrics",
        "ad_sets",
        ["ad_set_id", "campaign_id", "platform"],
        ["id", "campaign_id", "platform"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_metric_ad_group_ad",
        "daily_metrics",
        "ads",
        ["ad_id", "ad_group_id", "platform"],
        ["id", "ad_group_id", "platform"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_metric_ad_set_ad",
        "daily_metrics",
        "ads",
        ["ad_id", "ad_set_id", "platform"],
        ["id", "ad_set_id", "platform"],
        ondelete="CASCADE",
    )

    op.drop_constraint("ck_daily_metrics_entity_scope", "daily_metrics", type_="check")
    op.create_check_constraint(
        "ck_daily_metrics_entity_scope",
        "daily_metrics",
        (
            "((entity_type = 'campaign' AND entity_id = campaign_id AND ad_group_id IS NULL"
            " AND keyword_id IS NULL AND search_term_id IS NULL) OR (entity_type = 'ad_grou"
            "p' AND entity_id = ad_group_id AND ad_group_id IS NOT NULL AND keyword_id IS N"
            "ULL AND search_term_id IS NULL) OR (entity_type = 'keyword' AND entity_id = ke"
            "yword_id AND ad_group_id IS NOT NULL AND keyword_id IS NOT NULL AND search_ter"
            "m_id IS NULL) OR (entity_type = 'search_term' AND entity_id = search_term_id A"
            "ND ad_group_id IS NOT NULL AND keyword_id IS NULL AND search_term_id IS NOT NU"
            "LL)) AND ad_set_id IS NULL AND ad_id IS NULL OR (entity_type = 'ad_set' AND en"
            "tity_id = ad_set_id AND ad_set_id IS NOT NULL AND ad_id IS NULL AND ad_group_i"
            "d IS NULL AND keyword_id IS NULL AND search_term_id IS NULL) OR (entity_type ="
            " 'ad' AND entity_id = ad_id AND ad_id IS NOT NULL AND keyword_id IS NULL AND s"
            "earch_term_id IS NULL AND ((ad_set_id IS NOT NULL AND ad_group_id IS NULL) OR "
            "(ad_set_id IS NULL AND ad_group_id IS NOT NULL)))"
        ),
    )


def downgrade() -> None:
    # Destructive downgrade is tested only on an explicitly disposable database.
    op.execute("DELETE FROM daily_metrics WHERE entity_type IN ('ad_set', 'ad')")
    op.drop_constraint("ck_daily_metrics_entity_scope", "daily_metrics", type_="check")
    op.create_check_constraint(
        "ck_daily_metrics_entity_scope",
        "daily_metrics",
        (
            "(entity_type = 'campaign' AND entity_id = campaign_id AND ad_group_id IS NULL "
            "AND keyword_id IS NULL AND search_term_id IS NULL) OR (entity_type = 'ad_group"
            "' AND entity_id = ad_group_id AND ad_group_id IS NOT NULL AND keyword_id IS NU"
            "LL AND search_term_id IS NULL) OR (entity_type = 'keyword' AND entity_id = key"
            "word_id AND ad_group_id IS NOT NULL AND keyword_id IS NOT NULL AND search_term"
            "_id IS NULL) OR (entity_type = 'search_term' AND entity_id = search_term_id AN"
            "D ad_group_id IS NOT NULL AND keyword_id IS NULL AND search_term_id IS NOT NUL"
            "L)"
        ),
    )
    op.drop_constraint("fk_metric_ad_set_ad", "daily_metrics", type_="foreignkey")
    op.drop_constraint("fk_metric_ad_group_ad", "daily_metrics", type_="foreignkey")
    op.drop_constraint("fk_metric_ad_set", "daily_metrics", type_="foreignkey")
    op.drop_column("daily_metrics", "ad_id")
    op.drop_column("daily_metrics", "ad_set_id")
    op.drop_constraint("uq_ads_id_set_platform", "ads", type_="unique")
    op.drop_constraint("uq_ads_id_group_platform", "ads", type_="unique")
    op.drop_column("ads", "creative_name")
    op.drop_column("ads", "creative_external_id")
    op.drop_constraint("uq_ad_sets_id_campaign_platform", "ad_sets", type_="unique")
