"""Preserve erasure identity before commerce enablement and expose pending resolution."""

import sqlalchemy as sa
from alembic import op

revision = "20261005_0025"
down_revision = "20261005_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopify_privacy_identities",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("shop_domain", sa.String(253), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("object_key", sa.String(64), nullable=False),
        sa.Column("pending_legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "shop_domain", "kind", "object_key"),
    )
    op.execute(
        sa.text("""INSERT INTO shopify_privacy_identities
        (workspace_id, shop_domain, kind, object_key, pending_legacy)
        SELECT workspace_id, shop_domain, 'scope', :scope, false FROM shopify_connections
    """).bindparams(scope="0" * 64)
    )
    op.execute(
        sa.text("""INSERT INTO shopify_privacy_identities
        (workspace_id, shop_domain, kind, object_key, pending_legacy)
        SELECT DISTINCT c.workspace_id, c.shop_domain, 'order', t.order_key, false
        FROM shopify_tombstones t JOIN shopify_connections c ON c.id=t.connection_id
    """)
    )
    op.add_column(
        "shopify_privacy_requests", sa.Column("customer_key", sa.String(64), nullable=True)
    )
    op.add_column(
        "shopify_privacy_requests",
        sa.Column("resolution_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Older requests did not retain customer identity. Do not assert a complete
    # export while legacy facts on that connection still lack a customer bridge.
    op.execute(
        sa.text("""UPDATE shopify_privacy_requests SET resolution_pending=true
        WHERE completed_at IS NULL AND EXISTS (
            SELECT 1 FROM shopify_orders o
            JOIN shopify_connections c ON c.id=o.connection_id
            LEFT JOIN commerce_orders co ON co.store_id=c.commerce_store_id
                AND co.order_key=o.commerce_order_key
            WHERE o.connection_id=shopify_privacy_requests.connection_id
                AND (co.order_key IS NULL OR co.customer_key IS NULL)
        )""")
    )


def downgrade() -> None:
    op.drop_column("shopify_privacy_requests", "resolution_pending")
    op.drop_column("shopify_privacy_requests", "customer_key")
    op.drop_table("shopify_privacy_identities")
