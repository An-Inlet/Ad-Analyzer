"""Bind the original customer session to every server runtime transaction boundary."""

from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession, CustomerUser
from app.publication.service import owner


def bind_authority(
    principal: CustomerPrincipal, provider: IdentityProvider
) -> Callable[[Session, int, str], None]:
    user_id, session_digest = principal.user.id, principal.session.digest
    issuer, subject = principal.user.issuer, principal.user.subject

    def authorize(db: Session, wid: int, actor: str) -> None:
        if actor != user_id:
            raise HTTPException(401, "original customer session required")
        user = db.get(CustomerUser, user_id, populate_existing=True)
        session = db.get(CustomerSession, session_digest, populate_existing=True)
        if (
            user is None
            or session is None
            or (user.issuer, user.subject) != (issuer, subject)
            or session.user_id != user_id
        ):
            raise HTTPException(401, "original customer session required")
        lock_customer_mutation(db, CustomerPrincipal(user, session), wid, provider)
        if (user.issuer, user.subject) != (issuer, subject):
            raise HTTPException(401, "original customer identity changed")
        owner(db, wid, user_id)

    return authorize
