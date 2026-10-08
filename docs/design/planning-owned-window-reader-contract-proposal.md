# Owned Window Reader — Bounded Package Proposal

Base `206e03f`; docs only, pending review. This refines the owned-reader portion of
[phase two](planning-window-reader-phase2-proposal.md). The pure projector and
private evidence/policy contracts have separate owners. This package may precede
adapter activation; it does not enable v3, change a route/default policy, implement
a composer comparison, or add public comparison output/UI.

## Files And Additive Interfaces

Proposed new module `app/planning_documents/window_reader.py` owns
`OwnedWindowReadContext`, `prepare_owned_window_context`, and
`read_owned_requested_window`. Refine the phase-two signatures explicitly:

```python
def prepare_owned_window_context(
    db: Session, *, principal: CustomerPrincipal, account: AccountRef,
    expected_source: SourceFence, expected_reporting_pin: ReportingPresencePin,
    catalog: CatalogEvidence, authorize: Authorize,
    clock: Callable[[], datetime],
) -> OwnedWindowReadContext: ...

def read_owned_requested_window(
    context: OwnedWindowReadContext, *, target: TargetRef,
    requested_window: ReportingWindow,
) -> RequestedWindowPerformanceV1 | KnownWindowGap: ...
```

The caller supplies its existing trusted clock, locked read context, and DB-only
authorization callback. There is no implicit wallclock/provider callback or new
identity flow. Sample the supplied clock after waits for resolve_source_fences and
actual catalog expiry checks; preserve caller final authority-age checks and its
existing database-clock freshness comparisons. Tests may supply a deterministic
clock but production does not acquire a new adjustable freshness policy.

`catalog` is the actual current server-owned CatalogEvidence (including a validated
saved original receipt where that is the established path), not a caller-asserted
target list. Revalidate its exact source/account/privacy binding, server-owned
receipt provenance when applicable, and original deadline through existing caller
resolution before preparing this context. Prepare binds it to expected_source and
reporting pin account and builds an exact campaign target map including catalog
reference key, canonical key, snapshot selection key, kind, provider reference,
display name and budget-owner key. Every requested TargetRef must equal the target
derived from that catalog, not just match a native ID. Validate local campaign
mapping separately. A DTO constructor cannot prove ownership or replace those
caller-owned catalog/receipt and current source checks; neither a TargetRef alone
nor a canonical-key lookup grants membership/selection. Catalog-unavailable paths
remain adapter gaps without inventing an owned reader context.
It depends on planning AccountRef/SourceFence/ReportingPresencePin/TargetRef and
therefore must not live in generic campaign_performance. KnownWindowGap belongs
to the separately reviewed private window evidence contracts. No reverse runtime
import from ports or retained_sources into window_reader is allowed.

Retained sources receives only these additive private seams:

```python
_reporting(db, principal, ref, privacy, *, qualified=False,
           presence_context: PresenceReadContext | None = None) -> tuple[str, str]
capture_reporting_presence_pin(db, principal, ref, privacy, *,
           presence_context: PresenceReadContext | None = None) -> str
```

`None` preserves the existing read_presence call, fingerprint domain, state fields,
header/fact order, None absence, exceptions and old policy behavior. For a supplied
context verify same Session and live transaction, then use context.read(completion).
No supplied cached digest or caller-generated graph is accepted. Both outputs
must match the old helper byte-for-byte for identical valid state.

The planning-owned context wraps a new guarded operation-local PresenceReadContext
(or a private subclass accepted by the existing typed helper). Keep the public
existing context's default semantics unchanged in this bounded package. Calls to
real `read_current_with_presence` receive this guarded context. A guard on every
cache-hit path is mandatory; merely checking in the outer helper is insufficient
if the generic reader calls context.read after refreshing ORM completion state.

## Immutable Completion Binding On Every Read

Current `PresenceReadContext.read` checks the root transaction and completion ID;
a hit does not call `_completion_binding` again. `read_presence` validates supplied
and refreshed persisted completion binding only on a miss. Therefore an ID alone
is not a sufficient reuse key. Capture a detached immutable tuple of **every**
PerformanceCompletion mapped scalar immediately after the initial successful read:

```text
id, workspace_id, account_id, platform, source_connection_ref,
generation, privacy_revision, starts_on, ends_on, currency, time_zone,
query_version, semantics, selected_event, reporting_basis,
completed_at, row_count, manifest_digest
```

Normalize only timezone representation of aware completed_at as existing UTC
helpers do; do not stringify/coerce integers or omit None selected_event. Before
any reuse, require the same scoped current pointer, refresh the actual persisted
completion with populate_existing, and compare all scalars to the detached tuple.
Also compare the supplied completion's pre-refresh scalar snapshot: do not let
populate_existing erase a caller's changed/unflushed values before detecting it.
An absent completion state has an explicit sentinel; it must remain absent. A
context is single-completion/single-account and must reject, not silently switch,
if current changes. Full validation happens on miss; equality with that validated
snapshot preserves its binding on hit without rereading/reparsing all facts.

Source/account/privacy/native mapping checks remain real DB checks, not inferred
from this tuple. Use actual current source resolution and original ordinary Meta
provenance guard, real legacy current reader and unchanged manifest recomputation.
Bound local/native campaign mappings with existing limits and exact account and
platform predicates. Do not downgrade malformed/present completion graphs to a
gap, even if the requested target has no metric rows.

## Read Slice And Transaction Lifetime

The context is scoped to a short **read-only slice** within a caller-owned locked
transaction. It owns no commit or rollback. At entry require an active root
Session transaction, no nested transaction, no pending new/dirty/deleted ORM state,
and the expected current source locks/DB-only authorization. Capture root Session
transaction identity and the underlying active connection transaction identity.
Context cannot be used after close, root commit/rollback, connection transaction
replacement, Session replacement, or final persistence begins.

Prohibit savepoints for this new context: checking `get_nested_transaction()` only
at reuse is insufficient because a savepoint may already have rolled back while
root identity remains unchanged. Register a narrowly scoped Session transaction
observer for the context lifetime that irrevocably invalidates it upon nested
transaction creation/end or root end. Invalidation persists after nested rollback
or release; do not revive the cache when the active nested transaction becomes
None. Remove observers when the context closes. Existing callers without this new
context retain their behavior. Tests must exercise rollback as well as active
savepoints and release, not merely different Session IDs.

No ORM write/flush, bulk DML, raw SQL mutation, or provider/identity I/O may occur
between successful validation and reuse. Run the slice with autoflush disabled;
reject pending mutations on each entry and invalidate on flush attempt/completion
via narrowly scoped Session hooks. Helpers issue reads only. Raw/bulk writes and
external I/O are prohibited caller behavior, not something a dirty-set check can
prove absent; do not claim the context guards arbitrary hostile code with access
to the same connection. A code path that needs any write or external call must
close/discard context first and create a fresh context afterward. Nested/savepoint
hooks and actual write/flush tests make the relevant repository paths verifiable.
No provider callbacks are retained as authorization functions: supplied callback
is DB-only and current external authority must have been refreshed before SQL.

Final generation persistence is outside this read slice. Close contexts before
flush/insert; retain immutable report/pin values, then preserve the service's final
fresh authority/time checks immediately around writes. This proposal does not
relax that service contract or claim source locks replace current authorization.

## One Presence Parse Per Context, Not Per Operation

Create the guarded PresenceReadContext **before** the optional pin-helper call.
Its initial read validates/indexes the whole graph. The pin helper serializes the
same validated graph in the unchanged fingerprint. Each actual campaign V3 reader
reuses this context; each validated original is cached per local campaign for the
primary/comparison projector calls. The pure projector receives only original V3
and requested window. Never pass the whole graph to the pure projector.

The existing adapter's initial pin block and subsequent per-account `reads.open()`
blocks are different transactions, often separated by native HTTP. They **cannot**
share this cache. Future integration uses fresh per-account contexts in each actual
transaction. Initial pin transaction may parse once; later collection transaction
must parse freshly; final recheck transaction must parse freshly again. That is
necessary validation, not a target for cross-operation caching.

When one final transaction processes several accounts, use a bounded dictionary
keyed by exact account identity, with one context per account (maximum MAX_ACCOUNTS)
or process each account's pin and reports together before closing its context.
Do not feed all account pins through one single-entry cache and then revisit their
campaigns, causing reparsing/cache thrash. Preserve deterministic account lock order.
The same verified graph can avoid redundant parse/index work; legacy manifest
queries and per-operation source/authority checks remain unchanged. No claimed
latency improvement or broad SQL optimization belongs to this package.

## Known Absence Versus Integrity Failure

Only after current owned source validation:

- Truly absent current pointer -> current_reporting_unavailable.
- Valid whole current graph but no exact native-to-local campaign mapping ->
  campaign_reporting_unavailable. No name fallback.
- Valid current legacy report with truly absent sidecar ->
  reporting_presence_unavailable; present malformed/partial graph aborts.
- Frozen projector's three typed valid-source incompatibilities -> corresponding
  known gap. Ordinary validation errors never become benign gaps.

Missing returned days/cells remain report coverage/null values. They are not no-data
exceptions. Whole source pins preserve current/sidecar absence, including accounts
with gaps. Source/mapping/privacy/manifest changes invalidate; generic 409/auth/
billing/capacity errors abort. Google/TikTok retain explicit absence where no
presence producer exists, not synthetic Meta semantics. No provider requests occur.

## Required Bounded Qualification Before Integration

Actual SQLite/PostgreSQL fixtures use real source/completion/presence storage and
existing MockHTTP import where needed; never an invented valid bundle or mock table.
Reader tests do not require new public runtime wiring.

1. Valid Meta original V3 projected to primary/comparison; exact source header and
   both requested digests; unchanged legacy whole-window reader outputs. Optional
   pin helper equals default digest for graph present and absent. Default v1/v2
   helper paths remain unchanged.
2. Instrument actual read_presence/whole graph validation and indexing: exactly
   once per guarded context including the pin and multiple campaigns/windows;
   fresh context after each transaction validates anew. Do not assert legacy
   manifest scan reduction. Multiple accounts never share cached graphs.
3. Foreign workspace/account/connection/platform/campaign/native ID, swapped target,
   detached/expired/revoked principal, changed source generation, privacy, and
   current completion reject. Valid absent current/presence/mapping gives only the
   precise known gap; corrupt header/facts/manifests/partial sidecar abort.
4. Same completion ID with each changed scalar rejects before a hit is accepted,
   specifically source_connection_ref, query_version, row_count, selected_event
   (including None transitions), currency/timezone and manifest. Test supplied
   in-memory changed values and persisted changes using explicitly isolated
   corruption fixtures; do not weaken production immutable triggers.
5. Changed native/local mapping or current pointer between reads rejects; a new
   context detects source changes outside the selected campaign/subset. Existing
   workspace/source locks and supported transaction isolation remain the defense
   against concurrent legitimate mutation during a read-only slice.
6. Root rollback/commit then reuse, other Session/connection, active nested
   transaction, nested rollback, nested release, pending ORM changes and flush
   invalidate/reject. No provider call occurs under DB locks. Confirm observers
   are removed on exit/error and do not affect subsequent ordinary readers.
7. Final-time/source tests continue to use fresh authority and original expiry;
   no default lifetime changes. No read helper commits or leaves partial writes.

Require focused tests on both DBs, Ruff/mypy/diff, ledger and independent review.
No aggregate run is needed for this proposal. After this package, reader/adapter/
composer activation still needs its own integration tests and approval; public
comparison behavior remains a separate contract. This document alone qualifies
nothing and changes no executable behavior.
