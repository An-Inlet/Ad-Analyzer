"""Opaque lookup binds exact original authority, without returning its inputs."""

from typing import Any

import pytest
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.planning_documents.google_budget_owner_discovery import owner_selection_id
from app.planning_documents.google_budget_owner_discovery_contracts import (
    GoogleBudgetOwnerOptionV1,
    GoogleBudgetOwnersRequestV1,
)
from app.planning_documents.source_contracts import SourceFence

from tests.test_google_budget_owner_contracts import derive, evidence


def setup() -> tuple[Any, CustomerPrincipal, SourceFence]:
    witness = derive(evidence())
    ref = witness.catalog_evidence.reference
    assert ref.account is not None
    source = SourceFence(
        account=ref.account,
        source_revision=ref.source_revision,
        source_binding_digest=ref.source_binding_digest,
        privacy_revision=ref.privacy_revision,
    )
    principal = CustomerPrincipal(
        CustomerUser(id="a" * 32), CustomerSession(digest="b" * 64, authenticated_at=123)
    )
    return witness, principal, source


@pytest.mark.parametrize("field", ["actor", "session", "authenticated"])
def test_opaque_commitment_original_principal(field: str) -> None:
    witness, principal, source = setup()
    original = owner_selection_id(principal=principal, source=source, witness=witness)
    if field == "actor":
        principal.user.id = "c" * 32
    elif field == "session":
        principal.session.digest = "d" * 64
    else:
        principal.session.authenticated_at += 1
    assert owner_selection_id(principal=principal, source=source, witness=witness) != original


@pytest.mark.parametrize(
    "field,value",
    [
        ("privacy_revision", 99),
        ("source_binding_digest", "f" * 64),
        ("source_revision", "different"),
    ],
)
def test_opaque_commitment_rejects_unmatched_source(field: str, value: Any) -> None:
    witness, principal, source = setup()
    with pytest.raises(ValueError):
        owner_selection_id(
            principal=principal, source=source.model_copy(update={field: value}), witness=witness
        )


def test_request_and_option_copied_timestamp_and_boolean_refuse_coercion() -> None:
    witness, _, _ = setup()
    ref = witness.catalog_evidence.reference
    request = GoogleBudgetOwnersRequestV1(
        account_id=ref.account.account_id,
        catalog_composite_digest=witness.catalog_evidence.catalog.composite_digest,
        reporting_window=ref.reporting_window,
    )
    with pytest.raises(ValueError):
        GoogleBudgetOwnersRequestV1.model_validate(request.model_copy(update={"account_id": True}))
    option = GoogleBudgetOwnerOptionV1(
        account_id=ref.account.account_id,
        owner_selection_id="0" * 64,
        expected_observation_digest=witness.digest(),
        expected_owner_facts_digest="1" * 64,
        representative=witness.representative,
        affected_campaigns=witness.affected_campaigns,
        current_amount_micros=witness.current_amount_micros,
        currency=witness.currency,
        observation_started_at=ref.observation_started_at,
        observed_at=ref.observed_at,
        expires_at=ref.expires_at,
    )
    for field, value in (
        ("review_only", 1),
        ("observed_at", 123),
        ("affected_campaigns", (witness.representative, witness.representative)),
    ):
        with pytest.raises(ValueError):
            GoogleBudgetOwnerOptionV1.model_validate(option.model_copy(update={field: value}))
