# Standalone Creative Retained Proof V1

Preparatory pure contracts only; do not change PlanVersion, EvidenceRef,
RetainedSourceWitness, SQL dependencies, runtime or policy registration yet.
This follows the private collection interface d7f09f8 and standalone creative
basis. Proof parsing validates structure, never authenticates an observation.

Add a document-safe leaf module `creative_retained_proof.py`:

- `CreativeImageCommitmentV1(media_id:Id,row_identity_digest:Digest)`.
- `CreativeRetainedProofV1` with fixed schema
  `inlet.creative-retained-proof.v1`, `basis:CreativeBasisV1`, and ordered
  `images:tuple[CreativeImageCommitmentV1,...]` bounded30. Require exact one-to-one
  media ID/order equality with basis.images; duplicate, extra and missing entries
  fail. Empty selections retain an explicit proof with empty image commitments.
  Use existing frozen NoAuthority primitives and recursive revalidation.
- `assert_inputs(inputs:PlanInputRevision,privacy_revision:int)` revalidates values;
  requires explicit inputs.creative exactly equal to basis.requested, same
  workspace, confirmed-goal currency, and strict nonnegative privacy revision.
- `source_binding_digest()` uses the existing domain-separated fingerprint over
  schema/workspace/privacy, exact requested input digest, and complete ordered
  image commitments. It excludes observation times and product visual assessment
  claims beyond the fixed not_assessed semantics. `digest()` commits the complete
  proof including the basis and original image observation times.

A factory `creative_proof_from_collection(collection,ticket)` locally imports
private collection/ticket classes, revalidates them, calls collection.assert_ticket,
then creates every row_identity_digest from the full row.identity() using the
existing fingerprint. Revalidate/assert_inputs before returning. Preserve exact
image observation times. Never put created_by, ticket/session digest or raw bytes
in the public proof; identity commitments are hashes. No policy/authority inference
from the proof's schema or valid hash.

The source-binding commitment is not a new availability promise: bytes were checked
at their recorded observation times. Future finalization must compare the private
collection's complete actual SQL rows (including creator/time), enforce original
session/goal/paid/privacy, and persist exact proof/dependencies atomically. Future
history checks retained immutable proof and complete dependency commitments with
READ_ROLES/privacy; it does not acquire a paid-work requirement or repeat byte I/O.
Ordinary current metadata/storage changes and semantic privacy erasure remain
separate concerns. None of those consumers are implemented in this package.

Test complete/empty/ordered/multiple proof; exact input/workspace/currency/privacy;
creator-only and created_at-only changes alter row commitments; changing only
observed_at changes full proof digest but not source-binding digest; unsafe copied
models and strict coercion/unknown keys fail; JSON roundtrip/order/import-cycle
safety. Do not claim hash commitments establish independent ownership. Run whole
Ruff/configured mypy and focused tests. No migration, runtime or default changes.
