"""Strict preview-version dispatch; erased v2 provenance never becomes v1/manual."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning.models import PreviewRow
from app.initial_planning.review_contracts import InitialPreviewReviewGuard
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.initial_planning.review_v2_api_contracts import InitialPreviewExecutionRuntime
from app.initial_planning.review_v2_owned import unavailable
from app.initial_planning.runtime import InitialPlanningRuntime
from app.publication.customer_authority import bind_authority
from app.publication.customer_optimization_contracts import CustomerOptimizationRuntime


def guard_for(
    planning: InitialPlanningRuntime,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    optimization: CustomerOptimizationRuntime,
) -> InitialPreviewReviewGuard:
    from app.initial_planning.review_bridge import guard_for as v1
    from app.initial_planning.review_v2_guard import guard_for as v2

    old = v1(planning, principal, provider)
    new = v2(InitialPreviewExecutionRuntime(planning, optimization), principal, provider)

    def guard(db: Session, wid: int, rid: str, actor: str, clock: Callable[[], datetime]) -> None:
        bind_authority(principal, provider)(db, wid, actor)
        link = db.get(InitialPreviewReviewLink, rid, populate_existing=True)
        if link is None or link.workspace_id != wid or link.preview_id is None:
            raise unavailable()
        preview = db.get(PreviewRow, link.preview_id, populate_existing=True)
        if preview is None or preview.workspace_id != wid:
            raise unavailable()
        version = preview.document.get("schema_version")
        if version == "inlet.initial-efficiency-preview.v1":
            old(db, wid, rid, actor, clock)
        elif version == "inlet.initial-efficiency-preview.v2":
            new(db, wid, rid, actor, clock)
        else:
            raise unavailable()

    return guard
