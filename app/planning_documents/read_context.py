"""One-operation planning read contexts: identity IO before opening database sessions."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession, CustomerUser
from app.planning_documents import authority


def snapshot(principal: CustomerPrincipal) -> CustomerPrincipal:
    """Copy loaded scalar identity only; never trigger lazy SQL during external refresh."""
    user_fields = ("id", "issuer", "subject", "status")
    session_fields = ("digest", "user_id", "authenticated_at", "expires_at", "revoked_at")
    if (
        set(user_fields) & inspect(principal.user).unloaded
        or set(session_fields) & inspect(principal.session).unloaded
    ):
        raise HTTPException(401, "loaded original customer identity required")
    return CustomerPrincipal(
        CustomerUser(**{field: getattr(principal.user, field) for field in user_fields}),
        CustomerSession(**{field: getattr(principal.session, field) for field in session_fields}),
    )


class PlanningReadContexts:
    """Private to a single collect call; no authority fact crosses a transaction."""

    def __init__(
        self,
        sessions: Callable[[], Session],
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        actor: str,
    ) -> None:
        self.sessions, self.principal, self.provider = sessions, snapshot(principal), provider
        self.workspace_id, self.actor = workspace_id, actor
        self.active: tuple[Session, authority.IdentityFact] | None = None
        if self.principal.user.id != actor:
            raise HTTPException(401, "original customer identity required")

    def authorize(self, db: Session, workspace_id: int, actor: str) -> None:
        active = self.active
        if (
            active is None
            or active[0] is not db
            or (workspace_id, actor) != (self.workspace_id, self.actor)
        ):
            raise HTTPException(401, "current planning read context required")
        current = authority.lock(db, self.principal, workspace_id, active[1])
        authority.final(current, active[1])

    @contextmanager
    def open(self) -> Iterator[Session]:
        if self.active is not None:
            raise HTTPException(409, "nested planning read context unavailable")
        fact = authority.refresh(self.principal, self.provider)
        # Identity refresh has completed before a Session/transaction can be opened.
        with self.sessions() as db:
            self.active = (db, fact)
            try:
                self.authorize(db, self.workspace_id, self.actor)
                yield db
                # Same fact and freshly loaded locked principal after ALL body waits.
                self.authorize(db, self.workspace_id, self.actor)
            finally:
                self.active = None
