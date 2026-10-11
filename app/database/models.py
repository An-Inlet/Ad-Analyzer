"""One explicit ORM registry shared by migrations, services, workers and tests.

Registration imports declarations only; it never opens a database connection,
creates tables or performs provider IO. Add every new model module here.
"""

from importlib import import_module

from sqlalchemy import MetaData

from app.database.session import Base

MODEL_MODULES = (
    "app.ads.models",
    "app.analysis.models",
    "app.automation.models",
    "app.billing.models",
    "app.campaign_review.models",
    "app.campaign_performance.models",
    "app.campaign_performance.presence_models",
    "app.campaign_performance.selected_models",
    "app.campaign_performance.range_receipt_models",
    "app.commerce.models",
    "app.commerce.acquisition_models",
    "app.crm.models",
    "app.customer_context.models",
    "app.customers.models",
    "app.goals.models",
    "app.planning_documents.models",
    "app.planning_documents.catalog_receipt_models",
    "app.google_connections.models",
    "app.imports.models",
    "app.intelligence.models",
    "app.initial_planning.models",
    "app.initial_planning.automatic_models",
    "app.initial_planning.start_models",
    "app.initial_planning.budget_mandate_models",
    "app.initial_planning.planning_consent_models",
    "app.production_runtime.optimization_origin_models",
    "app.initial_planning.review_models",
    "app.initial_planning.review_v2_models",
    "app.lifecycle.models",
    "app.mandates.models",
    "app.measurement.models",
    "app.meta.models",
    "app.meta.presence_models",
    "app.outcomes.models",
    "app.operations.models",
    "app.outcome_feedback.models",
    "app.optimization_candidates.models",
    "app.optimization_candidates.review_models",
    "app.session_automation.models",
    "app.reported_feedback.models",
    "app.reported_feedback.candidate_models",
    "app.publication.execution_models",
    "app.publication.models",
    "app.publication.provider_models",
    "app.publication.social_review_models",
    "app.shopify.models",
    "app.sources.models",
    "app.workspaces.models",
)


# Metadata event installers are required, but do not declare ORM model classes.
GUARD_MODULES = ("app.commerce.acquisition_guards",)


def register_models() -> MetaData:
    """Populate and return the shared metadata, idempotently in any import order."""
    for module in (*MODEL_MODULES, *GUARD_MODULES):
        import_module(module)
    return Base.metadata
