# Owned Current Campaign Performance

Implemented first producer: Meta terminal campaign/day import. Migration 0074 follows 0073.
This supplies actual reported facts for later initial-policy calibration. It is not
mature action feedback, causal evidence, a policy or permission to spend.

## Frozen Interfaces

`app/campaign_performance/models.py:PerformanceCompletion` is immutable completion
metadata with an owned `(account_id, workspace_id)` foreign key. Fields bind the source
connection reference/generation, workspace privacy revision, exact inclusive local report
window, currency/time zone, query version, event selection, reporting basis, completion
time, row count and a domain-separated canonical campaign/day digest. The database
rejects updates; deletion is allowed for lifecycle erasure. No historical metric body
is stored. An old completion ID cannot reconstruct an old report.

`CurrentPerformance` holds one reference per account. Its composite FK includes completion,
account and workspace. `publish_meta(db, source, start, end, now)` runs after all pages
inside the existing import's terminal transaction; digest computation, completion insert,
reference replacement and metric replacement commit or roll back together. Failed/partial
pages cannot create a new completion. Metadata registration and lifecycle scalar export/
erasure classification include both tables.

The digest includes exactly campaign/day grain, ordered by owned local campaign ID and
date. It includes impressions, clicks, cost micros, fixed-six-place conversion decimal
and value micros. The manifest query fetches at most 100001 rows, rejecting anything above
100000 without truncation. It never adds ad-set/ad-group/ad rows to campaign totals.
The existing importer has the same campaign staged-row capacity. In-memory normalized
rows are temporary; only the digest and row count are retained in completion metadata.

`read_current(db, workspace_id, actor, account_id, campaign_id,
expected_completion_id, authorize) -> CampaignPerformanceV1` requires an original-session
owner authorization callback, then locks the current Meta source under the workspace
fence. It validates current account/native identity/integration, connected status,
generation, event, privacy revision, currency/time zone, exact coverage and completion
time. It reloads mutable rows and recomputes the full bounded manifest before aggregating
one owned campaign. Optional expected completion is a stale-preview fence, never proof.
It reauthorizes before returning and does not commit or perform provider IO. Consumers
must call it again at every future approval/use boundary; no numeric preview is persisted
in this package. A caller must not replace authorization with inferred ownership.

`app/campaign_performance/contracts.py:CampaignPerformanceV1` is the strict frozen
current-reader document. Unavailable conversions/value are nullable. Empty sparse
campaign reports are unavailable, not observed zero. A selected purchase event with a
returned zero row yields actual zero. CPA is undefined for zero/unavailable conversions;
reported ROAS is undefined for zero spend or unavailable purchase value. Returned
reported-day count does not assert daily completeness or zero-fill omitted dates.
Every response states reporting basis `provider_defaults_unspecified`, maturity
`unqualified`, causal attribution `unavailable`, spending authorization false.

## Current And Historical Limits

During an unfinished replacement the reader may return the unchanged last completed
report, explicitly with its original completion time/window. Error state rejects reads.
Completion time is an import observation, not a provider finality watermark or performance
freshness approval. A future policy must declare and validate its own age/window bounds.
Correction/reference change, reconnect generation, changed conversion selection, privacy
revision or direct row drift rejects previous evidence. Unknown attribution settings are
not filled from current configuration. No provider defaults are declared final or causal.

Google/TikTok producers are not implemented in this package. Their differing aggregate/
generic conversion semantics cannot inherit Meta's explicit selected-event meaning.
Next calibration/initial preview needs reviewed interfaces and explicit numerical inputs;
no first-policy defaults, new learning schema registration, UI or execution route is added.

## Verification

Tests use the actual MetaClient urllib request/parser with a bounded in-memory HTTP opener,
then actual page/staging/terminal transaction and SQLite/PostgreSQL reader. Fake OAuth
setup is a fixture only; no provider calls or credentials are used. Tests cover terminal
publication, source/row/privacy/session invalidation, unknown versus true zero, sparse
correction, overflow rollback, and actual 0074 update rejection/composite FK/cascade and
roundtrip. Existing Meta connection/detail tests and lifecycle/model registry suites
exercise integration. Exact counts are recorded in the progress ledger.

## Google And TikTok Successor (No New Migration)

`aggregate.ReportingDescriptor` is frozen and validates its provider/query version.
Only concrete GoogleHTTPRead/TikTokHTTPRead instances produce accepted descriptors;
arbitrary adapters or copied properties do not supply reporting provenance. Google binds
its explicitly pinned HTTP API version; TikTok binds the existing v1.3 BASIC campaign/day
query. Each import stages the descriptor across pages. Conflicting observed descriptors
are rejected. Legacy staged pages lacking a descriptor may finish ordinary import, but
remain unqualified throughout. Terminal unknown/unqualified writes delete the current
performance reference even when metric values are unchanged. No compatibility restart
is required merely because old staged pages lack the new field.

Google `tick` publishes after terminal normalized campaign/day replacement and before
advancing the next backfill/refresh window. Its reference describes exactly the last
completed bounded slice, which can be an older historical week. It never asserts all
backfill coverage or that the completed slice is the newest calendar interval. Reader
checks completion/current identity and last_sync_at; it does not compare captured dates
to the already-advanced next import window. TikTok `tick` publishes within the same nested
transaction as terminal campaign/group/ad replacement; the manifest includes campaign
rows only, and the reader verifies exact covered_from/through.

The explicit `CampaignPerformanceV2` variant handles these providers. Meta v1 fields and
serialized bytes remain unchanged. Google exposes platform aggregate conversions/value,
with no selected event or purchase/Shopify attribution claim. TikTok exposes only a
separately labelled `reported_generic_conversions`; conversions, conversion value, CPA
and ROAS remain null. Its storage value placeholder zero never becomes observed revenue.
Sparse absent rows remain unavailable. Both return unqualified maturity, unavailable
causal attribution and no spending authorization. Consumers must handle the versioned
union explicitly; this is not a qualified-learning schema or calibration registration.

All three current readers additionally use existing `validate_advertising_scope` under
the workspace→native source→account/integration locks, so a separately revoked integration
cannot be bypassed by a retained connected native row. Actual row digest, generation,
privacy and original-session checks remain mandatory.
