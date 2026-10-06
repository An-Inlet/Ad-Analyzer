"""Persist original scoped commercial offers and qualified subscription snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0063"
down_revision = "20261006_0061"
branch_labels = None
depends_on = None

OWNER = ["workspace_id", "provider", "environment", "merchant_account_id"]
POINTERS = ["checkout_offer_binding_id", "subscription_offer_binding_id"]


def upgrade() -> None:
    op.create_table(
        "customer_billing_offer_bindings",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("merchant_account_id", sa.String(160), nullable=False),
        sa.Column("checkout_key", sa.String(64), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("profile_digest", sa.String(64), nullable=False),
        sa.Column("binding_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "environment",
            "merchant_account_id",
            "checkout_key",
            name="uq_billing_offer_request",
        ),
        sa.UniqueConstraint("id", *OWNER, name="uq_billing_offer_owner"),
    )
    with op.batch_alter_table("customer_workspace_billing") as batch:
        for field in POINTERS:
            batch.add_column(sa.Column(field, sa.String(32)))
            batch.create_foreign_key(
                "fk_billing_" + field,
                "customer_billing_offer_bindings",
                [field, *OWNER],
                ["id", *OWNER],
                ondelete="RESTRICT",
            )
        batch.add_column(sa.Column("qualification", sa.JSON()))
        batch.add_column(sa.Column("qualification_digest", sa.String(64)))


def downgrade() -> None:
    db = op.get_bind()
    if db.scalar(sa.text("SELECT count(*) FROM customer_billing_offer_bindings")) or db.scalar(
        sa.text(
            "SELECT count(*) FROM customer_workspace_billing WHERE qualification_digest IS NOT NULL "
            "OR qualification IS NOT NULL OR checkout_offer_binding_id IS NOT NULL "
            "OR subscription_offer_binding_id IS NOT NULL"
        )
    ):
        raise RuntimeError("billing offer lineage requires preservation before downgrade")
    with op.batch_alter_table("customer_workspace_billing") as batch:
        for field in POINTERS:
            batch.drop_constraint("fk_billing_" + field, type_="foreignkey")
            batch.drop_column(field)
        batch.drop_column("qualification")
        batch.drop_column("qualification_digest")
    op.drop_table("customer_billing_offer_bindings")
