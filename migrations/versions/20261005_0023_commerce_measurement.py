"""commerce_measurement

Revision ID: 20261005_0023
Revises: 20261005_0022
Create Date: 2026-10-05 16:07:02.564215

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261005_0023"
down_revision: str | Sequence[str] | None = "20261005_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "commerce_suppressions",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("shop_key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("object_key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "shop_key", "kind", "object_key"),
    )
    op.create_table(
        "commerce_stores",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("shop_key", sa.String(length=64), nullable=False),
        sa.Column("shop_domain", sa.String(length=253), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("time_zone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("covered_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.String(length=4096), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_commerce_store_owner"),
        sa.UniqueConstraint("workspace_id", "shop_key", name="uq_commerce_store_identity"),
    )
    op.create_table(
        "commerce_daily_revisions",
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("time_zone", sa.String(length=64), nullable=False),
        sa.Column("net_micros", sa.BigInteger(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["commerce_stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("store_id", "day", "revision"),
    )
    op.create_table(
        "commerce_orders",
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("order_key", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("privacy_key", sa.String(length=64), nullable=False),
        sa.Column("customer_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("quality", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("store_id", "order_key"),
    )
    op.create_table(
        "commerce_snapshots",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["commerce_stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "commerce_entries",
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("entry_key", sa.String(length=64), nullable=False),
        sa.Column("order_key", sa.String(length=64), nullable=False),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("net_micros", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id", "order_key"],
            ["commerce_orders.store_id", "commerce_orders.order_key"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("store_id", "entry_key"),
    )
    op.create_index(
        op.f("ix_commerce_entries_happened_at"), "commerce_entries", ["happened_at"], unique=False
    )
    op.create_table(
        "commerce_source_links",
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("order_key", sa.String(length=64), nullable=False),
        sa.Column("evidence", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id", "order_key"],
            ["commerce_orders.store_id", "commerce_orders.order_key"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connection_id", "source_key"),
    )
    with op.batch_alter_table("shopify_connections") as batch:
        batch.add_column(sa.Column("commerce_store_id", sa.String(length=32), nullable=True))
        batch.create_foreign_key(
            "fk_shopify_commerce_store",
            "commerce_stores",
            ["commerce_store_id", "workspace_id"],
            ["id", "workspace_id"],
            ondelete="RESTRICT",
        )
    op.add_column(
        "shopify_privacy_requests",
        sa.Column("commerce_keys", sa.JSON(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("shopify_privacy_requests", "commerce_keys")
    with op.batch_alter_table("shopify_connections") as batch:
        batch.drop_constraint("fk_shopify_commerce_store", type_="foreignkey")
        batch.drop_column("commerce_store_id")
    op.drop_table("commerce_source_links")
    op.drop_table("commerce_entries")
    op.drop_table("commerce_snapshots")
    op.drop_table("commerce_orders")
    op.drop_table("commerce_daily_revisions")
    op.drop_table("commerce_stores")
    op.drop_table("commerce_suppressions")
