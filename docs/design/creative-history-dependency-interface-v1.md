# Creative Historical Dependency V1

Preparatory complete historical integrity support only; do not register v5 or
change service/repository/retained-source dispatch. Genuine creative documents and
proofs are now available as pure values, not customer-generation capability.

Extend RetainedSourceWitness with local_creative_basis_v1. Its exact scope is
key=local:creative:basis and account_id/connection_id/store_id all None. Preserve
all existing reporting/commerce rules and byte representations. PlanDependencyRow
already supports this kind and scope; no migration is needed.

Add `creative_history.py` with:

- `creative_local_witness(document)->RetainedSourceWitness`: fully revalidate a
  genuine exact-v5 PlanVersion and its typed proof. Set exact document workspace,
  plan_id/version/privacy; source_binding_digest=proof.source_binding_digest(),
  document_digest=proof.digest(), source_revision=proof.schema_version;
  observed_at=document.generated_at, expires_at=document.valid_until. This is the
  immutable document-basis commitment at generation, not a claim that SQL rows or
  bytes were re-read at that timestamp. Required even for zero selected images.
- `validate_creative_local_dependency(document,dependencies)->None`: identify rows
  with either the reserved key OR new kind; require exactly one and compare its
  complete normalized persisted fields to the expected witness. Reject missing,
  duplicate, wrong key/kind/scope/order-derived hash/time/revision and extra creative
  witness rows. This validates the creative subset only; caller must validate the
  complete remaining dependency set and stored document digest.

Extend validate_selected_historical_dependencies to recognize exact v4/v5 via the
reviewed selected contract (not registration), retaining selected/traffic proof
semantics. V5 requires the above exact creative dependency and consumes it before
checking all remaining dependencies. V4 rejects it. Increase dependency bound by
exactly one only for v5; missing/extra rows never silently pass. Preserve canonical
local_reporting_v3, commerce, normal EvidenceRef dependency checks and actual
immutable selected capture/raw-traffic graph verification. No fake v4 document.
Use local imports where required to avoid existing retained_sources/history cycles.

Historical reads validate original proof/complete dependencies without current
MediaObject presence, storage calls, new identity-provider calls or paid_work.
Existing caller READ_ROLES/privacy authority and storage document digest remain
mandatory. Ordinary image metadata/blob loss must not rewrite archived inspection;
semantic workspace privacy erasure still removes the version-owned dependency
set. Current metadata checking and atomic persistence are separate future ports.

Tests include genuine v5 document proof with both empty and multiple images,
complete v4 compatibility, absent/extra/reordered/tampered commitments/dependencies,
creator/time commitment changes, current image rows removed without invalidating
immutable proof, original observation timestamps retained, and missing selected
capture/raw evidence rejected through the genuine historical path. If SQL fixtures
are required, use both databases and coordinate the slot. No advertising writes,
service dispatch, new historical paid restriction or runtime activation. Whole
Ruff/configured mypy and exact byte/digest compatibility checks required.
