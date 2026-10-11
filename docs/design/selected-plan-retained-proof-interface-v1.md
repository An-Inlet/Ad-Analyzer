# Selected Plan Retained Proof Interface V1

This implements the reviewed currentness/historical distinction for reserved v4.
No policy registration or runtime activation is implied by the proof DTOs.

## Immutable Proof In The Existing Plan Document

`PlanVersion.selected_reporting_proof: SelectedRetainedProofV1 | None = None`
is omitted when None from nested Python/JSON serialization and canonical/digest
paths. Old plan bytes remain unchanged. The exact v4 policy/generator pair requires
proof plus an explicit input selected_reporting tuple; all other pairs reject
non-null proof. No table or retention period is added.

A proof contains exactly one ordered unique account entry for every full owned
AccountRef in persisted inputs, including explicit-no-capture accounts. Each entry
retains SourceFence, legacy_reporting_digest, selection_head and capture_pin.
Selection head is either None or an atomic strict selection ID/digest/boolean
invalidated record. Chosen capture pins must match an active saved head, full
source/account/privacy and the explicit persisted input selector. Missing/extra/
duplicate account or selector bindings reject the proof.

The account state digest uses a new `inlet.local-reporting-state.v3` domain over
the complete canonical account proof. Its source digest is the SourceFence binding.
`legacy_reporting_digest` and the pin's `campaign_map_digest` are retained opaque
commitments to the original mutable state; historical validation must not claim to
reconstruct old aggregate rows or full campaign maps from these hashes.

Shared SourceFence and selected pin types move to dependency-light modules with
backward explicit re-exports. Python type identity and old canonical bytes stay
unchanged. No old local_reporting_v1/v2 witness changes.

## Current Capture Port

`capture_selected_reporting_pin(db, principal, account, privacy, selector, now)`
returns the complete `SelectedRetainedAccountProofV1`, not merely an opaque digest.
Caller holds fresh original-session/owner/workspace authority and the exact current
transaction. Before/after local guards and current source resolution are required.
Recompute the existing qualified reporting state, exact current selection head and
selected full graph when explicitly chosen. Use the shared SQL-only
`load_selected_plan_graph(db, account, expected_source, capture_id)` after caller
checks; it does not confer authority or do provider IO. Invalid/foreign/stale chosen
captures abort. No selector means exact intentional absence, never latest lookup.

Collection retains this proof; final locked persistence recomputes and compares it.
Later decisions/currentness perform the same current checks. Source, aggregate,
privacy, head, capture integrity or mapping changes invalidate current use.

## Historical Validator Port

A separate historical validator checks complete scoped ordinary evidence rows,
one matching local_reporting_v3 row per account and the commerce row, with no
missing/extra/duplicate rows and exact workspace/plan/version/account/connection/
privacy/policy/time bindings. It recomputes the saved v3 state digest from canonical
stored proof. It does not call the current capture port or compare a live head,
current aggregate pointer, original session or expired TTL.

For each chosen pin, use historical selected storage to validate its complete
retained capture/selection/aggregate graph and compare full capture, request,
selection and aggregate commitments with the saved pin. Missing or corrupt chosen
graphs fail historical integrity. Historical export still needs current viewer
access and lifecycle guards; old acquiring sessions are not authority for export.
Ordinary sync can make a plan stale while leaving its history/artifact/archive
readable. Existing selected historical campaign ownership/integrity checks remain.

Semantic privacy erasure continues removing the complete existing planning and
selected graph and revoking prepared archive delivery. There is no financial
retention exception. Pure byte-compatibility tests, both-database current mutation
negatives, historical advancement positives, missing/corrupt graph negatives and
actual archive/erasure checks precede v4 registration.
