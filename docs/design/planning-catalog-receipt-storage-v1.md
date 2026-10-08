# Exact Catalog Receipt Storage And Private Interfaces

Status: frozen design candidate for review; no implementation or migration yet.
Base: `ca08615`. Companion: `planning-catalog-receipts-v1.md`. Migration **0088**
reserved for the three tables below; 0087 and existing evidence digests stay unchanged.

## Observed Integration Seams

`customer_planning_target_catalog.read_target_catalog_v2` currently returns
`project_v2(inventory, metadata)` after owned source and expiry checks, without storage.
`input_resolution.prepare` creates a provisional input, and pure `resolve` matches
submitted `(account_id, canonical_entity_key, selection_key)` against CatalogEvidence.
The saved input retains full allocation/scenario TargetRefs, but exclusions retain
only canonical keys. A second native read has different observation times and thus
selection keys, even with unchanged names/settings. Canonical-only remapping is invalid.

The core service's `_save_inputs` already has a final atomic `repository.save_input`
transaction, and presently rejects target-bearing requests pending this feature.
`OwnedPlanningEvidenceReader.collect(ticket)` can keep its signature: resolve private
input links for targeted accounts and read other accounts normally. No execution,
mandate, financial-source qualification, or provider mutation belongs in this path.

## Exact Private Types

All private value types use frozen, extra-forbidden, strict fields with nested instance
revalidation. IDs/digests reuse existing bounded types; timestamps are timezone-aware
UTC. These values are not authority and are never accepted from customer JSON.

* `ReceiptPayloadV1`: literal schema `inlet.planning-catalog-receipt.v1`, `inventory`
  (existing discriminated Inventory union), `metadata` (PlanningMetadataV1). Validate
  unchanged native/metadata contracts, actual owned advertiser/request binding, and
  `project_v2` exact correspondence. Canonical JSON uses the existing planning canonical
  encoding and a domain-separated fingerprint over the entire payload. No OAuth context,
  credentials, raw HTTP body, or duplicated V2 payload is stored.
* `ReceiptBindingV1`: receipt_id, workspace_id, account_id, connection_id,
  composite_digest, input_digest, selected_keys_digest, selected_count. The selected
  key set is the sorted, deduplicated tuple of `(canonical_entity_key, selection_key)`
  used anywhere in that account's submitted exclusions/fixed/scenario allocations.
  Repeated uses in scenarios do not inflate count. Digest domain is
  `inlet.planning-receipt-selected-keys.v1`. Each account has exactly one receipt.
* `ResolvedInputs`: exact final PlanInputRevision plus tuple of ReceiptBindingV1,
  sorted by account_id, at most 20. No-target inputs have no bindings.
* `ResolvedInputCatalogs`: exact tuple of CatalogEvidence plus bindings. Catalog evidence
  retains ORIGINAL native/metadata read times, coverage, digests, expiry and SourceFence;
  resolving is not a new observation. Conversion into existing EvidenceRef must reuse
  the adapter's validated mapping, not invent another clock or validity bound.

Input digest binds the complete input including amounts, scenario placement, exclusion
set and its revision. The private selected set only preserves observation identity.
Reconstruct that set from each linked exact catalog and the public saved input: full
TargetRefs must compare exactly; each exclusion canonical key must resolve exactly once
across the linked account catalogs. Every link must contribute at least one used target.
Reject missing/extra links, unmatched/ambiguous exclusions, mixed observations within
an account, duplicate links, or different selected-set digest/count. Thus an exclusion
cannot disappear merely because it has no public TargetRef.

## 0088 Tables And Constraints

All fields below are NOT NULL unless explicitly nullable. Dates use
DateTime(timezone=True), integers use Integer, hashes String(64), generated receipt and
plan IDs String(32). No database defaults can manufacture observations or ownership.

### planning_catalog_receipts

Columns:

| Columns | Type / meaning |
| --- | --- |
| workspace_id, id | Integer, String(32); composite primary key |
| account_id, connection_id | Integer; exact owned source |
| actor_id, session_digest | String(32), String(64); original read identity provenance |
| authenticated_at | BigInteger; original session authentication epoch |
| privacy_revision | Integer >= 0 |
| source_revision | String(2000); exact current SourceFence revision |
| source_binding_digest | String(64); existing planning source fingerprint |
| payload_schema | String(64); exact receipt schema literal |
| canonical_json, payload_digest | Text, String(64); bounded ReceiptPayloadV1 |
| payload_bytes | Integer, 1..1048576; exact UTF-8 byte length |
| composite_digest | String(64); reconstructed V2 composite |
| target_count | Integer, 0..400; exact projected target count |
| reporting_starts_at, reporting_ends_at | UTC past reporting interval, end exclusive |
| observation_started_at, observed_at, expires_at | original composite min-start, max-observed, min-expiry |
| created_at | server persistence time; must be >= observed_at and < expires_at |

FK workspace_id → workspaces.id CASCADE. Composite FK
(account_id, workspace_id, connection_id) → advertising_accounts
(id, workspace_id, connection_id) RESTRICT. Unique
(workspace_id, id, account_id, connection_id) is the child binding target. Unique
(workspace_id, actor_id, session_digest, account_id, composite_digest) prevents duplicate
storage of the same exact read in the same session. All time ordering checked;
`reporting_starts_at < reporting_ends_at <= observation_started_at <= observed_at < expires_at`.
Index (workspace_id, expires_at, id) supports bounded cleanup.

Actor/session are immutable provenance scalars, deliberately not lifetime FKs to
customer_sessions or customer_memberships. Session removal/member removal must not
cascade historical plan evidence or prevent revocation. An INSERT binding trigger on
both dialects requires an existing session with the exact actor/authenticated_at and
an active owner membership in the receipt workspace. Runtime fresh authority checks
also require active user, current unrevoked/unexpired original session and entitlement.
Historical access never treats this insert check as continuing authorization.

### planning_catalog_receipt_selections

Columns: workspace_id, account_id, selection_key (composite PK); receipt_id,
connection_id, canonical_entity_key. Composite FK
(workspace_id, receipt_id, account_id, connection_id) → receipt unique tuple,
ondelete CASCADE. Unique (workspace_id, receipt_id, canonical_entity_key).

Exactly one row for EACH reconstructed V2 target, including ones not selected yet;
zero-target receipt has zero rows. Canonical/entity/parent/native-setting correspondence
is validated by reconstruction, not independently duplicated mutable columns. Collision
with an existing selector is never overwritten or rebound; fail closed unless every
receipt/provenance field is identical. A new read in another session cannot claim an
old selection key. Resolve compares full row set/count to the reconstructed payload.

### planning_input_catalog_receipts

Columns: workspace_id, plan_id, input_revision, account_id (composite PK);
receipt_id, connection_id, composite_digest, input_digest, selected_keys_digest,
selected_count (Integer 1..400), created_at (UTC).

Composite FK (workspace_id, plan_id, input_revision) → planning_input_revisions
(workspace_id, plan_id, revision), CASCADE. Composite FK
(workspace_id, receipt_id, account_id, connection_id) → receipt unique tuple,
RESTRICT. No standalone FK that could accept a foreign-workspace account or revision.
Insert trigger requires input_digest equal referenced input.digest, input.actor_id equal
receipt.actor_id, composite_digest equal receipt.composite_digest, created_at >= input
created_at and < receipt.expires_at. Service additionally reconstructs exact input
selection/account/window/source/privacy/session binding; SQL triggers do not pretend
to validate typed JSON or live identity.

All three tables reject every UPDATE with dialect-specific immutable-row triggers.
There is no public deletion API. Do not forbid all DELETEs: legitimate expired-unused
cleanup and semantic erasure must work. RESTRICT prevents cleanup of a linked receipt;
application cleanup checks NOT EXISTS under the canonical workspace lock. No receipt
is deleted just because its session is revoked or TTL has elapsed if history links it.

## Capacity, Cleanup And Privacy

Proposed fixed engineering bounds (not a subscription promise): 1 MiB canonical payload,
400 target links per receipt, 20 receipt links per input, 1,000 receipt headers and
64 MiB summed payload bytes per workspace, including linked history. At most 40 unlinked
unexpired receipts per actor/account. Each explicit V2 request may invoke exactly one
maintenance batch BEFORE native IO: delete up to 100 expired unlinked receipts ordered
by expiry/id in a separately committed, caller-owned transaction. No retry loop or
additional automatic batches in that request. Remaining capacity exhaustion returns
actionable 409 without returning unretained V2 selections. No silent truncation,
LRU eviction of unexpired receipts, or automatic deletion of linked history. These caps
are reviewable capacity choices; a workspace that fills retained history needs an
explicit later capacity change, not hidden destructive cleanup.

Count/sum checks and insert/link/delete serialize on the existing workspace authority
lock. Maintenance refreshes the original identity outside SQL, then validates current
owner/session, workspace privacy revision and paid-work access under that lock. Its
caller performs the same final authority and privacy checks after deletion/flush, then
commits; the cleanup helper itself never commits or rolls back. Cleanup recomputes
current time after lock waits and performs no provider IO. Failed maintenance authority
or privacy checks roll back the batch and abort the request.

The subsequent native read and receipt insertion use fresh, independent authority and
source/privacy checks; no maintenance fact survives across IO. A capacity 409 rolls back
all NEW receipt/selection rows, but retains successfully committed authorized cleanup.
This avoids rollback starvation when reclaiming one bounded batch does not immediately
make enough space. Parent-operation atomicity excludes this independent maintenance
transaction. Cleanup never removes linked history, unexpired receipts, inputs or plans.
PostgreSQL concurrent link versus cleanup and SQLite transaction behavior require tests.
Quotas do not change native TTLs; failure never exposes a catalog as selectable.

Register all tables in lifecycle ownership/export/closure inventories. Canonical payload
export revalidates schemas, canonical byte length, digest, scalar fields and complete
selection links; corruption fails closed. Add receipt tables to the bounded planning
archive classification (existing 5 MiB conservative row estimate covers 1 MiB JSON).
Export names/settings and ownership/provenance needed to interpret history, but omit
session_digest/authenticated_at from customer exports as private authentication metadata;
never emit raw transport payloads or secrets. Preserve existing archive total-row/byte
limits rather than raising them to bypass bounds.

Semantic workspace/source privacy invalidation erases the plan graph and all affected
receipts: input receipt links before inputs, receipt selections before headers. Existing
workspace erasure may conservatively remove all workspace receipts alongside all plans.
Workspace closure archive/erasure must include unused receipts too. Ordinary reporting
correction invalidates source proof/use without deleting history. Receipt expiry permits
cleanup only when unused; it neither grants export access nor erases committed plans.

## Frozen Private Function Signatures

New module: `app.planning_documents.catalog_receipts`. Names/signatures below are proposed
for shared implementation; DB helpers never commit/rollback or perform identity/provider IO.

```python
write_catalog_receipt(
    db: Session, *, principal: CustomerPrincipal, source: SourceFence,
    inventory: Inventory, metadata: PlanningMetadataV1, now: datetime,
) -> TargetCatalogV2

resolve_input_catalogs(
    db: Session, *, principal: CustomerPrincipal, prepared: PlanInputRevision,
    intent: CustomerInputs, sources: tuple[SourceFence, ...], now: datetime,
) -> ResolvedInputCatalogs

bind_input_receipts(
    db: Session, *, principal: CustomerPrincipal, resolved: ResolvedInputs,
    sources: tuple[SourceFence, ...], now: datetime,
) -> None

resolve_saved_input_catalogs(
    db: Session, *, principal: CustomerPrincipal, ticket: GenerationTicket,
    now: datetime,
) -> ResolvedInputCatalogs

recheck_saved_input_receipts(
    db: Session, *, principal: CustomerPrincipal, ticket: GenerationTicket,
    catalogs: tuple[CatalogEvidence, ...], now: datetime,
) -> None

cleanup_expired_unused_receipts(
    db: Session, *, workspace_id: int, now: datetime, limit: int = 100,
) -> int
```

Resolve_input_catalogs initially returns bindings with input_digest of the final pure
`input_resolution.resolve(prepared, intent, catalogs)` result, computed inside this
helper using that existing resolver. ResolvedInputs is then a packaging operation; it
must not permit a caller to substitute different resolved inputs with old bindings.
Cleanup limit is strict 1..100; its caller owns the separately committed maintenance
transaction, fresh owner/session/privacy checks, workspace lock and final check. The
workspace-only helper is private and is not an independently authorized/public route. All other helpers require
current caller-owned owner authority, canonical source/account locks and paid-work
checks. They enforce DB-only guard/current principal/source/privacy checks themselves
without identity callbacks; caller refreshes IdentityFact before opening transaction,
and calls authority.final after ALL helper waits and before/after flush. Sample actual
clock after waits for receipt expiry, never trust only the incoming `now`.

A typed `CatalogReceiptUnavailable` carries bounded reasons (missing, expired,
selection_mismatch, source_changed, original_session_changed, integrity_unavailable,
capacity_exceeded). Caller maps to 409 with fresh-read/reselection guidance, except
current authentication/authorization failures propagate as existing 401/403. Never
convert arbitrary HTTP409/metadata errors into absent evidence or new native rereads.

## Atomic Operation Boundaries

1. **V2 read:** run at most the one separately committed maintenance batch described
   above, before native IO. Use reviewed planning authority/read contexts; identity
   refresh before DB, native IO outside SQL transactions. In a final new transaction refresh outside,
   lock original owner/session/workspace then account/source, compare source/privacy
   from BEFORE IO, validate advertiser/request/payload, enforce bounds and write receipt
   plus complete selection rows atomically. Final original expiry and authority check
   after flush, commit, then return unchanged V2. Response loss leaves an unused receipt,
   never an authority grant. Receipt insertion failure does not undo earlier authorized
   maintenance. V1 route stays unchanged. No global auth change.
2. **Create/edit:** preserve current idempotent replay check before resolving selectors.
   Resolve exact submitted keys in one owner transaction; all selectors for an account
   must use one receipt with exact requested primary past window and original session.
   Perform existing pure input resolution. Final save transaction rechecks original
   receipt/source/privacy/expiry and complete bindings, inserts input then links in the
   SAME transaction as input head/idempotency receipt. Any failure rolls all back.
3. **Generation:** resolve saved exact input digest and complete links under original
   owner/session; reconstruct and validate receipt catalogs. Targeted accounts make no
   new native request. Untargeted accounts retain existing fresh native read flow. This
   does not suppress current performance/commerce reads for any account. Final commit
   calls recheck_saved_input_receipts alongside existing recheck_local_sources, exact
   current reporting/commerce proof, final expiry and 5-second authority checks. No DB
   locks are held during IO. Erasure/revocation/expiry during other-account IO aborts.
4. **History/replay:** current authorized READ_ROLES and privacy rules still apply, but
   no requirement that original session or receipt TTL is active. Render committed
   immutable PlanInput/PlanVersion; do not call the NEW-generation resolver for historical
   reads or an already completed idempotency replay. New generation from an expired
   selection requires a fresh read AND explicit new input revision. No silent refresh,
   owner/session substitution, target remap, or decision carryover.

## Required Qualification Matrix

* Pure: original native schemas/golden hashes unchanged; payload and every scalar tamper,
  unsafe model_copy, swapped IDs/parents/settings, wrong advertiser, canonical mismatch,
  forged selection, duplicate/missing/extra selection and input links reject.
* Actual SQLite/PostgreSQL migration 0087→0088: composite foreign workspace/account/source
  rejection, original-session insert binding, immutability, expiry/count/bytes constraints,
  FK-safe semantic erase, clean disposable downgrade only, registry/export/archive bounds.
* Actual all-three-provider MockHTTP V2→receipt→create/edit→generate: identical second read
  has distinct selection; ORIGINAL selection still resolves; allocations/scenarios and
  exclusion-only input preserve exact original target. No native HTTP for targeted
  generation accounts; mixed untargeted accounts still read normally. Names HTML-like
  remain plain text. No ad writes or execution anchors.
* Mixed snapshot keys for one account, foreign receipt/session rotation, wrong primary
  window, source revision/account advertiser/privacy changes, missing/corrupt receipt,
  zero-target selections, stale raw client catalog all reject without partial persistence.
* Delays/races: expiry after read/before save/after flush/during other-account IO, revoked
  owner, membership/entitlement/session changes, source/semantic erasure, concurrent
  cleanup versus input binding, simultaneous capacity insertion. Current authority failures
  never become gaps. Assert identity IO precedes SQL; no provider IO under locks.
* Capacity: byte and count bounds exact at/above limits, expired-unused batch limit,
  linked history protected, unused closure/export coverage, no unretained success response.
  Seed more than one cleanup batch plus insufficient reclaimed bytes: successive explicit
  V2 requests each commit at most 100 eligible deletions despite capacity 409, eventually
  reclaiming space without an unbounded loop. Failed maintenance authorization/privacy
  rolls back deletion; subsequent insertion failure preserves only committed maintenance.
  Assert no provider IO during maintenance and no change to linked receipts/plan history.
* History: expired original receipt/session permits currently authorized historical read
  and completed idempotent replay, denies NEW generation; fresh selection creates new
  revision with no automatic decision carryover. Viewer read stays DB-only/read-scoped.
* Real customer browser: explicit read→select→save→generate, exclusion-only path,
  stale/reselection guidance, no automatic reread, same-owner rotated session isolation.

Implementation is pending shared review. Original short native validity may constrain
interactive editing; this design does not assert a usable production timing envelope or
extend any deadline to conceal that limitation.

## Implementation Ownership Freeze

Independent design review closed `f6c06f1`. Model module is
`app.planning_documents.catalog_receipt_models` with SQLAlchemy classes
`CatalogReceiptRow`, `CatalogReceiptSelectionRow`, `InputCatalogReceiptRow` and exact
column names above. Storage/migration/lifecycle lane owns that module, revision0088,
model registration, archive/erasure integration and corresponding database tests.
The receipt-helper lane owns `app.planning_documents.catalog_receipts`, the frozen
private types/functions above and source-proof/payload/helper tests. It imports the
frozen model names; no model/schema changes without coordinated contract update.
Root owns customer V2 route, core service/evidence-reader wiring and customer browser
integration after reviewed prerequisites. Both lanes begin from this root freeze;
helper DB qualification awaits the actual frozen model implementation, not mock tables.

## Historical Export Validator Addendum

Approved private DB-only interfaces in `app.planning_documents.catalog_receipts`:

```python
validate_retained_receipt(
    db: Session, row: CatalogReceiptRow,
) -> tuple[ReceiptPayloadV1, TargetCatalogV2]
validate_retained_input_receipts(db: Session, inputs: PlanInputRevision) -> None
```

These reconstruct canonical payload/scalars and the COMPLETE selection row set, and
validate complete input links/input digests/selected sets respectively. Historical
validation does not require an active original session, unexpired receipt, or current
native source. Caller retains current read-role authorization and privacy/export locks.
They do not authorize new use; new-use resolvers layer fresh original session, source,
ownership, entitlement and expiry checks over the same structural validation. No IO,
commit, rollback or lifecycle callback is performed by these helpers; lifecycle callers
must not enter the current-use resolver to export history. Failures use the existing
typed CatalogReceiptUnavailable and fail export integrity, never expose partial proof.
