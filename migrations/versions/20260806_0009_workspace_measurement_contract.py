"""add workspace measurement contracts

Revision ID: 20260806_0009
Revises: 20260802_0008
Create Date: 2026-08-06
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0009"
down_revision: str | None = "20260802_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "measurement_contracts",
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("source_of_truth", sa.String(32), nullable=False),
        sa.Column("platform_conversion_role", sa.String(32), nullable=False),
        sa.Column("attribution_model", sa.String(64), nullable=False),
        sa.Column("click_lookback_days", sa.Integer(), nullable=False),
        sa.Column("engaged_view_lookback_days", sa.Integer(), nullable=False),
        sa.Column("outcome_maturity_days", sa.Integer(), nullable=False),
        sa.Column("customer_value_mode", sa.String(64), nullable=False),
        sa.Column("customer_value_horizon_days", sa.Integer(), nullable=False),
        sa.Column("optimization_goal_stage_key", sa.String(64), nullable=False),
        sa.Column("business_value_stage_key", sa.String(64), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_measurement_contracts_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'active')",
            name="ck_measurement_contracts_status",
        ),
        sa.CheckConstraint(
            "status <> 'active' OR effective_at IS NOT NULL",
            name="ck_measurement_contracts_active_effective",
        ),
        sa.CheckConstraint(
            "currency_code = upper(currency_code) AND length(currency_code) = 3",
            name="ck_measurement_contracts_currency",
        ),
        sa.CheckConstraint(
            "source_of_truth = 'crm'",
            name="ck_measurement_contracts_source_of_truth",
        ),
        sa.CheckConstraint(
            "platform_conversion_role IN ('diagnostic_only', 'disabled')",
            name="ck_measurement_contracts_platform_conversion_role",
        ),
        sa.CheckConstraint(
            "attribution_model = 'last_eligible_paid_touch'",
            name="ck_measurement_contracts_attribution_model",
        ),
        sa.CheckConstraint(
            "customer_value_mode IN ('observed_revenue_only', "
            "'observed_plus_modeled_ltv')",
            name="ck_measurement_contracts_customer_value_mode",
        ),
        sa.CheckConstraint(
            "click_lookback_days BETWEEN 1 AND 365",
            name="ck_measurement_contracts_click_lookback",
        ),
        sa.CheckConstraint(
            "engaged_view_lookback_days BETWEEN 0 AND 30",
            name="ck_measurement_contracts_view_lookback",
        ),
        sa.CheckConstraint(
            "outcome_maturity_days BETWEEN 1 AND 730",
            name="ck_measurement_contracts_outcome_maturity",
        ),
        sa.CheckConstraint(
            "customer_value_horizon_days BETWEEN 1 AND 3650",
            name="ck_measurement_contracts_value_horizon",
        ),
    )
    op.create_table(
        "measurement_stage_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("measurement_contracts.workspace_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("counts_toward_funnel", sa.Boolean(), nullable=False),
        sa.Column("accepts_monetary_value", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(512), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "workspace_id",
            "stage_key",
            name="uq_measurement_stages_workspace_key",
        ),
        sa.CheckConstraint(
            "stage_key = lower(stage_key) AND stage_key NOT LIKE '% %'",
            name="ck_measurement_stages_key_canonical",
        ),
        sa.CheckConstraint("position >= 1", name="ck_measurement_stages_position"),
        sa.CheckConstraint(
            "category IN ('leading_indicator', 'optimization_outcome', "
            "'business_outcome', 'value_adjustment', 'negative_outcome')",
            name="ck_measurement_stages_category",
        ),
    )
    op.create_index(
        "ix_measurement_stages_workspace_position",
        "measurement_stage_definitions",
        ["workspace_id", "position"],
    )
    op.create_table(
        "measurement_event_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("event_source", sa.String(32), nullable=False),
        sa.Column("source_event_type", sa.String(64), nullable=False),
        sa.Column("stage_key", sa.String(64), nullable=False),
        sa.Column("authority", sa.String(16), nullable=False),
        sa.Column("value_behavior", sa.String(16), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["measurement_contracts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "stage_key"],
            [
                "measurement_stage_definitions.workspace_id",
                "measurement_stage_definitions.stage_key",
            ],
            name="fk_measurement_mappings_workspace_stage",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "event_source",
            "source_event_type",
            name="uq_measurement_mappings_workspace_source_event",
        ),
        sa.CheckConstraint(
            "event_source IN ('crm', 'web_analytics', 'google_ads', 'meta_ads')",
            name="ck_measurement_mappings_event_source",
        ),
        sa.CheckConstraint(
            "authority IN ('authoritative', 'diagnostic')",
            name="ck_measurement_mappings_authority",
        ),
        sa.CheckConstraint(
            "value_behavior IN ('ignore', 'set', 'adjust')",
            name="ck_measurement_mappings_value_behavior",
        ),
        sa.CheckConstraint(
            "source_event_type = lower(source_event_type) "
            "AND source_event_type NOT LIKE '% %'",
            name="ck_measurement_mappings_event_canonical",
        ),
    )
    op.create_index(
        "ix_measurement_mappings_workspace_stage",
        "measurement_event_mappings",
        ["workspace_id", "stage_key"],
    )

    connection = op.get_bind()
    workspace_id = connection.scalar(
        sa.text("SELECT id FROM workspaces WHERE slug = 'denticode'")
    )
    if workspace_id is None:
        return
    currency_code = connection.scalar(
        sa.text(
            "SELECT currency_code FROM advertising_accounts "
            "WHERE workspace_id = :workspace_id ORDER BY id LIMIT 1"
        ),
        {"workspace_id": workspace_id},
    )
    currency = str(currency_code or "USD").upper()
    if len(currency) != 3:
        currency = "USD"
    now = datetime.now(UTC)

    contract_table = sa.table(
        "measurement_contracts",
        sa.column("workspace_id", sa.Integer()),
        sa.column("version", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("effective_at", sa.DateTime(timezone=True)),
        sa.column("currency_code", sa.String()),
        sa.column("source_of_truth", sa.String()),
        sa.column("platform_conversion_role", sa.String()),
        sa.column("attribution_model", sa.String()),
        sa.column("click_lookback_days", sa.Integer()),
        sa.column("engaged_view_lookback_days", sa.Integer()),
        sa.column("outcome_maturity_days", sa.Integer()),
        sa.column("customer_value_mode", sa.String()),
        sa.column("customer_value_horizon_days", sa.Integer()),
        sa.column("optimization_goal_stage_key", sa.String()),
        sa.column("business_value_stage_key", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        contract_table,
        [
            {
                "workspace_id": int(workspace_id),
                "version": 1,
                "status": "draft",
                "effective_at": None,
                "currency_code": currency,
                "source_of_truth": "crm",
                "platform_conversion_role": "diagnostic_only",
                "attribution_model": "last_eligible_paid_touch",
                "click_lookback_days": 90,
                "engaged_view_lookback_days": 0,
                "outcome_maturity_days": 90,
                "customer_value_mode": "observed_revenue_only",
                "customer_value_horizon_days": 365,
                "optimization_goal_stage_key": "qualified_lead",
                "business_value_stage_key": "sale",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    stage_table = sa.table(
        "measurement_stage_definitions",
        sa.column("workspace_id", sa.Integer()),
        sa.column("stage_key", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("position", sa.Integer()),
        sa.column("category", sa.String()),
        sa.column("counts_toward_funnel", sa.Boolean()),
        sa.column("accepts_monetary_value", sa.Boolean()),
        sa.column("description", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    stage_rows = [
        ("lead", "Lead", 10, "leading_indicator", True, False, "A new lead entered the CRM."),
        (
            "appointment",
            "Appointment scheduled",
            20,
            "leading_indicator",
            True,
            False,
            "The lead scheduled an appointment.",
        ),
        (
            "qualified_lead",
            "Qualified lead",
            30,
            "optimization_outcome",
            True,
            False,
            "The CRM confirmed that the lead meets Denticode's qualification standard.",
        ),
        (
            "proposal",
            "Proposal sent",
            40,
            "leading_indicator",
            True,
            False,
            "A commercial proposal was sent to the qualified lead.",
        ),
        (
            "sale",
            "Sale won",
            50,
            "business_outcome",
            True,
            True,
            "A sale was won; observed CRM value is the authoritative business outcome.",
        ),
        (
            "revenue_adjustment",
            "Revenue adjustment",
            60,
            "value_adjustment",
            False,
            True,
            "A later CRM event corrected observed revenue without inventing modeled value.",
        ),
        (
            "lost",
            "Sale lost",
            90,
            "negative_outcome",
            False,
            False,
            "The CRM marked the opportunity as lost.",
        ),
        (
            "cancelled",
            "Sale cancelled",
            91,
            "negative_outcome",
            False,
            False,
            "The CRM marked a previously won sale as cancelled.",
        ),
    ]
    op.bulk_insert(
        stage_table,
        [
            {
                "workspace_id": int(workspace_id),
                "stage_key": key,
                "display_name": name,
                "position": position,
                "category": category,
                "counts_toward_funnel": counts,
                "accepts_monetary_value": accepts_value,
                "description": description,
                "created_at": now,
                "updated_at": now,
            }
            for key, name, position, category, counts, accepts_value, description in stage_rows
        ],
    )
    mapping_table = sa.table(
        "measurement_event_mappings",
        sa.column("workspace_id", sa.Integer()),
        sa.column("event_source", sa.String()),
        sa.column("source_event_type", sa.String()),
        sa.column("stage_key", sa.String()),
        sa.column("authority", sa.String()),
        sa.column("value_behavior", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    event_mappings = [
        ("lead_created", "lead", "ignore"),
        ("appointment_scheduled", "appointment", "ignore"),
        ("lead_qualified", "qualified_lead", "ignore"),
        ("proposal_sent", "proposal", "ignore"),
        ("sale_won", "sale", "set"),
        ("sale_lost", "lost", "ignore"),
        ("sale_cancelled", "cancelled", "adjust"),
        ("revenue_adjusted", "revenue_adjustment", "adjust"),
    ]
    op.bulk_insert(
        mapping_table,
        [
            {
                "workspace_id": int(workspace_id),
                "event_source": "crm",
                "source_event_type": event_type,
                "stage_key": stage_key,
                "authority": "authoritative",
                "value_behavior": value_behavior,
                "created_at": now,
                "updated_at": now,
            }
            for event_type, stage_key, value_behavior in event_mappings
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_measurement_mappings_workspace_stage",
        table_name="measurement_event_mappings",
    )
    op.drop_table("measurement_event_mappings")
    op.drop_index(
        "ix_measurement_stages_workspace_position",
        table_name="measurement_stage_definitions",
    )
    op.drop_table("measurement_stage_definitions")
    op.drop_table("measurement_contracts")
