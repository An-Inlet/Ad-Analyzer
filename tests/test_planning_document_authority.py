from dataclasses import replace

import pytest
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.planning_documents import authority
from fastapi import HTTPException
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine


def principal() -> CustomerPrincipal:
    return CustomerPrincipal(
        CustomerUser(
            id="a" * 32,
            issuer=FakeProvider().issuer,
            subject="customer",
            email="customer@example.test",
            status="active",
        ),
        CustomerSession(
            digest="b" * 64,
            user_id="a" * 32,
            csrf_digest="c" * 64,
            created_at=10,
            expires_at=1000,
            authenticated_at=10,
            revoked_at=None,
        ),
    )


@pytest.mark.parametrize("age,allowed", [(0, True), (5, True), (5.00001, False), (-1, False)])
def test_final_authority_five_seconds_never_extends(
    age: float, allowed: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    customer = principal()
    fact = authority.IdentityFact(
        customer.user.id,
        customer.user.issuer,
        customer.user.subject,
        customer.session.digest,
        customer.session.authenticated_at,
        100,
    )
    monkeypatch.setattr("app.planning_documents.authority.time.monotonic", lambda: 100 + age)
    monkeypatch.setattr("app.planning_documents.authority.time.time", lambda: 500)
    if allowed:
        authority.final(customer, fact)
    else:
        with pytest.raises(HTTPException) as error:
            authority.final(customer, fact)
        assert error.value.status_code == 409


def test_identity_fact_captures_scalars_before_provider_and_rechecks_revocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer = principal()
    provider = FakeProvider()

    def change(subject: str, authenticated_at: int) -> None:
        customer.user.subject = "changed"

    monkeypatch.setattr(provider, "check_active", change)
    monkeypatch.setattr("app.planning_documents.authority.time.monotonic", lambda: 100)
    monkeypatch.setattr("app.planning_documents.authority.time.time", lambda: 500)
    fact = authority.refresh(customer, provider)
    assert fact.subject == "customer"
    with pytest.raises(HTTPException):
        authority.final(customer, fact)
    customer.user.subject = "customer"
    customer.session.revoked_at = 501
    with pytest.raises(HTTPException):
        authority.final(customer, fact)
    customer.session.revoked_at = None
    customer.session.expires_at = 500
    with pytest.raises(HTTPException) as error:
        authority.final(customer, replace(fact, completed_monotonic=100))
    assert error.value.status_code == 409


@pytest.mark.parametrize("changed", ["issuer", "subject", "authenticated_at"])
def test_detached_principal_cannot_hide_current_identity_change(
    customer_engine: Engine, changed: str
) -> None:
    from tests.test_customer_lifecycle import seed

    with Session(customer_engine) as db:
        detached, wid = seed(db)
        fact = authority.refresh(detached, FakeProvider())
        # Load the fields used by guard and final before detaching.
        assert detached.user.status == "active" and detached.session.user_id == detached.user.id
        assert detached.session.expires_at and detached.session.revoked_at is None
    with Session(customer_engine) as other:
        if changed == "authenticated_at":
            other.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == fact.session_digest)
                .values(authenticated_at=fact.authenticated_at + 1)
            )
        else:
            other.execute(
                update(CustomerUser)
                .where(CustomerUser.id == fact.user_id)
                .values(**{changed: "changed"})
            )
        other.commit()
    with Session(customer_engine) as current, pytest.raises(HTTPException) as error:
        authority.lock(current, detached, wid, fact)
    assert error.value.status_code == 401


def test_lock_returns_current_transaction_identity_for_final_check(customer_engine: Engine) -> None:
    from tests.test_customer_lifecycle import seed

    with Session(customer_engine) as db:
        detached, wid = seed(db)
        fact = authority.refresh(detached, FakeProvider())
        assert detached.user.status == "active" and detached.session.user_id == detached.user.id
        assert detached.session.expires_at and detached.session.revoked_at is None
    with Session(customer_engine) as db:
        current = authority.lock(db, detached, wid, fact)
        assert current.user is db.get(CustomerUser, fact.user_id)
        assert current.session is db.get(CustomerSession, fact.session_digest)
        assert current.user is not detached.user and current.session is not detached.session
        authority.final(current, fact)
