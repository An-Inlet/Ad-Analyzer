"""Original receipt commitment from private scalars; never current session authority."""

from datetime import UTC

from pydantic import Field

from app.planning_documents.common import Digest, Frozen, Id, fingerprint
from app.planning_documents.google_budget_owner_contracts import GoogleDailyBudgetOwnerWitnessV1
from app.planning_documents.source_contracts import SourceFence


class _OriginalAuthority(Frozen):
    actor_id: Id
    session_digest: Digest
    authenticated_at: int = Field(strict=True, ge=0)


def original_owner_selection_id(
    *,
    actor_id: str,
    session_digest: str,
    authenticated_at: int,
    source: SourceFence,
    witness: GoogleDailyBudgetOwnerWitnessV1,
) -> str:
    """Caller supplies validated original receipt provenance, not a fabricated principal."""
    authority = _OriginalAuthority(
        actor_id=actor_id, session_digest=session_digest, authenticated_at=authenticated_at
    )
    source = SourceFence.model_validate(source)
    witness = GoogleDailyBudgetOwnerWitnessV1.model_validate(witness)
    ref = witness.catalog_evidence.reference
    if (ref.account, ref.source_binding_digest, ref.source_revision, ref.privacy_revision) != (
        source.account,
        source.source_binding_digest,
        source.source_revision,
        source.privacy_revision,
    ):
        raise ValueError("exact witness source required")
    window = ref.reporting_window
    assert window is not None
    return fingerprint(
        "inlet.google-budget-owner-selection.v1",
        dict(
            source=source.model_dump(mode="json"),
            actor=authority.actor_id,
            session_digest=authority.session_digest,
            authenticated_at=authority.authenticated_at,
            composite_digest=witness.catalog_evidence.catalog.composite_digest,
            witness_digest=witness.digest(),
            owner_key=witness.owner_key,
            reporting_starts_at=window.starts_at.astimezone(UTC).isoformat(),
            reporting_ends_at=window.ends_at_exclusive.astimezone(UTC).isoformat(),
        ),
    )
