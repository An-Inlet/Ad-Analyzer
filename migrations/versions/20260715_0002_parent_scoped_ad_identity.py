"""parent scoped ad identity

Revision ID: 20260715_0002
Revises: 20260714_0001
Create Date: 2026-07-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260715_0002"
down_revision: str | None = "20260714_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_ads_platform_external", "ads", type_="unique")
    op.create_unique_constraint(
        "uq_ads_ad_group_platform_external",
        "ads",
        ["ad_group_id", "platform", "external_ad_id"],
    )
    op.create_unique_constraint(
        "uq_ads_ad_set_platform_external",
        "ads",
        ["ad_set_id", "platform", "external_ad_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_ads_ad_set_platform_external", "ads", type_="unique")
    op.drop_constraint("uq_ads_ad_group_platform_external", "ads", type_="unique")
    op.create_unique_constraint(
        "uq_ads_platform_external",
        "ads",
        ["platform", "external_ad_id"],
    )
