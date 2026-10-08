"""Owner-only optimization discovery and exact review intent; no proof input."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app import advertising_capabilities
from app.api.customer_optimization_runtime import get_configured_customer_optimization_runtime
from app.api.customer_planning_catalog import accounts as planning_accounts
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.production_runtime import optimization_mandates
from app.production_runtime.optimization_policy_contracts import (
    ConsentOptimizationMandateV1,
    PreparedOptimizationMandateV1,
    PrepareOptimizationMandateV1,
)
from app.publication import customer_intents as intents
from app.publication import customer_optimization as service
from app.publication import execution_mandates as mandates
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    InitialOptimizationIntent,
    OptimizationPolicyEdit,
    OptimizationPolicyIntent,
    RepeatOptimizationIntent,
    TargetQuery,
)
from app.publication.customer_schemas import ConsentIntent
from app.publication.service import owner

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/execution/optimization", tags=["customer"]
)
Runtime = Annotated[
    CustomerOptimizationRuntime | None, Depends(get_configured_customer_optimization_runtime)
]


@router.get("/accounts")
def accounts(
    workspace_id: int, principal: Principal, provider: Provider, db: Database, response: Response
) -> dict[str, Any]:
    return planning_accounts(workspace_id, principal, provider, db, response)


@router.get("/capabilities")
def capabilities(
    workspace_id: int, principal: Principal, db: Database, runtime: Runtime, response: Response
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    enabled = False  # Execution capabilities cannot be enabled in this artifact.
    transports = {
        "google_ads": runtime.execution.google if runtime else None,
        "meta_ads": runtime.execution.meta if runtime else None,
        "tiktok_ads": runtime.execution.tiktok if runtime else None,
    }
    response.headers["Cache-Control"] = "no-store"
    return {
        "providers": [
            {
                "platform": platform,
                "initial_available": bool(enabled and runtime and runtime.catalog and adapter),
                "repeat_available": bool(
                    enabled
                    and runtime
                    and runtime.catalog
                    and adapter
                    and runtime.execution.replacement_reader
                ),
            }
            for platform, adapter in transports.items()
        ],
        "environment": runtime.execution.environment if runtime else None,
        "catalog_available": bool(enabled and runtime and runtime.catalog),
        "repeat_available": bool(
            enabled
            and runtime
            and runtime.catalog
            and any(transports.values())
            and runtime.execution.replacement_reader
        ),
        "live_qualification_implied": False,
        "advertising_writes_enabled": False,
        "reason": None
        if enabled and runtime and runtime.catalog
        else "advertising_writes_disabled_in_planning_mvp",
    }


@router.post("/target-options")
def target_options(
    workspace_id: int,
    body: TargetQuery,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> dict[str, Any]:
    server = service.bind(runtime, principal, provider)
    result = service.discover(db, workspace_id, body, principal.user.id, server)
    response.headers["Cache-Control"] = "no-store"
    return {
        "schema_version": "inlet.customer-optimization-target-options.v1",
        "environment": server.execution.environment,
        "complete": result.complete,
        "observed_at": result.observed_at.isoformat(),
        "expires_at": result.expires_at.isoformat(),
        "options": [
            {"id": o.identifier(result.request), **service.option_view(o)} for o in result.options
        ],
        "dispatch_qualified": False,
    }


@router.post("/mandates", status_code=201)
def create_mandate(
    workspace_id: int,
    body: OptimizationPolicyIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    server = service.bind(runtime, principal, provider)
    if server.configured is not None:
        raise intents.unavailable("optimization_customer_budget_review_required")
    policy = service.make_policy(db, workspace_id, body, principal.user.id, server)
    row = mandates.revise(db, workspace_id, policy, principal.user.id, server.clock)
    response.headers["Cache-Control"] = "no-store"
    return intents.policy_view(db, row)


@router.put("/mandates/{mandate_id}")
def edit_mandate(
    workspace_id: int,
    mandate_id: str,
    body: OptimizationPolicyEdit,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    server = service.bind(runtime, principal, provider)
    if server.configured is not None:
        raise intents.unavailable("optimization_customer_budget_review_required")
    policy = service.make_policy(db, workspace_id, body, principal.user.id, server)
    row = mandates.revise(
        db,
        workspace_id,
        policy,
        principal.user.id,
        server.clock,
        mandate_id=mandate_id,
        expected_revision=body.expected_revision,
    )
    response.headers["Cache-Control"] = "no-store"
    return intents.policy_view(db, row)


@router.post("/mandates/{mandate_id}/consent")
def consent(
    workspace_id: int,
    mandate_id: str,
    body: ConsentIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    server = service.bind(runtime, principal, provider)
    if server.configured is not None:
        raise intents.unavailable("optimization_customer_exact_consent_required")
    service.current_policy_catalog(db, workspace_id, mandate_id, principal.user.id, server)
    mandates.consent(
        db,
        workspace_id,
        mandate_id,
        body.expected_revision,
        body.policy_digest,
        principal.user.id,
        server.clock,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"state": "consented", "revision": body.expected_revision}


@router.post("/initial-reviews", status_code=201)
def initial_review(
    workspace_id: int,
    body: InitialOptimizationIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    server = service.bind(runtime, principal, provider)
    row = service.prepare(db, workspace_id, body, principal.user.id, server)
    response.headers["Cache-Control"] = "no-store"
    return service.review_view(row, db)


@router.post("/repeat-reviews", status_code=201)
def repeat_review(
    workspace_id: int,
    body: RepeatOptimizationIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    server = service.bind(runtime, principal, provider)
    row = service.prepare(db, workspace_id, body, principal.user.id, server)
    response.headers["Cache-Control"] = "no-store"
    return service.review_view(row, db)


@router.post("/budget-mandates", status_code=201, response_model=PreparedOptimizationMandateV1)
def prepare_customer_budget(
    workspace_id: int,
    body: PrepareOptimizationMandateV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> PreparedOptimizationMandateV1:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    server = service.bind(runtime, principal, provider)
    response.headers["Cache-Control"] = "no-store"
    return optimization_mandates.prepare(db, workspace_id, body, principal.user.id, server)


@router.post("/budget-mandates/{mandate_id}/consent", response_model=PreparedOptimizationMandateV1)
def consent_customer_budget(
    workspace_id: int,
    mandate_id: str,
    body: ConsentOptimizationMandateV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> PreparedOptimizationMandateV1:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    server = service.bind(runtime, principal, provider)
    response.headers["Cache-Control"] = "no-store"
    return optimization_mandates.consent(
        db, workspace_id, mandate_id, body, principal.user.id, server
    )
