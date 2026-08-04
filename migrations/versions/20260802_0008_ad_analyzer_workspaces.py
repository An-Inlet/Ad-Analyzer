"""establish Ad Analyzer client workspaces

Revision ID: 20260802_0008
Revises: 20260729_0007
Create Date: 2026-08-02
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0008"
down_revision: str | None = "20260729_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    now = datetime.now(UTC)
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "slug = lower(slug) AND slug NOT LIKE '% %'",
            name="ck_workspaces_slug_canonical",
        ),
    )
    op.create_index("ix_workspaces_status", "workspaces", ["status"])
    workspace_table = sa.table(
        "workspaces",
        sa.column("id", sa.Integer()),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("client_name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("is_default", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        workspace_table,
        [
            {
                "slug": "denticode",
                "name": "Denticode Ad Analyzer",
                "client_name": "Denticode",
                "status": "active",
                "is_default": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    connection = op.get_bind()
    denticode_workspace_id = int(
        connection.scalar(
            sa.select(workspace_table.c.id).where(workspace_table.c.slug == "denticode")
        )
    )

    op.create_table(
        "workspace_configurations",
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("analysis", sa.JSON(), nullable=False),
        sa.Column("automation", sa.JSON(), nullable=False),
        sa.Column("notifications", sa.JSON(), nullable=False),
        sa.Column("branding", sa.JSON(), nullable=False),
        *_timestamps(),
    )
    configuration_table = sa.table(
        "workspace_configurations",
        sa.column("workspace_id", sa.Integer()),
        sa.column("analysis", sa.JSON()),
        sa.column("automation", sa.JSON()),
        sa.column("notifications", sa.JSON()),
        sa.column("branding", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        configuration_table,
        [
            {
                "workspace_id": denticode_workspace_id,
                "analysis": {},
                "automation": {"live_writes_enabled": False},
                "notifications": {},
                "branding": {
                    "platform_name": "Ad Analyzer",
                    "workspace_name": "Denticode Ad Analyzer",
                },
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("principal", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "principal", name="uq_workspace_memberships_principal"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'analyst', 'viewer')",
            name="ck_workspace_memberships_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended')",
            name="ck_workspace_memberships_status",
        ),
    )
    op.create_index(
        "ix_workspace_memberships_principal_status",
        "workspace_memberships",
        ["principal", "status"],
    )
    op.create_table(
        "workspace_integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("integration_key", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("secret_manager_reference", sa.String(512)),
        *_timestamps(),
        sa.UniqueConstraint(
            "workspace_id", "integration_key", name="uq_workspace_integrations_key"
        ),
    )
    op.create_index(
        "ix_workspace_integrations_provider_status",
        "workspace_integrations",
        ["provider", "status"],
    )

    scoped_tables = ("advertising_accounts", "conversion_events", "job_runs", "recommendations")
    for table_name in scoped_tables:
        op.add_column(table_name, sa.Column("workspace_id", sa.Integer(), nullable=True))
        connection.execute(
            sa.text(f"UPDATE {table_name} SET workspace_id = :workspace_id"),
            {"workspace_id": denticode_workspace_id},
        )
        op.alter_column(table_name, "workspace_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table_name}_workspace",
            table_name,
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="RESTRICT" if table_name != "recommendations" else "CASCADE",
        )

    op.add_column("crm_connections", sa.Column("workspace_id", sa.Integer(), nullable=True))
    connection.execute(
        sa.text("UPDATE crm_connections SET workspace_id = :workspace_id"),
        {"workspace_id": denticode_workspace_id},
    )
    op.alter_column("crm_connections", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_crm_connections_workspace",
        "crm_connections",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "crm_connections", sa.Column("workspace_integration_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_crm_connections_workspace_integration",
        "crm_connections",
        "workspace_integrations",
        ["workspace_integration_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("uq_ad_accounts_platform_external", "advertising_accounts", type_="unique")
    op.drop_index("ix_ad_accounts_platform", table_name="advertising_accounts")
    op.create_unique_constraint(
        "uq_ad_accounts_workspace_platform_external",
        "advertising_accounts",
        ["workspace_id", "platform", "external_account_id"],
    )
    op.create_unique_constraint(
        "uq_ad_accounts_id_workspace",
        "advertising_accounts",
        ["id", "workspace_id"],
    )
    op.create_unique_constraint(
        "uq_campaigns_id_account",
        "campaigns",
        ["id", "account_id"],
    )
    op.create_foreign_key(
        "fk_job_runs_account_workspace",
        "job_runs",
        "advertising_accounts",
        ["account_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_recommendations_account_workspace",
        "recommendations",
        "advertising_accounts",
        ["account_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="CASCADE",
    )
    connection.execute(
        sa.text(
            "UPDATE recommendations AS recommendation SET campaign_id = NULL "
            "WHERE campaign_id IS NOT NULL AND NOT EXISTS ("
            "SELECT 1 FROM campaigns AS campaign "
            "WHERE campaign.id = recommendation.campaign_id "
            "AND campaign.account_id = recommendation.account_id)"
        )
    )
    op.create_foreign_key(
        "fk_recommendations_campaign_account",
        "recommendations",
        "campaigns",
        ["campaign_id", "account_id"],
        ["id", "account_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_ad_accounts_workspace_platform",
        "advertising_accounts",
        ["workspace_id", "platform"],
    )

    op.drop_constraint(
        "uq_conversion_events_platform_external", "conversion_events", type_="unique"
    )
    op.drop_index("ix_conversion_events_platform_occurred", table_name="conversion_events")
    op.create_unique_constraint(
        "uq_conversion_events_workspace_platform_external",
        "conversion_events",
        ["workspace_id", "platform", "external_conversion_id"],
    )
    op.create_index(
        "ix_conversion_events_workspace_platform_occurred",
        "conversion_events",
        ["workspace_id", "platform", "occurred_at"],
    )
    op.create_index(
        "ix_job_runs_workspace_started",
        "job_runs",
        ["workspace_id", sa.text("started_at DESC")],
    )
    op.drop_index("ix_recommendations_account_status", table_name="recommendations")
    op.create_index(
        "ix_recommendations_workspace_account_status",
        "recommendations",
        ["workspace_id", "account_id", "status"],
    )
    op.drop_index("ix_crm_connections_status", table_name="crm_connections")
    op.create_unique_constraint(
        "uq_crm_connections_workspace_name",
        "crm_connections",
        ["workspace_id", "name"],
    )
    op.create_index(
        "ix_crm_connections_workspace_status",
        "crm_connections",
        ["workspace_id", "status"],
    )

    op.create_table(
        "workspace_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("advertising_account_id", sa.Integer()),
        sa.Column("campaign_id", sa.Integer()),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("code", sa.String(96), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("supporting_metrics", sa.JSON(), nullable=False),
        sa.Column("window_start", sa.Date()),
        sa.Column("window_end", sa.Date()),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["advertising_account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            name="fk_workspace_findings_ad_account_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "advertising_account_id"],
            ["campaigns.id", "campaigns.account_id"],
            name="fk_workspace_findings_campaign_account",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "dedupe_key", name="uq_workspace_findings_dedupe"),
    )
    op.create_index(
        "ix_workspace_findings_status_detected",
        "workspace_findings",
        ["workspace_id", "status", "detected_at"],
    )

    integration_table = sa.table(
        "workspace_integrations",
        sa.column("id", sa.Integer()),
        sa.column("workspace_id", sa.Integer()),
        sa.column("integration_key", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", sa.JSON()),
        sa.column("secret_manager_reference", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    platforms = {
        str(value)
        for value in connection.scalars(
            sa.text("SELECT DISTINCT platform FROM advertising_accounts")
        )
    }
    integration_rows: list[dict[str, object]] = []
    if "google_ads" in platforms:
        integration_rows.append(
            {
                "workspace_id": denticode_workspace_id,
                "integration_key": "google-ads-primary",
                "provider": "google_ads",
                "display_name": "Google Ads",
                "status": "active",
                "configuration": {},
                "secret_manager_reference": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    if "meta_ads" in platforms:
        integration_rows.append(
            {
                "workspace_id": denticode_workspace_id,
                "integration_key": "meta-ads-primary",
                "provider": "meta_ads",
                "display_name": "Meta Ads",
                "status": "active",
                "configuration": {},
                "secret_manager_reference": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    crm_count = int(connection.scalar(sa.text("SELECT count(*) FROM crm_connections")) or 0)
    integration_rows.append(
        {
            "workspace_id": denticode_workspace_id,
            "integration_key": "denticode-crm-primary",
            "provider": "crm",
            "display_name": "Denticode CRM",
            "status": "active" if crm_count else "configured",
            "configuration": {},
            "secret_manager_reference": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    op.bulk_insert(integration_table, integration_rows)
    crm_integration_id = int(
        connection.scalar(
            sa.select(integration_table.c.id).where(
                integration_table.c.workspace_id == denticode_workspace_id,
                integration_table.c.integration_key == "denticode-crm-primary",
            )
        )
    )
    connection.execute(
        sa.text(
            "UPDATE crm_connections SET workspace_integration_id = :integration_id "
            "WHERE workspace_id = :workspace_id"
        ),
        {"integration_id": crm_integration_id, "workspace_id": denticode_workspace_id},
    )


def downgrade() -> None:
    workspace_count = int(op.get_bind().scalar(sa.text("SELECT count(*) FROM workspaces")) or 0)
    if workspace_count > 1:
        raise RuntimeError(
            "Refusing to remove workspace isolation while multiple workspaces exist."
        )

    op.drop_table("workspace_findings")
    op.drop_index("ix_crm_connections_workspace_status", table_name="crm_connections")
    op.drop_constraint("uq_crm_connections_workspace_name", "crm_connections", type_="unique")
    op.create_index("ix_crm_connections_status", "crm_connections", ["status"])
    op.drop_constraint(
        "fk_crm_connections_workspace_integration", "crm_connections", type_="foreignkey"
    )
    op.drop_column("crm_connections", "workspace_integration_id")
    op.drop_constraint("fk_crm_connections_workspace", "crm_connections", type_="foreignkey")
    op.drop_column("crm_connections", "workspace_id")

    op.drop_index("ix_recommendations_workspace_account_status", table_name="recommendations")
    op.create_index(
        "ix_recommendations_account_status", "recommendations", ["account_id", "status"]
    )
    op.drop_index("ix_job_runs_workspace_started", table_name="job_runs")
    op.drop_index(
        "ix_conversion_events_workspace_platform_occurred", table_name="conversion_events"
    )
    op.drop_constraint(
        "uq_conversion_events_workspace_platform_external",
        "conversion_events",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_conversion_events_platform_external",
        "conversion_events",
        ["platform", "external_conversion_id"],
    )
    op.create_index(
        "ix_conversion_events_platform_occurred",
        "conversion_events",
        ["platform", "occurred_at"],
    )
    op.drop_index("ix_ad_accounts_workspace_platform", table_name="advertising_accounts")
    op.drop_constraint("fk_recommendations_campaign_account", "recommendations", type_="foreignkey")
    op.drop_constraint(
        "fk_recommendations_account_workspace", "recommendations", type_="foreignkey"
    )
    op.drop_constraint("fk_job_runs_account_workspace", "job_runs", type_="foreignkey")
    op.drop_constraint("uq_ad_accounts_id_workspace", "advertising_accounts", type_="unique")
    op.drop_constraint("uq_campaigns_id_account", "campaigns", type_="unique")
    op.drop_constraint(
        "uq_ad_accounts_workspace_platform_external",
        "advertising_accounts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_ad_accounts_platform_external",
        "advertising_accounts",
        ["platform", "external_account_id"],
    )
    op.create_index("ix_ad_accounts_platform", "advertising_accounts", ["platform"])

    for table_name in ("recommendations", "job_runs", "conversion_events", "advertising_accounts"):
        op.drop_constraint(f"fk_{table_name}_workspace", table_name, type_="foreignkey")
        op.drop_column(table_name, "workspace_id")

    op.drop_table("workspace_integrations")
    op.drop_table("workspace_memberships")
    op.drop_table("workspace_configurations")
    op.drop_table("workspaces")
