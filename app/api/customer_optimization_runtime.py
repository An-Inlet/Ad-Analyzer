"""Original-session configured optimization with explicit legacy fixture compatibility."""

from collections.abc import Iterator
from dataclasses import replace
from typing import Annotated

from fastapi import Depends

from app.customers.access import Database, Principal, Provider
from app.optimization_candidates.review_bridge import guard_for
from app.production_runtime.candidate_assembly import configured_candidates
from app.production_runtime.optimization_assembly import configured_optimization
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    get_customer_optimization_runtime,
)
from app.settings import settings

Legacy = Annotated[CustomerOptimizationRuntime | None, Depends(get_customer_optimization_runtime)]


def get_configured_customer_optimization_runtime(
    db: Database,
    principal: Principal,
    provider: Provider,
    legacy: Legacy,
) -> Iterator[CustomerOptimizationRuntime | None]:
    if legacy is not None:
        yield legacy
        return
    with configured_optimization(db, principal, provider, settings) as runtime:
        if runtime is None:
            yield None
            return

        def candidate_guard(session, wid, identifier, actor, clock):  # type: ignore[no-untyped-def]
            # Resolve only for protected candidate reviews. Missing candidate setup
            # must not alter manual or V2 preview execution availability.
            from fastapi import HTTPException

            from app.optimization_candidates.review_models import CandidateReviewLink

            link = session.get(CandidateReviewLink, identifier)
            if link is None or link.original_session_digest != principal.session.digest:
                raise HTTPException(409, "candidate_original_session_required")
            with configured_candidates(
                session, principal, provider, settings, existing_native=runtime
            ) as bundle:
                if bundle is None:
                    raise HTTPException(409, "candidate_runtime_unavailable")
                guard_for(bundle.review)(session, wid, identifier, actor, clock)

        yield replace(
            runtime, execution=replace(runtime.execution, candidate_review_guard=candidate_guard)
        )
