"""Immutable billing environment and merchant ownership; legacy rows stay unqualified."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0061"
down_revision = "20261006_0060"
branch_labels = None
depends_on = None

SCOPE = ["provider", "environment", "merchant_account_id"]
TABLES = {"customer_workspace_billing": "workspace_id", "customer_billing_events": "id"}
UNIQUE = ["customer_id", "customer_request_key", "checkout_key", "checkout_id", "subscription_id"]
CONVENTION = {"pk": "pk_%(table_name)s", "uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for name, identity in TABLES.items():
        pk = inspector.get_pk_constraint(name)["name"] or f"pk_{name}"
        unique = inspector.get_unique_constraints(name)
        with op.batch_alter_table(name, naming_convention=CONVENTION) as batch:
            batch.add_column(
                sa.Column("provider", sa.String(16), nullable=False, server_default="stripe")
            )
            batch.add_column(
                sa.Column("environment", sa.String(16), nullable=False, server_default="test")
            )
            batch.add_column(
                sa.Column(
                    "merchant_account_id",
                    sa.String(160),
                    nullable=False,
                    server_default="legacy_unqualified",
                )
            )
            batch.drop_constraint(pk, type_="primary")
            batch.create_primary_key(f"pk_{name}", [identity, *SCOPE])
            if identity == "workspace_id":
                for item in unique:
                    batch.drop_constraint(
                        item["name"] or f"uq_{name}_{item['column_names'][0]}", type_="unique"
                    )
                for column in UNIQUE:
                    batch.create_unique_constraint(f"uq_billing_scope_{column}", [*SCOPE, column])
            batch.create_check_constraint(
                "ck_billing_scope" if identity == "workspace_id" else "ck_billing_event_scope",
                "provider = 'stripe' AND environment IN ('test','live') "
                "AND (environment <> 'live' OR merchant_account_id <> 'legacy_unqualified')",
            )


def downgrade() -> None:
    db = op.get_bind()
    for name, identity in TABLES.items():
        if db.scalar(
            sa.text(
                f"SELECT count(*) FROM {name} WHERE provider <> 'stripe' "
                "OR environment <> 'test' OR merchant_account_id <> 'legacy_unqualified'"
            )
        ):
            raise RuntimeError("qualified billing identities require preservation before downgrade")
        if db.scalar(
            sa.text(
                f"SELECT count(*) FROM (SELECT {identity} FROM {name} "
                f"GROUP BY {identity} HAVING count(*) > 1) AS duplicates"
            )
        ):
            raise RuntimeError("multiple billing identities cannot be collapsed")
    for name, identity in TABLES.items():
        with op.batch_alter_table(name, naming_convention=CONVENTION) as batch:
            batch.drop_constraint(f"pk_{name}", type_="primary")
            batch.create_primary_key(f"pk_{name}", [identity])
            batch.drop_constraint(
                "ck_billing_scope" if identity == "workspace_id" else "ck_billing_event_scope",
                type_="check",
            )
            if identity == "workspace_id":
                for column in UNIQUE:
                    batch.drop_constraint(f"uq_billing_scope_{column}", type_="unique")
                    batch.create_unique_constraint(f"uq_{name}_{column}", [column])
            for column in SCOPE:
                batch.drop_column(column)
