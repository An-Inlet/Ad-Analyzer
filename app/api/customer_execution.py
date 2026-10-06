"""Customer execution intent APIs; no client-controlled runtime, proof or provider request."""

from collections.abc import Callable
from dataclasses import replace
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.api.customer_optimization import Runtime as OptimizationRuntime
from app.campaign_review.contracts import MediaStore
from app.campaign_review.storage import get_media_store
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.executors.google_publication import GooglePublicationUnavailable
from app.publication import (
    activation,
    activation_review,
    coordinator,
    execution_mandates,
    optimization,
    provider_service,
)
from app.publication import customer_intents as intents
from app.publication import customer_optimization as opt
from app.publication.customer_authority import bind_authority
from app.publication.customer_runtime import (
    CustomerExecutionRuntime,
    get_customer_execution_runtime,
)
from app.publication.customer_schemas import (
    ActivationIntent,
    CatalogIntent,
    ConsentIntent,
    CreationIntent,
    ExactApproval,
    PolicyEdit,
    PolicyIntent,
    ReconcileIntent,
)
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionMandate,
    ProviderExecutionRun,
)
from app.publication.provider_contracts import ProviderPublishPlan
from app.publication.service import owner

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/execution", tags=["customer"])
Runtime = Annotated[CustomerExecutionRuntime | None, Depends(get_customer_execution_runtime)]
Store = Annotated[MediaStore, Depends(get_media_store)]


def get_execution_media_factory() -> Callable[[], MediaStore]:
    """Resolve media only for operations that actually use creative assets."""
    return get_media_store


MediaFactory = Annotated[Callable[[], MediaStore], Depends(get_execution_media_factory)]


def bound(
    runtime: CustomerExecutionRuntime | None, principal: Any, provider: Any
) -> CustomerExecutionRuntime:
    server = intents.require_runtime(runtime)
    authorize = bind_authority(principal, provider)
    creation = replace(server.creation, authorize=authorize)
    activation_runtime = server.activation
    if activation_runtime is not None:
        activation_runtime = replace(
            activation_runtime, review=replace(activation_runtime.review, creation=creation)
        )
    return replace(server, creation=creation, activation=activation_runtime)


def read_access(db: Database, principal: Any, wid: int, response: Response) -> None:
    owner(db, wid, principal.user.id)
    response.headers["Cache-Control"] = "no-store"


@router.get("/capabilities")
def capabilities(
    workspace_id: int, principal: Principal, db: Database, runtime: Runtime, response: Response
) -> dict[str, Any]:
    read_access(db, principal, workspace_id, response)
    available = runtime is not None and (
        runtime.creation.environment != "live" or runtime.creation.live_enabled
    )
    return {
        "environment": runtime.creation.environment if runtime else None,
        "providers": [
            {
                "platform": platform,
                "available": bool(
                    available and runtime and runtime.catalog and platform == "google_ads"
                ),
                "reason": (
                    None
                    if available and runtime and runtime.catalog
                    else "named_configuration_catalog_unavailable"
                )
                if platform == "google_ads" and available
                else (
                    "provider_configuration_producer_unavailable"
                    if available
                    else "provider_execution_not_configured"
                ),
            }
            for platform in ("google_ads", "meta_ads", "tiktok_ads")
        ],
        "activation_available": bool(available and runtime and runtime.activation),
        "scope": "contract_test_no_provider_changes"
        if runtime and runtime.creation.environment == "contract_test"
        else "separate_exact_consent_required",
    }


@router.get("/mandates")
def list_mandates(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    read_access(db, principal, workspace_id, response)
    rows = db.scalars(
        select(ProviderExecutionMandate)
        .where(ProviderExecutionMandate.workspace_id == workspace_id)
        .order_by(ProviderExecutionMandate.id)
        .limit(100)
    )
    return [intents.policy_view(db, row) for row in rows]


@router.post("/mandates", status_code=201)
def create_mandate(
    workspace_id: int,
    body: PolicyIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    server.creation.authorize(db, workspace_id, principal.user.id)
    p = intents.policy(db, workspace_id, body, server)
    row = execution_mandates.revise(db, workspace_id, p, principal.user.id, server.clock)
    response.headers["Cache-Control"] = "no-store"
    return intents.policy_view(db, row)


@router.put("/mandates/{mandate_id}")
def edit_mandate(
    workspace_id: int,
    mandate_id: str,
    body: PolicyEdit,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    server.creation.authorize(db, workspace_id, principal.user.id)
    p = intents.policy(db, workspace_id, body.intent, server)
    row = execution_mandates.revise(
        db,
        workspace_id,
        p,
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
    optimization_runtime: OptimizationRuntime,
    response: Response,
) -> dict[str, Any]:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    _, mandate_row = execution_mandates.owned(db, workspace_id, mandate_id)
    if "existing_campaign_optimize" in execution_mandates.policy(db, mandate_row).allowed_purposes:
        from app.api.customer_optimization import consent as optimization_consent

        return optimization_consent(
            workspace_id, mandate_id, body, principal, provider, db, optimization_runtime, response
        )
    server = bound(runtime, principal, provider)
    server.creation.authorize(db, workspace_id, principal.user.id)
    execution_mandates.consent(
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


@router.post("/mandates/{mandate_id}/revoke")
def revoke(
    workspace_id: int,
    mandate_id: str,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    # Local authority can always be stopped, even when provider runtime is unavailable.
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    execution_mandates.suspend(db, workspace_id, mandate_id, principal.user.id, revoke=True)
    response.headers["Cache-Control"] = "no-store"
    return {
        "state": "revoked",
        "external_effects_recalled": False,
        "unresolved_reservations_released": False,
    }


@router.post("/configuration-options")
def options(
    workspace_id: int,
    body: "CatalogIntent",
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    catalog = intents.discover(db, workspace_id, body.draft_id, principal.user.id, media, server)
    response.headers["Cache-Control"] = "no-store"
    return {
        "draft_revision": catalog.request.draft_revision,
        "expires_at": catalog.expires_at.isoformat(),
        "options": [
            {"id": item.identifier(catalog.request), "name": item.label} for item in catalog.options
        ],
        "unavailable_reasons": catalog.unavailable_reasons,
    }


@router.post("/creation-reviews", status_code=201)
def prepare_creation(
    workspace_id: int,
    body: CreationIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    catalog = intents.discover(db, workspace_id, body.draft_id, principal.user.id, media, server)
    selected = next(
        (
            item
            for item in catalog.options
            if item.identifier(catalog.request) == body.google.catalog_option_id
        ),
        None,
    )
    if selected is None:
        raise intents.unavailable("named_configuration_selection_changed")
    try:
        fields = intents.google_fields(
            db, workspace_id, body, principal.user.id, media, server, selected
        )
        record = provider_service.prepare_google(
            db,
            workspace_id,
            body.draft_id,
            fields,
            principal.user.id,
            media,
            server.google_qualification,
            server.google_context,
            server.clock,
            authorize=server.creation.authorize,
        )
    except (GooglePublicationUnavailable, ValueError):
        raise intents.unavailable("provider_configuration_unqualified") from None
    server.creation.authorize(db, workspace_id, principal.user.id)
    binding = intents.binding(db, workspace_id, body.mandate_id, body.mandate_revision)
    row = coordinator.prepare_creation(
        db,
        workspace_id,
        ProviderPublishPlan.model_validate(record.plan),
        binding,
        principal.user.id,
        media,
        server.creation,
        server.clock,
    )
    response.headers["Cache-Control"] = "no-store"
    return intents.review_view(row, db)


@router.post("/activation-reviews", status_code=201)
def prepare_activation(
    workspace_id: int,
    body: ActivationIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    if server.activation is None:
        raise intents.unavailable("activation_runtime_unavailable")
    server.creation.authorize(db, workspace_id, principal.user.id)
    binding = intents.binding(db, workspace_id, body.mandate_id, body.mandate_revision)
    row = activation_review.prepare_activation(
        db,
        workspace_id,
        body.parent_run_id,
        binding,
        principal.user.id,
        media,
        server.activation.review,
        server.clock,
    )
    response.headers["Cache-Control"] = "no-store"
    return intents.review_view(row, db)


@router.get("/reviews/{review_id}")
def get_review(
    workspace_id: int, review_id: str, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    read_access(db, principal, workspace_id, response)
    return intents.review_view(intents.review(db, workspace_id, review_id), db)


@router.post("/reviews/{review_id}/approval")
def approve(
    workspace_id: int,
    review_id: str,
    body: ExactApproval,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    optimization_runtime: OptimizationRuntime,
    media_factory: MediaFactory,
    response: Response,
) -> dict[str, Any]:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    row = intents.review(db, workspace_id, review_id)
    kind = opt.purpose(row)
    if kind == "existing_campaign_optimize":
        server_opt = opt.bind(optimization_runtime, principal, provider)
        runtime_opt = server_opt.execution
        optimization.approve_optimization(
            db,
            workspace_id,
            review_id,
            body.review_digest,
            body.plan_digest,
            principal.user.id,
            runtime_opt,
            server_opt.clock,
        )
        response.headers["Cache-Control"] = "no-store"
        return {"state": "approved", "provider_dispatch_complete": False}
    server = bound(runtime, principal, provider)
    media = media_factory()
    server.creation.authorize(db, workspace_id, principal.user.id)
    row = intents.review(db, workspace_id, review_id)
    if row.document.get("purpose") == "activate":
        if server.activation is None:
            raise intents.unavailable("activation_runtime_unavailable")
        activation_review.approve_activation(
            db,
            workspace_id,
            review_id,
            body.review_digest,
            body.plan_digest,
            principal.user.id,
            media,
            server.activation.review,
            server.clock,
        )
    else:
        coordinator.approve_creation(
            db,
            workspace_id,
            review_id,
            body.review_digest,
            body.plan_digest,
            principal.user.id,
            media,
            server.creation,
            server.clock,
        )
    response.headers["Cache-Control"] = "no-store"
    return {"state": "approved", "provider_dispatch_complete": False}


@router.post("/reviews/{review_id}/runs", status_code=201)
def start_run(
    workspace_id: int,
    review_id: str,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    optimization_runtime: OptimizationRuntime,
    media_factory: MediaFactory,
    response: Response,
) -> dict[str, Any]:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    row = intents.review(db, workspace_id, review_id)
    kind = opt.purpose(row)
    if kind == "existing_campaign_optimize":
        server_opt = opt.bind(optimization_runtime, principal, provider)
        runtime_opt = server_opt.execution
        result = optimization.create_run(
            db, workspace_id, review_id, principal.user.id, runtime_opt, server_opt.clock
        )
        response.headers["Cache-Control"] = "no-store"
        return intents.run_view(db, result)
    server = bound(runtime, principal, provider)
    media = media_factory()
    server.creation.authorize(db, workspace_id, principal.user.id)
    row = intents.review(db, workspace_id, review_id)
    if row.document.get("purpose") == "activate":
        if server.activation is None:
            raise intents.unavailable("activation_runtime_unavailable")
        run = activation_review.create_run(
            db,
            workspace_id,
            review_id,
            principal.user.id,
            media,
            server.activation.review,
            server.clock,
        )
    else:
        run = coordinator.create_run(
            db, workspace_id, review_id, principal.user.id, media, server.creation, server.clock
        )
    response.headers["Cache-Control"] = "no-store"
    return intents.run_view(db, run)


@router.get("/runs")
def list_runs(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    read_access(db, principal, workspace_id, response)
    return [
        intents.run_view(db, row)
        for row in db.scalars(
            select(ProviderExecutionRun)
            .where(ProviderExecutionRun.workspace_id == workspace_id)
            .order_by(ProviderExecutionRun.created_at.desc(), ProviderExecutionRun.id)
            .limit(100)
        )
    ]


@router.get("/runs/{run_id}")
def get_run(
    workspace_id: int, run_id: str, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    read_access(db, principal, workspace_id, response)
    return intents.run_view(db, intents.run(db, workspace_id, run_id))


@router.post("/runs/{run_id}/advance")
def advance(
    workspace_id: int,
    run_id: str,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    optimization_runtime: OptimizationRuntime,
    media_factory: MediaFactory,
    response: Response,
) -> dict[str, Any]:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    run = intents.run(db, workspace_id, run_id)
    row = intents.review(db, workspace_id, run.review_id)
    kind = opt.purpose(row)
    if kind == "existing_campaign_optimize":
        server_opt = opt.bind(optimization_runtime, principal, provider)
        runtime_opt = server_opt.execution
        opt_claim = optimization.claim_step(
            db, workspace_id, run_id, principal.user.id, runtime_opt, server_opt.clock
        )
        if opt_claim is not None:
            optimization.execute_claim(
                db, opt_claim, principal.user.id, runtime_opt, server_opt.clock
            )
        runtime_opt.authorize(db, workspace_id, principal.user.id)
        response.headers["Cache-Control"] = "no-store"
        return intents.run_view(db, intents.run(db, workspace_id, run_id))
    server = bound(runtime, principal, provider)
    media = media_factory()
    server.creation.authorize(db, workspace_id, principal.user.id)
    run = intents.run(db, workspace_id, run_id)
    if intents.review(db, workspace_id, run.review_id).document.get("purpose") == "activate":
        if server.activation is None:
            raise intents.unavailable("activation_runtime_unavailable")
        claim = activation.claim_step(
            db, workspace_id, run_id, principal.user.id, media, server.activation, server.clock
        )
        if claim is not None:
            activation.execute_claim(
                db, claim, principal.user.id, media, server.activation, server.clock
            )
    else:
        creation_claim = coordinator.claim_creation_step(
            db, workspace_id, run_id, principal.user.id, media, server.creation, server.clock
        )
        if creation_claim is not None:
            coordinator.execute_claim(
                db, creation_claim, principal.user.id, media, server.creation, server.clock
            )
    server.creation.authorize(db, workspace_id, principal.user.id)
    response.headers["Cache-Control"] = "no-store"
    return intents.run_view(db, intents.run(db, workspace_id, run_id))


@router.post("/runs/{run_id}/reconcile")
def reconcile(
    workspace_id: int,
    run_id: str,
    body: ReconcileIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    optimization_runtime: OptimizationRuntime,
    response: Response,
) -> dict[str, Any]:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    run = intents.run(db, workspace_id, run_id)
    row = intents.review(db, workspace_id, run.review_id)
    kind = opt.purpose(row)
    if kind == "existing_campaign_optimize":
        server_opt = opt.bind(optimization_runtime, principal, provider)
        runtime_opt = server_opt.execution
        original = db.get(ProviderExecutionAttempt, body.attempt_id)
        if original is None or original.workspace_id != workspace_id or original.run_id != run_id:
            raise HTTPException(404, "original execution attempt unavailable")
        optimization.reconcile_attempt(
            db, workspace_id, body.attempt_id, runtime_opt, server_opt.clock
        )
        runtime_opt.authorize(db, workspace_id, principal.user.id)
        response.headers["Cache-Control"] = "no-store"
        return intents.run_view(db, intents.run(db, workspace_id, run_id))
    server = bound(runtime, principal, provider)
    server.creation.authorize(db, workspace_id, principal.user.id)
    run = intents.run(db, workspace_id, run_id)
    attempt = db.get(ProviderExecutionAttempt, body.attempt_id)
    if attempt is None or attempt.workspace_id != workspace_id or attempt.run_id != run_id:
        raise HTTPException(404, "original execution attempt unavailable")
    if intents.review(db, workspace_id, run.review_id).document.get("purpose") == "activate":
        if server.activation is None:
            raise intents.unavailable("activation_runtime_unavailable")
        activation.reconcile_attempt(
            db, workspace_id, body.attempt_id, server.activation, server.clock
        )
    else:
        coordinator.reconcile_attempt(
            db, workspace_id, body.attempt_id, server.creation, server.clock
        )
    server.creation.authorize(db, workspace_id, principal.user.id)
    response.headers["Cache-Control"] = "no-store"
    return intents.run_view(db, intents.run(db, workspace_id, run_id))


@router.post("/runs/{run_id}/cancel")
def cancel(
    workspace_id: int,
    run_id: str,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    from app.publication.customer_runtime import utc_now

    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    coordinator.cancel_creation(db, workspace_id, run_id, principal.user.id, utc_now)
    response.headers["Cache-Control"] = "no-store"
    return intents.run_view(db, intents.run(db, workspace_id, run_id))


@router.get("/attempts/{attempt_id}/receipt")
def receipt(
    workspace_id: int, attempt_id: str, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    read_access(db, principal, workspace_id, response)
    result = coordinator.read_owned_outcome_receipt(db, workspace_id, attempt_id, principal.user.id)
    if result is None:
        return {"state": "awaiting_evidence"}
    return {"receipt": result.model_dump(mode="json"), "causal_effect_time": "unavailable"}


@router.post("/draft-context")
def draft_context(
    workspace_id: int,
    body: CatalogIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    from app.ads.models import AdvertisingAccount
    from app.campaign_review import service as sources
    from app.mandates import service as simulation

    server = bound(runtime, principal, provider)
    server.creation.authorize(db, workspace_id, principal.user.id)
    row, artifact = sources.preview(db, workspace_id, body.draft_id, media, server.clock())
    if row.approved_by is None:
        raise intents.unavailable("current_approved_creative_required")
    previous = simulation.policy(
        db, simulation.owned(db, workspace_id, artifact.definition.mandate_id)
    )
    proposal = PolicyIntent(
        goal_id=previous.goal_id,
        goal_revision=previous.goal_revision,
        account_ids=[a.account_id for a in previous.accounts],
        currency=previous.currency,
        time_zone=previous.time_zone,
        starts_at=previous.starts_at,
        ends_at=previous.ends_at,
        total_cap_micros=previous.total_cap_micros,
        per_plan_cap_micros=previous.per_action_cap_micros,
        positive_change_cap_micros=previous.positive_change_cap_micros,
        action_limit=max(1, previous.action_limit),
        cooldown_seconds=previous.cooldown_seconds,
        aggressiveness_percent=5,
        allowed_purposes=["create_paused", "activate"],
    )
    names = list(
        db.scalars(
            select(AdvertisingAccount.name)
            .where(
                AdvertisingAccount.workspace_id == workspace_id,
                AdvertisingAccount.id.in_(proposal.account_ids),
            )
            .order_by(AdvertisingAccount.id)
        )
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "draft": sources.view(row),
        "proposal": proposal.model_dump(mode="json"),
        "account_names": names,
        "proposal_is_authority": False,
        "explanation": (
            "Review these proposed limits separately. "
            "Prior simulation approval is not execution consent."
        ),
    }
