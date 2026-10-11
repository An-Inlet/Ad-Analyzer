"""Original scalar commitment preserves discovery bytes without an ORM principal."""

from typing import Any

import pytest
from app.planning_documents.google_budget_owner_discovery import owner_selection_id
from app.planning_documents.google_budget_owner_selection import original_owner_selection_id

from tests.test_google_budget_owner_discovery_contracts import setup


def test_original_scalar_commitment_preserves_pre_extraction_golden() -> None:
    witness, principal, source = setup()
    values = dict(
        actor_id=principal.user.id,
        session_digest=principal.session.digest,
        authenticated_at=principal.session.authenticated_at,
        source=source,
        witness=witness,
    )
    expected = "fadc61111232ea32b91e34aec2130023bae1743b0a4a269f9b3a39642cd66404"
    assert original_owner_selection_id(**values) == expected
    assert owner_selection_id(principal=principal, source=source, witness=witness) == expected
    # Retained scalars remain original even when a current principal changes.
    principal.session.digest = "c" * 64
    principal.session.authenticated_at += 1
    assert original_owner_selection_id(**values) == expected
    assert owner_selection_id(principal=principal, source=source, witness=witness) != expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor_id", b"a" * 32),
        ("actor_id", "invalid"),
        ("session_digest", b"b" * 64),
        ("session_digest", "invalid"),
        ("authenticated_at", True),
        ("authenticated_at", "123"),
        ("authenticated_at", 123.0),
        ("authenticated_at", -1),
    ],
)
def test_original_scalar_commitment_refuses_coercion(field: str, value: Any) -> None:
    witness, principal, source = setup()
    values = dict(
        actor_id=principal.user.id,
        session_digest=principal.session.digest,
        authenticated_at=principal.session.authenticated_at,
        source=source,
        witness=witness,
    )
    values[field] = value
    with pytest.raises(ValueError):
        original_owner_selection_id(**values)
