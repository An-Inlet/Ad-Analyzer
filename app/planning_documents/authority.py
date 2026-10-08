"""Planning-local one-shot identity refresh; no provider IO while local locks are held."""

import time
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal, guard_customer_mutation
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession, CustomerUser

AUTHORITY_MAX_AGE_SECONDS = 5.0
OWNER_ROLES = frozenset({"owner"})
READ_ROLES = frozenset({"owner", "admin", "analyst", "viewer"})


@dataclass(frozen=True)
class IdentityFact:
    user_id: str
    issuer: str
    subject: str
    session_digest: str
    authenticated_at: int
    completed_monotonic: float


def refresh(principal: CustomerPrincipal, provider: IdentityProvider) -> IdentityFact:
    """Caller has released its preparation transaction before invoking this function."""
    identity = (
        principal.user.id,
        principal.user.issuer,
        principal.user.subject,
        principal.session.digest,
        principal.session.authenticated_at,
    )
    if identity[1] != provider.issuer:
        raise HTTPException(401, "customer authentication required")
    provider.check_active(identity[2], identity[4])
    return IdentityFact(*identity, completed_monotonic=time.monotonic())


def _same(principal: CustomerPrincipal, fact: IdentityFact) -> bool:
    return (
        principal.user.id,
        principal.user.issuer,
        principal.user.subject,
        principal.session.digest,
        principal.session.authenticated_at,
    ) == (fact.user_id, fact.issuer, fact.subject, fact.session_digest, fact.authenticated_at)


def lock(
    db: Session,
    principal: CustomerPrincipal,
    workspace_id: int,
    fact: IdentityFact,
    *,
    roles: frozenset[str] = OWNER_ROLES,
) -> CustomerPrincipal:
    if not _same(principal, fact):
        raise HTTPException(401, "customer identity changed")
    guard_customer_mutation(db, principal, workspace_id, allowed_roles=roles)
    # The request principal may be detached. Validate rows refreshed in THIS locked
    # transaction, never the stale objects that were used for external identity IO.
    user = db.get(CustomerUser, fact.user_id, populate_existing=True)
    session = db.get(CustomerSession, fact.session_digest, populate_existing=True)
    if user is None or session is None:
        raise HTTPException(401, "customer authentication required")
    current = CustomerPrincipal(user, session)
    final(current, fact)
    return current


def final(principal: CustomerPrincipal, fact: IdentityFact) -> None:
    """Mandatory AFTER all plan/goal/source lock waits, immediately before acceptance."""
    if (
        not _same(principal, fact)
        or principal.user.status != "active"
        or principal.session.user_id != fact.user_id
        or principal.session.revoked_at is not None
    ):
        raise HTTPException(401, "customer authentication required")
    age = time.monotonic() - fact.completed_monotonic
    if not 0 <= age <= AUTHORITY_MAX_AGE_SECONDS or principal.session.expires_at <= time.time():
        raise HTTPException(409, "planning_authority_expired")
