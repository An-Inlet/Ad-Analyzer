"""Retain exclusive Meta external-account ownership after local disconnect."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0049"
down_revision = "20261006_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    duplicate = op.get_bind().scalar(
        sa.text(
            "SELECT 1 FROM advertising_accounts WHERE platform = 'meta_ads' "
            "GROUP BY external_account_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    )
    if duplicate:
        raise RuntimeError(
            "Meta account ownership conflicts require explicit reconciliation before migration; "
            "no data changed"
        )
    op.create_index(
        "uq_meta_external_account_owner",
        "advertising_accounts",
        ["external_account_id"],
        unique=True,
        postgresql_where=sa.text("platform = 'meta_ads'"),
        sqlite_where=sa.text("platform = 'meta_ads'"),
    )


def downgrade() -> None:
    op.drop_index("uq_meta_external_account_owner", table_name="advertising_accounts")
