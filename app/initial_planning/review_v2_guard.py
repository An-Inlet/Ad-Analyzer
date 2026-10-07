"""Fresh v2 provenance on every forward path; never historical reconciliation."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning.clock import effective_now
from app.initial_planning.review_contracts import InitialPreviewReviewGuard
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.initial_planning.review_v2_api_contracts import InitialPreviewExecutionRuntime
from app.initial_planning.review_v2_export import bind_execution_proof
from app.initial_planning.review_v2_models import InitialPreviewExecutionProofRow
from app.initial_planning.review_v2_owned import current_preview, policy_pair, unavailable
from app.publication.customer_authority import bind_authority
from app.publication.execution_models import ProviderExecutionReview


def values(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def guard_for(
    runtime: InitialPreviewExecutionRuntime,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
) -> InitialPreviewReviewGuard:
    def guard(
        db: Session, wid: int, review_id: str, actor: str, clock: Callable[[], datetime]
    ) -> None:
        fresh = replace(runtime, planning=replace(runtime.planning, clock=clock))
        authorize = bind_authority(principal, provider)
        authorize(db, wid, actor)
        row = db.get(ProviderExecutionReview, review_id, populate_existing=True)
        link = db.get(
            InitialPreviewReviewLink, review_id, populate_existing=True, with_for_update=True
        )
        saved = db.get(
            InitialPreviewExecutionProofRow,
            (review_id, wid),
            populate_existing=True,
            with_for_update=True,
        )
        if (
            row is None
            or link is None
            or saved is None
            or row.workspace_id != wid
            or link.workspace_id != wid
            or row.actor != actor
            or link.actor_id != actor
            or actor != principal.user.id
            or link.original_session_digest != principal.session.digest
            or link.preview_id is None
            or row.initial_preview_origin_id != link.preview_id
            or row.candidate_provenance_required
            or row.automatic_authority_required
        ):
            raise unavailable()
        value, preview, intent = current_preview(
            db, principal, provider, wid, link.preview_id, fresh
        )
        try:
            proof = bind_execution_proof(values(saved), values(link), values(preview), values(row))
        except (ValueError, TypeError, KeyError):
            raise unavailable() from None
        planning, _ = policy_pair(
            db, wid, value, preview, intent, proof.execution_mandate, actor, fresh, clock
        )
        if planning.model_dump() != proof.planning_mandate.model_dump():
            raise unavailable()
        authorize(db, wid, actor)
        if effective_now(db, fresh.planning) >= proof.expires_at:
            raise unavailable()

    return guard
