# Exact Catalog Selection Receipts — Proposed Implementation Boundary

## Reproduced Problem

Two real MockHTTP V2 reads can return the same canonical entity and exact native
entity while their selection keys differ: composite observations include read times.
Re-reading a submitted selector therefore cannot prove the original selected snapshot.
Current target-bearing input resolution must fail explicitly; it must not silently
remap the selection. No-target creation/generation can continue independently.

## Compatible Selection Contract

Keep the public `TargetSelector(account_id, canonical_entity_key, selection_key)` and
immutable TargetRef/composer contracts. Add short-lived server-owned catalog receipts
and indexed selection-key links. A successful owned V2 catalog read retains the exact
native inventory and metadata plus their verified composite, workspace, actor/session,
account/source/privacy fences, reporting window and original expiry. The V2 response
need not change. Client-supplied complete catalogs are never trusted as receipts.

Resolve submitted selection keys only through this owned receipt store. Require exact
canonical/entity/parent/source/window correspondence, original current actor/session,
current ownership/entitlement/privacy, unexpired actual receipt and unchanged source.
All selections for one account must refer to a single compatible observation. Names
are display data, never lookup keys. Missing, mixed, expired or changed selections fail
with actionable 409 and require a fresh read and explicit customer edit/reselection.

For a target-bearing account, generation uses that exact retained catalog while it is
still valid, rechecking the original fences before/finally. It does not perform a new
native read and pretend the new selection hash equals the old one. Other selected
accounts may use fresh normal reads. Old committed inputs/results remain historical
and replayable under current authorization/privacy after receipt expiry; new generation
from expired selections requires a new confirmed input revision. No decisions carry over.

## Storage And Lifecycle

Reserve migration 0088 for two private owned tables: catalog receipt headers/canonical
bounded native+metadata payloads, and selection-key links to receipts. Composite keys/FKs
must bind workspace, advertising account and connection; actor/session belongs to the
workspace-owned read. Immutable payload/selection rows, explicit maximum catalog size,
receipt/count bounds and cleanup of expired unused reads are required. Exact field/DDL
review precedes implementation. No schema reset or rewrite of migration 0087.

Receipts follow workspace/source privacy erasure and closure/export policy. Never leave
catalog names or settings outside the lifecycle registry. Semantic erasure removes both
receipt tables together with the existing plan graph. Ordinary reporting corrections may
invalidate use without deleting immutable plan history. No credential/token payloads.

## Shared Interface To Freeze Next

The catalog receipt writer accepts actual server-read Inventory+PlanningMetadataV1 under
fresh original authority and exact final source checks. The resolver accepts selected
keys/owned account and returns the verified exact catalog, never a synthesized reference.
The trusted evidence reader consumes a server-only resolver for target-bearing accounts.
Service input resolution and generation retain the same immutable receipt-derived target.
No generic client proof injection, invented lifetime or provider write is introduced.

Required checks: unchanged repeated native reads produce distinct snapshot keys; original
receipt resolves; forged/foreign/session-rotated/mixed/expired keys reject; source/privacy
changes before commit reject; target-bearing create→generate preserves exact references;
expired receipt requires explicit reselection; historical replay remains readable; actual
SQLite/PostgreSQL migration/export/erasure and real customer API/browser flow.

This design is not implemented or qualified. The private proof interfaces, schema and
retention bound must be concretized and reviewed before dependent implementation.
