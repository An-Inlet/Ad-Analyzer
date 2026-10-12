"""Exact candidate retained dispatch; original v5-only public wrappers stay closed."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.planning_documents.constraint_policy import is_constraint_policy
from app.planning_documents.creative_retained_sources import (
    _capture_creative_retained_sources,
    _recheck_creative_retained_sources,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.retained_sources import RetainedSourcesChanged, RetainedSourceWitness


def _candidate(document: PlanVersion) -> PlanVersion:
    document = PlanVersion.model_validate(document)
    if not is_constraint_policy(document.policy_version, document.generator_version):
        raise RetainedSourcesChanged("proof_unavailable")
    return document


def capture_constraint_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    document: PlanVersion,
    now: datetime,
) -> tuple[RetainedSourceWitness, ...]:
    return _capture_creative_retained_sources(
        db, principal=principal, document=_candidate(document), now=now
    )


def recheck_constraint_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    document: PlanVersion,
    dependencies: Sequence[PlanDependencyRow],
    now: datetime,
) -> None:
    _recheck_creative_retained_sources(
        db, principal=principal, document=_candidate(document), dependencies=dependencies, now=now
    )
