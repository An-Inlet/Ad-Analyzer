# Standalone Owned Planning Image Reader V1

Depends on reviewed creative-basis DTO `405a0d0`. This next package resolves actual
owned image bytes; no current API, policy, persistence, composer or export wiring.

## Port

`OwnedPlanningImageReader(sessions, *, principal, provider, store, clock)` exposes
`collect(ticket: GenerationTicket, requested: CreativeInputV1) -> CreativeBasisV1`.
Constructor snapshots the loaded original principal as existing planning readers
do. `store` is an explicitly injected existing `MediaStore`; no default external
storage or URL fetch. Ticket and requested values are revalidated, not trusted
because they are Pydantic instances. This is a server-only read helper, not a
public endpoint or permission from a parsed ticket.

The ticket's original actor/session must equal the supplied principal. Use its
workspace, privacy revision and confirmed goal currency. Existing `check_goal`
validates the exact current confirmed goal before and after I/O. The caller will
later bind `requested` to saved inputs when that separate integration is reviewed;
this standalone helper does not claim such persistence binding.

## Collection Sequence

1. Open a fresh `PlanningReadContexts` authority context, check paid work, exact
   ticket privacy and current goal. Snapshot only the selected owned `MediaObject`
   rows in customer order. Validate row metadata against selection ID/SHA, strict
   image bounds/MIME and aware timestamps. Foreign/missing IDs do not fall back.
   Reject combined sizes above128MiB before reading bytes. End the SQL context.
2. For each snapshot, call private `read_exact(workspace_id, sha256, size)` without
   any reader-owned SQL session/transaction. Independently check returned byte
   type, exact size and SHA256; decode/inspect via existing bounded image
   validation and require actual MIME/width/height equal snapshot metadata. Video
   is unsupported. Do not retain raw bytes in the result or logs. Each image's
   `observed_at` is recorded after successful byte inspection.
3. Refresh the same original identity outside SQL, then open a fresh authority
   context. Re-read exact rows with refreshed values and compare every snapped
   identity/metadata field, including creation actor/time. Recheck paid access,
   current goal, privacy and original session after lock waits. Return the exact
   ordered `CreativeBasisV1` only after context exit succeeds.

Bound total collection to60seconds using monotonic elapsed time, with checks
before/after storage and inspection and after final authority. Reject a backwards
monotonic clock or image observation clock. This deadline is an operational bound,
not a new provider freshness lifetime; it does not authorize extending plan expiry.
No SQL commit, file mutation, upload, advertising access or media deletion occurs.

## Failures And Limits

Retain authentication/authorization/payment failures as their existing HTTP status.
Use a fixed `PlanningImageUnavailable(ValueError)` for selected-media absence,
changed metadata/privacy/goal, invalid/corrupt/unsupported bytes and elapsed bounds;
storage unavailability must not expose paths, raw payloads or foreign IDs. Do not
catch arbitrary exceptions or convert an authorization error into optional absence.

The witness states what bytes were verified at observation time. It cannot promise
that out-of-band filesystem corruption/deletion never occurs afterward. Later
generation/currentness/export wiring must respect this temporal limitation and
existing lifecycle/privacy gates; this package does not wire or claim those gates.
No image-product match, visual suitability, asset rights or provider approval is
inferred from metadata or successful decoding.

## Focused Qualification

Use actual owned upload and confirmed goal/session fixtures on SQLite/PostgreSQL.
Verify exact image witness and digest, zero selections, original-session authority,
and absence of SQL transactions during storage I/O. Test foreign/missing IDs,
expected hash mismatch, swapped/corrupt bytes, MIME/dimension mismatch, metadata
change/deletion during I/O, privacy/goal/session/membership/entitlement changes,
and bounded clock failures. Retain failures and run whole Ruff/configured mypy.
No default planner activation or live storage/provider qualification is implied.
