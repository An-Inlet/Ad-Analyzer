"""Exact fresh-migration bootstrap values for the synthetic restore boundary."""

from typing import Any

STAGES = [
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

MAPPINGS = [
    ("lead_created", "lead", "ignore"),
    ("appointment_scheduled", "appointment", "ignore"),
    ("lead_qualified", "qualified_lead", "ignore"),
    ("proposal_sent", "proposal", "ignore"),
    ("sale_won", "sale", "set"),
    ("sale_lost", "lost", "ignore"),
    ("sale_cancelled", "cancelled", "adjust"),
    ("revenue_adjusted", "revenue_adjustment", "adjust"),
]


def expected_bootstrap() -> dict[str, list[dict[str, Any]]]:
    return {
        "workspaces": [
            dict(
                id=1,
                slug="denticode",
                name="Denticode Ad Analyzer",
                client_name="Denticode",
                status="active",
                is_default=True,
                export_privacy_revision=0,
            )
        ],
        "workspace_configurations": [
            dict(
                workspace_id=1,
                analysis={},
                automation={"live_writes_enabled": False},
                notifications={},
                branding={
                    "platform_name": "Ad Analyzer",
                    "workspace_name": "Denticode Ad Analyzer",
                },
            )
        ],
        "workspace_integrations": [
            dict(
                id=1,
                workspace_id=1,
                integration_key="denticode-crm-primary",
                provider="crm",
                display_name="Denticode CRM",
                status="configured",
                configuration={},
                secret_manager_reference=None,
            )
        ],
        "measurement_contracts": [
            dict(
                workspace_id=1,
                version=1,
                status="draft",
                effective_at=None,
                currency_code="USD",
                source_of_truth="crm",
                platform_conversion_role="diagnostic_only",
                attribution_model="last_eligible_paid_touch",
                click_lookback_days=90,
                engaged_view_lookback_days=0,
                outcome_maturity_days=90,
                customer_value_mode="observed_revenue_only",
                customer_value_horizon_days=365,
                optimization_goal_stage_key="qualified_lead",
                business_value_stage_key="sale",
            )
        ],
        "measurement_stage_definitions": [
            dict(
                id=index,
                workspace_id=1,
                stage_key=key,
                display_name=name,
                position=position,
                category=category,
                counts_toward_funnel=counts,
                accepts_monetary_value=accepts,
                description=description,
            )
            for index, (key, name, position, category, counts, accepts, description) in enumerate(
                STAGES, 1
            )
        ],
        "measurement_event_mappings": [
            dict(
                id=index,
                workspace_id=1,
                event_source="crm",
                source_event_type=event,
                stage_key=stage,
                authority="authoritative",
                value_behavior=value,
            )
            for index, (event, stage, value) in enumerate(MAPPINGS, 1)
        ],
        "platform_automation_controls": [
            dict(key=key, enabled=key != "github_hourly_production_audit", updated_by="migration")
            for key in (
                "github_hourly_production_audit",
                "post_sync_analysis",
                "nightly_analysis",
                "weekly_analysis",
                "automatic_recommendation_drafts",
                "all_data_syncs",
            )
        ],
        "goal_usage_policies": [
            dict(scope="global", call_limit=1000, cost_limit_micros=0, version=1)
        ],
    }
