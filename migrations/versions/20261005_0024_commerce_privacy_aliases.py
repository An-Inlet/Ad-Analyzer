"""Preserve verified Shopify domains for delayed privacy delivery after reconnect."""

import sqlalchemy as sa
from alembic import op

revision = "20261005_0024"
down_revision = "20261005_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shopify_orders", sa.Column("commerce_order_key", sa.String(64), nullable=True))
    op.execute(
        sa.text("""UPDATE shopify_orders SET commerce_order_key = (
        SELECT commerce_orders.order_key FROM commerce_orders
        WHERE commerce_orders.workspace_id = shopify_orders.workspace_id
          AND commerce_orders.privacy_key = shopify_orders.order_key LIMIT 1
    )""")
    )
    aliases = op.create_table(
        "commerce_shop_aliases",
        sa.Column("shop_domain", sa.String(253), nullable=False),
        sa.Column("store_id", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["commerce_stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("shop_domain", "store_id"),
    )
    stores = sa.table("commerce_stores", sa.column("id"), sa.column("shop_domain"))
    op.get_bind().execute(
        aliases.insert().from_select(
            ["shop_domain", "store_id"],
            sa.select(stores.c.shop_domain, stores.c.id),
        )
    )


def downgrade() -> None:
    op.drop_table("commerce_shop_aliases")
    op.drop_column("shopify_orders", "commerce_order_key")
