"""Customer planning intents and immutable reads; no advertising execution routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.orm import object_session

from app.customers.access import CustomerPrincipal, Database, MutationPrincipal, Principal, Provider
from app.customers.identity import IdentityProvider
from app.planning_documents.authority_diagnostics import PlanningDiagnosticRoute
from app.planning_documents.capabilities_view import PlanningCapabilitiesV1
from app.planning_documents.common import Id
from app.planning_documents.comparison import VersionComparison, compare_versions
from app.planning_documents.policy_capabilities import ticket_reporting_capability
from app.planning_documents.progress_contracts import PlanSalesProgressV1
from app.planning_documents.requests import (
    AssertionIntent,
    CreatePlan,
    DecisionIntent,
    EditPlan,
    GeneratePlan,
)
from app.planning_documents.responses import (
    EventPage,
    EventResult,
    InputResult,
    PlanPage,
    PlanReadResult,
    VersionPage,
    VersionResult,
)
from app.planning_documents.runtime_media import ConfiguredPlanningMedia
from app.planning_documents.runtime_policy import configured_policy
from app.planning_documents.service import PlanningDocumentService
from app.publication.customer_runtime import utc_now
from app.settings import settings

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/planning/plans",
    tags=["customer"],
    route_class=PlanningDiagnosticRoute,
)
Cursor = Annotated[str | None, Query(max_length=256)]
Limit = Annotated[int, Query(ge=1, le=100)]
Operation = Literal["create", "revise", "generate", "decide", "assert_applied"]
RequestKey = Annotated[str, Path(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


def service(
    db: Database, provider: IdentityProvider, principal: CustomerPrincipal
) -> PlanningDocumentService:
    policy = configured_policy(settings)
    bind = db.get_bind()
    engine = bind if isinstance(bind, Engine) else bind.engine
    # The authenticated principal must not expire on rollback and issue a lazy SELECT
    # during the service's external identity check. Detach already-loaded rows first.
    for row in (principal.user, principal.session):
        if object_session(row) is db:
            db.expunge(row)
    db.rollback()
    if policy is None:
        return PlanningDocumentService(engine, provider, clock=utc_now)
    if policy.version == "inlet.descriptive-review.v5":
        return PlanningDocumentService(
            engine, provider, clock=utc_now, policy=policy, media_store=ConfiguredPlanningMedia()
        )
    return PlanningDocumentService(engine, provider, clock=utc_now, policy=policy)


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/capabilities", response_model=PlanningCapabilitiesV1)
def planning_capabilities(
    workspace_id: int,
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
) -> PlanningCapabilitiesV1:
    no_store(response)
    configured = service(db, provider, principal)
    with configured._read_session(principal, workspace_id):
        capability = ticket_reporting_capability(
            configured.policy.version, configured.policy.digest()
        )
        return PlanningCapabilitiesV1(
            workspace_id=workspace_id,
            policy_version=configured.policy.version,
            generator_version=configured.policy.generator_version,
            selected_reporting_available=capability.mode
            in (
                "selected_requested_window",
                "creative_selected_requested_window",
                "owner_review_creative_selected_requested_window",
            ),
        )


@router.post("", response_model=InputResult, status_code=201)
def create_plan(
    workspace_id: int,
    body: CreatePlan,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> InputResult:
    no_store(response)
    return service(db, provider, principal).create(principal, workspace_id, body)


@router.get("", response_model=PlanPage)
def list_plans(
    workspace_id: int,
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
    cursor: Cursor = None,
    limit: Limit = 20,
) -> PlanPage:
    no_store(response)
    return service(db, provider, principal).listing(
        principal, workspace_id, cursor=cursor, limit=limit
    )


@router.get(
    "/requests/{operation}/{request_key}", response_model=InputResult | VersionResult | EventResult
)
def request_result(
    workspace_id: int,
    operation: Operation,
    request_key: RequestKey,
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
) -> InputResult | VersionResult | EventResult:
    no_store(response)
    return service(db, provider, principal).request_result(
        principal, workspace_id, operation, request_key
    )


@router.get("/{plan_id}", response_model=PlanReadResult)
def read_plan(
    workspace_id: int,
    plan_id: Id,
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
) -> PlanReadResult:
    no_store(response)
    return service(db, provider, principal).read(principal, workspace_id, plan_id)


@router.post("/{plan_id}/inputs", response_model=InputResult)
def revise_plan(
    workspace_id: int,
    plan_id: Id,
    body: EditPlan,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> InputResult:
    no_store(response)
    return service(db, provider, principal).revise(principal, workspace_id, plan_id, body)


@router.post("/{plan_id}/generate", response_model=VersionResult)
def generate_plan(
    workspace_id: int,
    plan_id: Id,
    body: GeneratePlan,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> VersionResult:
    no_store(response)
    return service(db, provider, principal).generate(principal, workspace_id, plan_id, body)


@router.get("/{plan_id}/versions", response_model=VersionPage)
def plan_versions(
    workspace_id: int,
    plan_id: Id,
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
    cursor: Cursor = None,
    limit: Limit = 20,
) -> VersionPage:
    no_store(response)
    return service(db, provider, principal).history(
        principal, workspace_id, plan_id, cursor=cursor, limit=limit
    )


@router.get("/{plan_id}/versions/{version}", response_model=PlanReadResult)
def read_version(
    workspace_id: int,
    plan_id: Id,
    version: Annotated[int, Path(ge=1)],
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
) -> PlanReadResult:
    no_store(response)
    return service(db, provider, principal).read(principal, workspace_id, plan_id, version)


@router.post("/{plan_id}/decisions", response_model=EventResult)
def decide_action(
    workspace_id: int,
    plan_id: Id,
    body: DecisionIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> EventResult:
    no_store(response)
    return service(db, provider, principal).decide(principal, workspace_id, plan_id, body)


@router.post("/{plan_id}/assertions", response_model=EventResult)
def report_application(
    workspace_id: int,
    plan_id: Id,
    body: AssertionIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> EventResult:
    no_store(response)
    return service(db, provider, principal).assert_applied(principal, workspace_id, plan_id, body)


@router.get("/{plan_id}/events", response_model=EventPage)
def plan_events(
    workspace_id: int,
    plan_id: Id,
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
    cursor: Cursor = None,
    limit: Limit = 20,
) -> EventPage:
    no_store(response)
    return service(db, provider, principal).events(
        principal, workspace_id, plan_id, cursor=cursor, limit=limit
    )


@router.get("/{plan_id}/export")
def export_version(
    workspace_id: int,
    plan_id: Id,
    version: Annotated[int, Query(ge=1)],
    principal: Principal,
    provider: Provider,
    db: Database,
) -> JSONResponse:
    result = service(db, provider, principal).export(principal, workspace_id, plan_id, version)
    filename = f"inlet-plan-{plan_id}-version-{version}-artifact.json"
    return JSONResponse(
        result.model_dump(mode="json"),
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{plan_id}/comparisons/{previous_version}/{current_version}", response_model=VersionComparison
)
def compare_plan_versions(
    workspace_id: int,
    plan_id: Id,
    previous_version: Annotated[int, Path(ge=1)],
    current_version: Annotated[int, Path(ge=2)],
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
) -> VersionComparison:
    no_store(response)
    if current_version != previous_version + 1:
        raise HTTPException(422, "Select consecutive plan versions.")
    runtime = service(db, provider, principal)
    previous = runtime.read(principal, workspace_id, plan_id, previous_version)
    current = runtime.read(principal, workspace_id, plan_id, current_version)
    if previous.document is None or current.document is None:
        raise HTTPException(409, "Both saved versions are required for comparison.")
    try:
        return compare_versions(previous.document, current.document)
    except ValueError:
        raise HTTPException(409, "The selected versions cannot be compared.") from None


@router.get("/{plan_id}/progress", response_model=PlanSalesProgressV1)
def sales_progress(
    workspace_id: int,
    plan_id: Id,
    version: Annotated[int, Query(ge=1)],
    principal: Principal,
    provider: Provider,
    db: Database,
    response: Response,
) -> PlanSalesProgressV1:
    no_store(response)
    return service(db, provider, principal).sales_progress(
        principal, workspace_id, plan_id, version
    )
