"""Explicit v2 preview handoff to separately consented exact execution review."""

from fastapi import APIRouter, Response

from app.api.customer_initial_planning import Runtime
from app.api.customer_optimization import Runtime as OptimizationRuntime
from app.customers.access import MutationPrincipal, Principal, Provider
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

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/initial-planning/previews/{preview_id}",
    tags=["customer"],
)


@router.get("/execution-review-options", response_model=InitialPreviewExecutionOptionsV1)
def options(
    workspace_id: int,
    preview_id: str,
    principal: Principal,
    provider: Provider,
    planning: Runtime,
    optimization: OptimizationRuntime,
    response: Response,
) -> InitialPreviewExecutionOptionsV1:
    response.headers["Cache-Control"] = "no-store"
    return execution_review_options(
        InitialPreviewExecutionRuntime(planning, optimization),
        principal,
        provider,
        workspace_id,
        preview_id,
    )


@router.post("/execution-review", response_model=InitialPreviewExecutionPreparedV1)
def prepare(
    workspace_id: int,
    preview_id: str,
    body: InitialPreviewExecutionIntentV1,
    principal: MutationPrincipal,
    provider: Provider,
    planning: Runtime,
    optimization: OptimizationRuntime,
    response: Response,
) -> InitialPreviewExecutionPreparedV1:
    response.headers["Cache-Control"] = "no-store"
    return prepare_preview_execution(
        InitialPreviewExecutionRuntime(planning, optimization),
        principal,
        provider,
        workspace_id,
        preview_id,
        body,
    )
