from dataclasses import dataclass
from enum import StrEnum


class AutomationControlKey(StrEnum):
    ALL_DATA_SYNCS = "all_data_syncs"
    GITHUB_HOURLY_PRODUCTION_AUDIT = "github_hourly_production_audit"
    SHOPIFY_SALES_SYNC = "shopify_sales_sync"
    META_ADS_SYNC = "meta_ads_sync"
    POST_SYNC_ANALYSIS = "post_sync_analysis"
    NIGHTLY_ANALYSIS = "nightly_analysis"
    WEEKLY_ANALYSIS = "weekly_analysis"
    AUTOMATIC_RECOMMENDATION_DRAFTS = "automatic_recommendation_drafts"


@dataclass(frozen=True)
class AutomationControlDefinition:
    key: AutomationControlKey
    label: str
    description: str
    supports_workspace: bool
    default_enabled: bool
    external: bool = False


AUTOMATION_CONTROL_DEFINITIONS = (
    AutomationControlDefinition(
        key=AutomationControlKey.ALL_DATA_SYNCS,
        label="All Ad Analyzer data syncs",
        description=(
            "Allows new Google Ads, Meta, and Shopify data-sync cycles across every "
            "Ad Analyzer. Turning this off "
            "also blocks one-shot or manually invoked sync workers; existing synchronized data "
            "and analysis controls remain available."
        ),
        supports_workspace=False,
        default_enabled=True,
    ),
    AutomationControlDefinition(
        key=AutomationControlKey.GITHUB_HOURLY_PRODUCTION_AUDIT,
        label="GitHub hourly production audit",
        description=(
            "Allows the scheduled read-only GitHub production audit. Manual audit runs remain "
            "available when this is off."
        ),
        supports_workspace=False,
        default_enabled=False,
        external=True,
    ),
    AutomationControlDefinition(
        key=AutomationControlKey.META_ADS_SYNC,
        label="Meta advertising sync",
        description="Imports performance from the Meta ad account selected for this workspace. "
        "Existing analysis remains available when sync is off. No ads or budgets are changed.",
        supports_workspace=True,
        default_enabled=True,
    ),
    AutomationControlDefinition(
        key=AutomationControlKey.SHOPIFY_SALES_SYNC,
        label="Shopify sales sync",
        description="Imports recent orders from a connected store. Disabling sync "
        "keeps existing reports available; privacy deletions still run.",
        supports_workspace=True,
        default_enabled=True,
    ),
    AutomationControlDefinition(
        key=AutomationControlKey.POST_SYNC_ANALYSIS,
        label="Post-sync analysis",
        description="Runs a lightweight local analysis after a successful account sync.",
        supports_workspace=True,
        default_enabled=True,
    ),
    AutomationControlDefinition(
        key=AutomationControlKey.NIGHTLY_ANALYSIS,
        label="Nightly analysis",
        description="Runs the full local analyzer once per eligible night.",
        supports_workspace=True,
        default_enabled=True,
    ),
    AutomationControlDefinition(
        key=AutomationControlKey.WEEKLY_ANALYSIS,
        label="Weekly analysis",
        description="Runs the longer-window local analyzer once per eligible week.",
        supports_workspace=True,
        default_enabled=True,
    ),
    AutomationControlDefinition(
        key=AutomationControlKey.AUTOMATIC_RECOMMENDATION_DRAFTS,
        label="Automatic recommendation drafts",
        description=(
            "Creates bounded recommendation proposals from analysis findings for human review. "
            "It never approves or executes them."
        ),
        supports_workspace=True,
        default_enabled=True,
    ),
)

AUTOMATION_CONTROL_BY_KEY = {
    definition.key: definition for definition in AUTOMATION_CONTROL_DEFINITIONS
}
