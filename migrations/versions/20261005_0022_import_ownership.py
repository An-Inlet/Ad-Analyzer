"""Bind source connections to owned accounts/jobs; preserve unbound legacy history."""

import sqlalchemy as sa
from alembic import op

revision = "20261005_0022"
down_revision = "20261005_0021"
branch_labels = None
depends_on = None


def native_binding(db, table: str, provider: str, row) -> int:
    registry = sa.table(
        "workspace_integrations",
        sa.column("id", sa.Integer()),
        sa.column("workspace_id", sa.Integer()),
        sa.column("integration_key", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    key = f"{provider}-source-{row['id']}"
    marker = {"native_source_table": table, "native_source_id": row["id"]}
    existing = (
        db.execute(
            sa.select(registry).where(
                registry.c.workspace_id == row["workspace_id"], registry.c.integration_key == key
            )
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        # Downgrades retain registry rows for history. Reuse only our exact source marker;
        # never overwrite a similarly named customer connection or reactivate a revoked one.
        if existing["provider"] != provider or existing["configuration"] != marker:
            raise RuntimeError("Native connection backfill key requires explicit repair")
        return existing["id"]
    return db.execute(
        sa.insert(registry)
        .values(
            workspace_id=row["workspace_id"],
            integration_key=key,
            provider=provider,
            display_name=provider,
            status="active" if row["status"] in ("active", "connected") else "revoked",
            configuration=marker,
            created_at=sa.func.now(),
            updated_at=sa.func.now(),
        )
        .returning(registry.c.id)
    ).scalar_one()


def upgrade() -> None:
    for owned_table in ("advertising_accounts", "job_runs", "crm_connections"):
        op.alter_column(owned_table, "workspace_id", server_default=None)
    with op.batch_alter_table("workspace_integrations") as batch:
        batch.create_unique_constraint(
            "uq_workspace_integrations_id_workspace", ["id", "workspace_id"]
        )
    for table in ("advertising_accounts", "job_runs"):
        op.add_column(table, sa.Column("connection_id", sa.Integer(), nullable=True))
    for table in ("meta_connections", "shopify_connections"):
        op.add_column(table, sa.Column("workspace_integration_id", sa.Integer(), nullable=True))
    # Existing native connection ownership is already explicit. Bind from that stored owner only.
    db = op.get_bind()
    for table, provider in (
        ("meta_connections", "meta_ads"),
        ("shopify_connections", "shopify"),
        ("crm_connections", "crm"),
    ):
        rows = (
            db.execute(
                sa.text(f"SELECT id, workspace_id, status, workspace_integration_id FROM {table}")
            )
            .mappings()
            .all()
        )
        for row in rows:
            existing = row["workspace_integration_id"]
            if existing is not None:
                valid = db.execute(
                    sa.text(
                        "SELECT id FROM workspace_integrations "
                        "WHERE id=:id AND workspace_id=:workspace"
                    ),
                    {"id": existing, "workspace": row["workspace_id"]},
                ).scalar()
                if valid is None:
                    raise RuntimeError(
                        "Native connection ownership requires explicit repair before migration"
                    )
                connection_id = existing
            else:
                connection_id = native_binding(db, table, provider, row)
                db.execute(
                    sa.text(
                        f"UPDATE {table} SET workspace_integration_id=:connection WHERE id=:id"
                    ),
                    {"connection": connection_id, "id": row["id"]},
                )
            if table == "meta_connections":
                db.execute(
                    sa.text("""UPDATE advertising_accounts SET connection_id=:connection
                    WHERE id=(SELECT account_id FROM meta_connections WHERE id=:id)
                      AND workspace_id=:workspace"""),
                    {
                        "connection": connection_id,
                        "id": row["id"],
                        "workspace": row["workspace_id"],
                    },
                )
                # Historical Meta runs can be linked to their known existing account binding.
                db.execute(
                    sa.text("""UPDATE job_runs SET connection_id=:connection
                    WHERE account_id=(SELECT account_id FROM meta_connections WHERE id=:id)
                      AND workspace_id=:workspace AND platform='meta_ads'"""),
                    {
                        "connection": connection_id,
                        "id": row["id"],
                        "workspace": row["workspace_id"],
                    },
                )
    with op.batch_alter_table("advertising_accounts") as batch:
        batch.create_foreign_key(
            "fk_account_connection_workspace",
            "workspace_integrations",
            ["connection_id", "workspace_id"],
            ["id", "workspace_id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint(
            "uq_account_connection_scope", ["id", "workspace_id", "connection_id"]
        )
    with op.batch_alter_table("job_runs") as batch:
        batch.create_foreign_key(
            "fk_job_connection_workspace",
            "workspace_integrations",
            ["connection_id", "workspace_id"],
            ["id", "workspace_id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_job_account_connection",
            "advertising_accounts",
            ["account_id", "workspace_id", "connection_id"],
            ["id", "workspace_id", "connection_id"],
            ondelete="RESTRICT",
        )
    for table, constraint in (
        ("meta_connections", "fk_metaconnection_integration_scope"),
        ("shopify_connections", "fk_shopifyconnection_integration_scope"),
        ("crm_connections", "fk_crm_integration_scope"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(
                constraint,
                "workspace_integrations",
                ["workspace_integration_id", "workspace_id"],
                ["id", "workspace_id"],
                ondelete="RESTRICT",
            )
            if table == "crm_connections":
                batch.create_unique_constraint("uq_crm_integration", ["workspace_integration_id"])
    op.create_table(
        "import_rejections",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for owned_table in ("advertising_accounts", "job_runs", "crm_connections"):
        op.alter_column(owned_table, "workspace_id", server_default="1")
    op.drop_table("import_rejections")
    for table, constraint in (
        ("crm_connections", "fk_crm_integration_scope"),
        ("shopify_connections", "fk_shopifyconnection_integration_scope"),
        ("meta_connections", "fk_metaconnection_integration_scope"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(constraint, type_="foreignkey")
            if table == "crm_connections":
                batch.drop_constraint("uq_crm_integration", type_="unique")
            else:
                batch.drop_column("workspace_integration_id")
    with op.batch_alter_table("job_runs") as batch:
        batch.drop_constraint("fk_job_account_connection", type_="foreignkey")
        batch.drop_constraint("fk_job_connection_workspace", type_="foreignkey")
        batch.drop_column("connection_id")
    with op.batch_alter_table("advertising_accounts") as batch:
        batch.drop_constraint("fk_account_connection_workspace", type_="foreignkey")
        batch.drop_constraint("uq_account_connection_scope", type_="unique")
        batch.drop_column("connection_id")
    with op.batch_alter_table("workspace_integrations") as batch:
        batch.drop_constraint("uq_workspace_integrations_id_workspace", type_="unique")
