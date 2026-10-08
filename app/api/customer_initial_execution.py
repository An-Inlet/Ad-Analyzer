"""Explicit v2 preview handoff to separately consented exact execution review."""

from fastapi import APIRouter, Depends, Response

from app import advertising_capabilities
from app.api.customer_initial_planning import Runtime
from app.api.customer_optimization import Runtime as OptimizationRuntime
from app.api.planning_boundary import deny_advertising_mutation, deny_advertising_options
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.initial_planning.review_v2_api_contracts import (
    InitialPreviewExecutionOptionsV1,
    InitialPreviewExecutionRuntime,
)
from app.initial_planning.review_v2_bridge import (
    execution_review_options,
    prepare_preview_execution,
)
from app.initial_planning.review_v2_contracts import (
    InitialPreviewExecutionIntentV1,
    InitialPreviewExecutionPreparedV1,
)
from app.publication.service import owner

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/initial-planning/previews/{preview_id}",
    tags=["customer"],
)


@router.get(
    "/execution-review-options",
    response_model=InitialPreviewExecutionOptionsV1,
    dependencies=[Depends(deny_advertising_options)],
)
def options(
    workspace_id: int,
    preview_id: str,
    principal: Principal,
    provider: Provider,
    db: Database,
    planning: Runtime,
    optimization: OptimizationRuntime,
    response: Response,
) -> InitialPreviewExecutionOptionsV1:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    response.headers["Cache-Control"] = "no-store"
    return execution_review_options(
        InitialPreviewExecutionRuntime(planning, optimization),
        principal,
        provider,
        workspace_id,
        preview_id,
    )


@router.post(
    "/execution-review",
    response_model=InitialPreviewExecutionPreparedV1,
    dependencies=[Depends(deny_advertising_mutation)],
)
def prepare(
    workspace_id: int,
    preview_id: str,
    body: InitialPreviewExecutionIntentV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    planning: Runtime,
    optimization: OptimizationRuntime,
    response: Response,
) -> InitialPreviewExecutionPreparedV1:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    response.headers["Cache-Control"] = "no-store"
    return prepare_preview_execution(
        InitialPreviewExecutionRuntime(planning, optimization),
        principal,
        provider,
        workspace_id,
        preview_id,
        body,
    )
