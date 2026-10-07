"""Local context commitment; no baseline qualification or interpretation authority."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.models import CommerceStore
from app.goals.models import Goal
from app.goals.schemas import GoalDefinition
from app.goals.service import current
from app.shopify.models import ShopifyConnection
from app.workspaces.models import Workspace, WorkspaceIntegration


def context(db: Session, goal: Goal) -> tuple[Any, ...]:
    """Read under the caller's canonical workspace/goal fence, without IO or commits.

    Manual clarification remains available for incomplete/unavailable sources; a
    source change during a call invalidates its result, not its usage accounting.
    """
    definition = current(db, goal).definition
    privacy = db.scalar(
        select(Workspace.export_privacy_revision).where(Workspace.id == goal.workspace_id)
    )
    if definition is None:
        return (privacy, None)
    selected = GoalDefinition.model_validate(definition)
    store = db.execute(
        select(
            CommerceStore.id,
            CommerceStore.revision,
            CommerceStore.status,
            CommerceStore.connection_id,
            CommerceStore.currency,
            CommerceStore.time_zone,
        ).where(
            CommerceStore.id == selected.store_id, CommerceStore.workspace_id == goal.workspace_id
        )
    ).first()
    connection = db.execute(
        select(
            ShopifyConnection.id,
            ShopifyConnection.status,
            ShopifyConnection.connected_at,
            ShopifyConnection.workspace_integration_id,
        ).where(
            ShopifyConnection.commerce_store_id == selected.store_id,
            ShopifyConnection.workspace_id == goal.workspace_id,
        )
    ).first()
    integration = (
        db.execute(
            select(WorkspaceIntegration.id, WorkspaceIntegration.status).where(
                WorkspaceIntegration.id == store.connection_id,
                WorkspaceIntegration.workspace_id == goal.workspace_id,
            )
        ).first()
        if store
        else None
    )
    return (
        privacy,
        tuple(store) if store else None,
        tuple(connection) if connection else None,
        tuple(integration) if integration else None,
    )
