# Reporting Presence Storage Review

Proposal only, 2026-10-08, inspected base `8b9d932`. Migration 0089 is reserved,
not implemented or authorized by this document. Exact pure models and byte bounds
remain subject to root review of the separate presence-contract implementation.
No change to PerformanceCompletion columns, legacy manifests, existing reporting
responses, or execution authority is proposed.

## Source Findings

- `app/meta/sync.py:370` selects a genuinely new rolling or fixed window; dates,
  phase and old campaign staging are initialized through line 400, before token
  acquisition or the first page. This is the provenance capture point.
- `app/meta/sync.py:136` normalizes campaign insights using the current selected
  action. `app/meta/normalize.py:70` produces legacy numeric values; presence must
  come from the original parsed field/event membership, never those defaulted
  numeric outputs. Preserve independent count/value presence.
- `app/meta/sync.py:448` begins detail staging only after campaign insights finish.
  `app/meta/staging.py:29` captures its checkpoint then, and `:149` clears it before
  returning to campaign publication. MetaDetailCheckpoint cannot prove the event
  or query contract at the start of campaign collection.
- `app/meta/sync.py:172` publishes staged metrics, deleting them at `:223` before
  `publish_meta`; `app/campaign_performance/service.py:77` creates the completion
  and moves CurrentPerformance. Presence facts must be captured/validated before
  this deletion and attached to that exact completion within the same transaction.
- `app/meta/service.py:278` reconnect bumps privacy and generation, changes the
  selected event, resets dates and staging. `app/meta/sync.py:475` handles reconnect
  failure and `:482` resets rejected staging. Every such path needs explicit new
  context cleanup; detail-only cleanup must not discard valid campaign context.
- `app/meta/sync.py:488` can reset phase/staging while retaining window dates.
  That is not the new-window branch. A restart without its original context must
  remain unqualified for the entire existing window; it cannot adopt a new event
  or producer descriptor merely because phase becomes `campaigns` again.

## Recommended Additive Shape

Use a separate `meta_presence_stage_contexts` table rather than a nullable JSON
blob on MetaConnection. It has one immutable context per active native connection,
with its own random window token, workspace, integration, account, native advertiser,
generation, privacy revision, inclusive requested dates, currency/timezone,
selected-event and attribution descriptors, producer/query contract versions and
capture time. These are bounded structured provenance, never grants or raw pages.

Recommended constraints:

- Primary key `connection_id`; unique `(connection_id, window_token)`.
- Composite FKs `(connection_id, workspace_id)` to MetaConnection and
  `(account_id, workspace_id, integration_id)` to AdvertisingAccount's existing
  `(id, workspace_id, connection_id)` unique key. Workspace/integration ownership
  therefore cannot be supplied independently.
- Insert binding trigger requires the native row's exact account, integration,
  generation, advertiser, selected event and window, plus current workspace privacy
  revision; ordered dates and reviewed canonical byte limits are SQL checks.
  Python validates exact pure types/canonical descriptors. UPDATE is forbidden;
  DELETE remains available for abort, cleanup and semantic erasure.

Add nullable `presence_context_token` and nullable bounded `presence_json` to
MetaStagedMetric, with a both-null-or-both-present check. Composite FK
`(connection_id, presence_context_token)` references the context. Delete staged
rows before deleting context (RESTRICT is suitable); do not cascade away legacy
numeric staging merely to clear a context. A binding trigger checks campaign
ownership/platform and metric date against the context on INSERT and UPDATE of
presence-bearing rows. Staging itself remains mutable to preserve existing page
retry/upsert behavior. Never UPDATE immutable finalized facts to mirror staging.
Nullable legacy rows remain legal. No migration backfill, defaults, or guessed
presence for existing rows.

Finalized storage uses two new tables:

1. `campaign_performance_semantics`: one immutable header per completion, primary
   key `completion_id`, unique `(completion_id, account_id, workspace_id)`.
   Composite FK to PerformanceCompletion's existing `(id, account_id, workspace_id)`;
   composite account/integration ownership FK as above. Store the canonical
   ReportingSemanticsV1 document, exact digest/byte count and indexed scope scalars.
   Insert binding checks legacy completion platform/source/generation/privacy,
   manifest, dates, currency/timezone, selected event and completion time against
   the new header. Do not reinterpret a legacy query version as a new producer
   contract; persist and validate the two version domains separately.
2. `campaign_performance_metric_presence`: immutable canonical fact rows, primary
   key `(completion_id, campaign_id, metric_date)`, composite FK
   `(completion_id, account_id, workspace_id)` to the header and
   `(campaign_id, account_id)` to Campaign's existing `(id, account_id)` unique key.
   Insert binding checks native campaign identity/platform/date and header scope.
   Store bounded canonical ReportedMetricPresenceV1 plus digest/byte count; avoid
   duplicate numeric columns that could disagree with JSON. All updates forbidden.

Header/fact deletion follows completion/workspace erasure with cascading child
cleanup. The source reference is historical provenance, not a live credential FK
or session requirement. Exact complete set/count/digest validation is a trusted
publisher and reader obligation: per-row SQL constraints alone cannot prove no
facts are missing. Validate header/facts together, including a real empty set.
No header means unavailable legacy presence, never a synthesized zero fact.

## Window And Transaction Contract

Create context only inside the actual no-window initialization branch, under the
existing owned source/workspace locks and transaction, before any first page IO.
Capture original selected event even if null, requested query/attribution basis,
generation, money context and privacy. Resume requires exact same context; changing
configuration while a window is in progress cannot adopt the new producer. An
already-active window without context must finish via the unchanged legacy path
with no sidecar; enabling presence midway cannot fill in the missing prefix.

Parse staged presence from each actual insight row, bound to the immutable token.
Requesting a field does not prove it was returned. Generic/unavailable selected
event identity cannot qualify selected conversion/value cells. Unknown provider
defaults retain unknown attribution. No row returned for a date/campaign means
unknown, not zero. Pagination completion is not all-day/all-entity coverage.

Before terminal staging deletion, collect the bounded complete staged fact set
and original context; revalidate ownership, generation, event, dates, privacy and
money context. Preserve existing legacy publication and its exact digest. Bind
the new header/facts to the actual newly created completion, validate complete
set/count/digest, then clear staging/context and commit together. Both rolling and
fixed-window terminal branches require this hook. Do not query an unlocked current
pointer later or attach sidecars in a second transaction. A malformed new context
or partial presence set must roll back terminal publication, not silently downgrade
a partially qualified new window to apparent success. Truly legacy no-context
windows retain the legacy path without new provenance.

Refactor a private publisher return value or same-transaction callback to expose
the exact created completion; retain existing public behavior/manifests. This is a
future implementation seam, not permission to alter the manifest model.

## Lifecycle, Migration And Export

Follow frozen dialect-specific DDL in
`migrations/versions/20261008_0088_catalog_receipts.py:26`; do not import current
application models into the migration. Model metadata must install equivalent
SQLite/PostgreSQL triggers so create_all tests exercise actual guards. Downgrade
refuses if any new header/fact/context or non-null staged presence exists; only an
empty downgrade removes triggers/functions/tables and nullable staging columns.
Do not erase retained evidence to make downgrade pass.

Register every table in `app/lifecycle/registry.py`; finalized rows are ordinary
owned data, not protected execution lineage. Context is owned transient work
related to the existing Meta import, not a new independent queue or lease. Review
local_work classification explicitly instead of adding every table to WORK_FAMILIES.
Include context and staged columns in model/erasure inventories; exclude incomplete
payloads from ordinary customer exports as existing staging is excluded.

Semantic `bump_workspace_export_revision` must erase finalized presence and active
context/presence staging under its existing transaction and lock ordering. Ordinary
`advance_workspace_export_revision` alone must not erase historical-as-observed
facts. On context removal during semantic erasure, either remove its associated
staging rows or clear both nullable fields coherently; no orphan FK or reusable
partial provenance. Connection restart/reconnect must reset context with staging.

Add versioned allowlisted export serializers using the archive's existing snapshot
Session (`app/lifecycle/archive.py:89,153`). Validate canonical payload/scalars,
legacy completion binding and complete fact set for EVERY header, including when
all fact rows disappeared. Fail closed on corruption; original live session,
current native generation and provider IO are not prerequisites to historical
export. Require current customer authorization/privacy delivery fences as today.
Do not apply the current workspace privacy number as equality to all historical
headers after an ordinary correction; semantic erasure removes them instead.
Use existing per-row/global archive bounds unchanged (`archive.py:25–30`);
fact limits must not promise a maximum import always fits one full archive.

## Required Qualification Before Integration

Actual SQLite/PostgreSQL migration tests: foreign completion/account/campaign,
native identity/date mismatch, scalar/payload corruption, forbidden updates,
stage token mismatch and both-null constraint; empty downgrade succeeds and every
populated new surface refuses downgrade. Legacy rows/manifests remain unchanged.

Actual Meta MockHTTP import tests: fresh start, paginated restart, retries, positive
and explicit-zero cells, independently missing count/value, unavailable/generic
event, empty response, context-less pre-upgrade window, flag enablement midway,
detail enabled/disabled, reconnect/event/generation/privacy change, fixed-window
terminal, and publication rollback. Assert no mixed context, no partial current
advance, no retroactive presence and no live calls.

Archive/privacy tests: complete and empty fact sets, missing whole fact set,
corruption, original connection changed, ordinary correction preserves history,
semantic deletion removes all new graph/staging, bounded exports and no orphan.
V3 readers/planner witnesses remain separate dependent work after these checks.

Review performed by source inspection only; no tests, migrations, provider calls
or application edits were run for this proposal. Open decisions: exact reviewed
pure schema/byte bounds, accepted producer attribution evidence, and final root
approval of the publication seam. No inferred provider-default attribution or
historical selected-event provenance is acceptable.
