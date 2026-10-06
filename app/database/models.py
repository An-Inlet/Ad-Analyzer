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
    "app.commerce.models",
    "app.crm.models",
    "app.customer_context.models",
    "app.customers.models",
    "app.goals.models",
    "app.google_connections.models",
    "app.imports.models",
    "app.intelligence.models",
    "app.lifecycle.models",
    "app.mandates.models",
    "app.measurement.models",
    "app.meta.models",
    "app.outcomes.models",
    "app.publication.execution_models",
    "app.publication.models",
    "app.publication.provider_models",
    "app.shopify.models",
    "app.sources.models",
    "app.workspaces.models",
)


def register_models() -> MetaData:
    """Populate and return the shared metadata, idempotently in any import order."""
    for module in MODEL_MODULES:
        import_module(module)
    return Base.metadata
