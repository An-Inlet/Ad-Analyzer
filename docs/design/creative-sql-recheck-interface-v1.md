# Standalone Creative SQL Recheck V1

Preparatory private port on reviewed collection/proof contracts. No service,
PlanVersion, dependency, history or capability wiring in this package.

Expose `creative_image_row_identity_digest(row:PlanningImageRowPinV1)` in the pure
proof module as the shared strictly revalidated implementation already used by its
factory. It hashes every row identity field except observed_at in the same existing
creative-image-row-identity.v1 domain, preserving all existing digest bytes.

Add `creative_finalization.py`:

`recheck_collected_creative(db,*,principal,ticket,collection,now,authorize)
 ->CreativeRetainedProofV1`

Revalidate complete ticket and envelope and assert their exact binding. Require
original principal actor/session equality. Caller supplies original fresh identity
fact and SQL-only authorize callback, owns workspace-first lock and transaction;
port must assert one active non-nested clean root transaction, call authorize before
and after locks, and independently retain original-session SQL scope checks using
the existing planning authority pattern. Do not call providers/storage/decoder or
open/commit a transaction. Recheck paid generation entitlement, confirmed goal and
privacy before and after image locks, including the empty selection. Sample fresh
max(aware UTC now,database_utc_now) after waits; reject future ticket/image evidence.
Preserve the existing authority freshness/deadline checks through authorize rather
than invent a new global generation TTL.

Reload every exact owned MediaObject in customer order with for_update and
populate_existing. Require all fields including created_by and created_at match
the collected pin identity. Construct comparison witnesses using the original
observed_at; never restamp successful byte inspection. Revalidate the supplied
collection again before deriving the returned public proof. Any missing/foreign/
changed row, scope, saved creative or ticket binding fails closed. Expected source
changes use existing409 conflict semantics; genuine authorization errors and
unexpected callback/database errors retain existing distinctions.

This validates current SQL against a private inspection envelope, not its provenance
in isolation. Future service must supply the envelope from the actual owned reader
and compare returned proof with the candidate document before atomic persistence.
The opaque DTO cannot grant itself read, write or finalization authority.

Tests on SQLite/PostgreSQL exercise actual owned collect_pinned then same-session
SQL recheck; empty/multiple images; creator/time/hash/size/MIME/dimension changes;
missing/foreign rows; original session/membership/entitlement/goal/privacy changes;
future witnesses; no storage/provider calls inside SQL; final lock/authority guard;
unsafe copies; no partial writes; callback exceptions propagate. Preserve original
observation timestamps and all existing proof digest regressions. Whole Ruff and
configured mypy required. History/currentness/dependency wiring remains a later
separately reviewed package; ordinary metadata loss is not semantic privacy erasure.

Review clarification: capture both Session root and underlying Connection root
transaction identities at entry; require the same active, nonnested, clean objects
through every callback and SQL phase. Reject dirty state before queries/autoflush.
Strictly validate aware supplied now and compare UTC-normalized ticket/image
instants (including DST folds), never raw same-zone datetimes. Future-ticket/image
checks apply at the freshly sampled final time as well as the initial boundary.
