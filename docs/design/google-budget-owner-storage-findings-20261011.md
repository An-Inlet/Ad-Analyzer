# Shared-Budget Consumer Storage Findings

Investigation at `d8e5d6b`. This document authorizes no consumer implementation.
The standalone owner/intent contract is separately reviewed; these findings keep
its future activation consistent with the existing original-session receipt rules.

## Existing Provenance Is Richer Than A Projected Hash

`CatalogReceiptRow.canonical_json` retains the typed original native inventory and
metadata, not only a projected catalog. `validate_retained_receipt` reconstructs
and validates the catalog. The receipt binds workspace/account/connection, actor,
original session and authenticated time, source/privacy revisions, reporting
window and original expiry. `CatalogReceiptSelectionRow` maps exact entity
selectors to that owned receipt. `InputCatalogReceiptRow` links an immutable input
revision to the exact receipt; its restrictive receipt foreign key keeps linked
provenance from ordinary unused-receipt cleanup.

Thus a second copy of the raw catalog is unnecessary solely to retain an original
owner witness. A witness can be deterministically rederived from that immutable
receipt and compared with the input's committed observation and owner facts.
Missing or changed raw receipt evidence must fail; a digest alone is insufficient.

## Additional Lookup And Link Requirements

The reviewed primitive owner selector has an opaque owner-selection commitment,
not a representative target selector. Existing entity-selection rows cannot simply
be relabeled or searched by owner hash. A future consumer must either freeze a new
scoped owner-selection mapping to the original receipt, or explicitly revise the
request contract to reuse an exact owned representative selector. Do not add a
bounded-table scan or trust a client-supplied receipt/account association as an
implicit implementation choice.

If a new mapping is chosen, its composite foreign key must include workspace,
receipt, account and connection. Uniqueness is required per receipt/owner and per
scoped opaque selection. Recompute the selection, full witness and facts commitment
from the original immutable receipt on admission. The input link must retain that
receipt even when no ordinary entity selector otherwise uses it. Owner membership
must never be represented by whichever single allocation target the customer picked.
Schema migration, immutability/binding guards, capacity limits, retained exports and
erasure registration must be reviewed together before that mapping is implemented.

## Generation Must Preserve Current Receipt Gates

`resolve_saved_input_catalogs` currently calls `_load`, which requires the original
session, exact source/privacy/window and an unexpired original receipt. Its final
recheck compares the saved catalogs against the generation read bundle. A facts
hash does not replace these checks or permit an expired receipt to be reused.

The standalone distinction between observation digest and stable facts digest
supports separately acquired observations, but does not introduce such a runtime
path. Any future fresh-generation acquisition must define its own reviewed source
and authority checks while retaining the original input proof. Do not weaken
`recheck_saved_input_receipts` to compare only owner facts, or silently substitute a
later catalog for the original one. Existing current-generation behavior can use
its already-qualified, unexpired receipt until a separate acquisition protocol is
reviewed. Historical export validates original provenance without requiring a live
session or current TTL; that distinction remains intact.

## Activation Checklist For The Next Interface Review

Freeze the exact owner lookup schema, request/response fields, input-link identity,
strict original-session and UTC-window checks, capability opt-in, and whole-owner
uniqueness/exclusions/scenario/zero-ceiling rules as one coherent contract. Freeze
how source fences enter document validation explicitly. Preserve omitted defaults
and legacy hashes. Require SQLite/PostgreSQL negative ownership, expired receipt,
reconnect, changed session, CAS/replay, missing provenance, export and erasure tests.

The proposed amount remains a customer hypothesis. No storage receipt, membership
proof or manual review prerequisite qualifies a positive daily amount as a period
spending cap. Native-setting output remains unavailable while that economic and
provider-validity evidence is unqualified. No advertising write path is introduced.
