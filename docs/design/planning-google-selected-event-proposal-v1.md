# Google Selected-Event Evidence — Investigation And Interface Proposal

Docs-only successor of `55bc389`, inspected against frozen W1 `6a3b0f1` and its
quality proposal. No implementation, migration, runtime activation, provider API
call, credential access, test run or W1 mutation. Public Google documentation was
read on2026-10-09. Q01/Q02 and expert/commercial gates remain partial.

## Recommendation And Blocking Decisions

Preserve all existing Google aggregate imports, completion bytes and readers.
First freeze a pure, additive raw-presence/parser contract. A genuine selected
conversion action then requires a separately reviewed query/collection/publication
architecture and versioned consumer binding; it cannot safely be plugged into the
Meta0090 producer or existing V1 storage by changing a descriptor.

Three concrete compatibility barriers precede selected-event implementation:

1. The current Google query has no selected event. Missing raw fields are defaulted
   to0 before `Page`; recovering presence from that normalized document is impossible.
2. Existing presence storage equates present selected count/value with the legacy
   aggregate numeric row, and its header/reader require the completion's same event.
   Google aggregate completions have `selected_event=None`. A real selected subset
   must not be equated with the sum of other events or rewrite old immutable bytes.
3. Google publishes one current completion per at-most-seven-day import window.
   September and August cannot be projected from that completion by replacing its
   dates or combining mutable daily rows without new publication provenance.

Additionally, the straightforward action-segmented Google query cannot establish
explicit zero from an omitted action row. This is a provider-semantics gap, not a
license to weaken frozen Q02. A raw explicit0 parser test is useful but is not proof
that this provider query supplies explicit0 in production.

## Inspected Existing Seams

| Source | Existing behavior and implication |
| --- | --- |
| `app/google_connections/http.py:GoogleHTTPRead.page` | Two phases, campaigns then campaign/date metrics. GAQL selects impressions/clicks/cost/conversions/conversions_value, no conversion action. `.get(...,0)` loses absence; Decimal quantization and value-to-micros conversion follow. Capture original key/token presence before this step. `_request` currently JSON-decodes ordinary numbers; a new exact-decimal path must preserve raw numeric lexemes without silently changing legacy decoding. |
| `app/google_connections/contracts.py:MetricRow,Page` | Only normalized campaign/day values; no event, attribution, per-field presence or query evidence. Preserve these DTOs and old serialization. The SDK `wire.py` is fixture-only and protobuf/defaulted attributes do not establish raw presence. |
| `app/google_connections/service.py:choose,owned,tick` | Workspace then owned connection lock; exact generation/connected grant check and advertising import scope. Initial90-day history is traversed in seven-day windows. `tick` holds these locks across existing provider I/O; do not claim the later planning reader's outside-SQL I/O guarantee applies here. |
| `service.py:tick` pages/staging | Max100 pages/50,000 combined campaign+metric rows, repeated cursor rejection, exact advertiser check, conflicting duplicate campaign/day rejection. Pages and descriptor persist atomically with next cursor. Terminal campaign mapping, daily-row replacement, job, publication, window advancement and pending analysis outbox commit together. |
| `app/campaign_performance/aggregate.py:descriptor,stage_contract,publish` | Concrete adapter type, not duck typing, qualifies query descriptor. Existing staged pages with no descriptor remain legacy; mismatch rejects. Publication invalidates calibration first, then captures actual privacy revision, new immutable manifest/completion and current pointer. Returns no completion ID today. Google descriptor names aggregate `metrics-conversions.v1`, eventNone/unspecified attribution. |
| `app/google_connections/dispatcher.py:run_imports,deliver_analysis` | Transient read failure retains stage for retry. Other rejected imports clear cursor/stage after rollback against the same connected generation. Pending analysis retries independently and does not rerun successful import. New stage context must survive transient failures and remain pinned even across rejected-window restart. |
| `service.py:choose,disconnect` and authorization failure | Reauthorization/disconnect invalidate privacy and advance generation; old queued generations reject before I/O. New selection/context must be cleared or invalidated in these same owned operations, never inherited into a new generation. |
| `presence_storage.py:_completion_binding,store_presence` | Exact owned completion/current pointer/privacy and campaign mapping, full manifest row set. Present selected count/value must equal `DailyMetric.conversions/conversion_value_micros`; header event must match completion. These are real invariants, not checks to disable for Google. |
| `presence_report.py:CampaignPerformanceV3.consistent` | Legacy nested bytes and header event/period/source bindings must agree. A selected-action header cannot be bolted onto existing aggregate completionNone. |
| `window_projection.py:_derive`; `planning_documents/window_reader.py` | Requested local calendar days must be closed and contained in the original header. Reader pins one current owned completion and entire source graph, not just requested slice. Complete selected-zero requires explicit-selected identity and complete observed requested-day coverage. |
| `app/settings.py:google_customer_api_version` | Defaults empty; no production API version is approved by these docs. New query capability must explicitly pin a supported version and validate field compatibility for it. |

## Provider Facts And Their Limits

Google documents action-segmented conversions and values, with zero-conversion
rows excluded. It also cautions that conversion data is delayed. Therefore an empty
successful response proves a completed query, not an explicitly observed numeric0
for each campaign/day. We must retain missing counts and independent value presence.
[Google conversion reporting](https://developers.google.com/google-ads/api/docs/conversions/reporting).

Google also documents suppression of all-zero metric rows. Inventory existence or
completed pagination cannot be used to manufacture calendar-day observations.
[Google zero metrics](https://developers.google.com/google-ads/api/docs/reporting/zero-metrics).

A conversion action's customer may be a manager acting for the advertising
customer. Verify the actual conversion-tracking customer relationship; do not assume
that action owner, login manager and advertiser IDs are interchangeable. Until that
relationship is supported and observed, report an unsupported/unknown identity gap.
[Google conversion setup](https://developers.google.com/google-ads/api/docs/conversions/getting-started).

Conversion-action configuration has lookback fields and goal-related metadata, but
an observation of current configuration does not establish its historical value
through August/September. Preserve observation time and distinguish request time
basis from observed current configuration. Do not infer a default attribution window
or infer an event merely from a purchase label/primary flag.
[Google ConversionAction reference](https://developers.google.com/google-ads/api/reference/rpc/v24/ConversionAction).
These public references inform proposal semantics; they do not qualify an actual
configured API version, authorized account, or live response.

## Proposed Private Ports — Not Yet Frozen Or Implemented

Use strict frozen contracts with bounded canonical serialization, copied-instance
revalidation, explicit schema versions and `spending_authority=none` throughout.
Reuse reviewed cell bounds (Integer2^31−1, Numeric18,6, micros2^63−1); no rounding
unsupported precision into purported observed evidence.

### 1. Raw Observation And Capture Identity

`GoogleReportingCaptureV1`:
- Server-created capture ID; workspace/integration/account/native connection ID,
  generation and captured privacy fence; exact advertising customer and optional
  independently verified login/conversion-owner customer references.
- Requested inclusive local start/end, currency and IANA account zone, capture
  start time, explicit API version and exact query-profile digest.
- Selection revision/digest and exact `customers/{id}/conversionActions/{id}`
  reference, or explicit unavailable selection. Selection comes from a separately
  owned server-validated event catalog/choice, never a display label or inferred
  Google default. That catalog/choice persistence is currently missing.
- Exact metric family (`metrics.conversions`, not silently `all_conversions` or
  by-conversion-date variant), request time basis, separate nullable observed
  attribution configuration and observation timestamp. Unsupported fields stay
  unknown; current settings are not historical facts.

`GoogleObservedCampaignDayV1` (pure parser output, not authority):
- Capture digest; exact campaign native ID/date; independently present/missing
  impressions, clicks, spend, aggregate count/value from the original unsegmented
  raw row. Pair with the unchanged normalized `MetricRow` and validate every
  present legacy field numerically. Malformed/null/missing are not explicit0.
- Separate selected-action count/value cells plus exact action reference and
  query-phase identity. Preserve explicit0 only when the raw value actually exists;
  missing row/key/null is missing. Never copy aggregate count into selected count.
- Exact resource/customer/day bounds and duplicate equivalence; fractional counts
  remain Decimal, money requires exact integer micros. Conflicting duplicate raw
  presence (absent versus explicit0), even with equal legacy normalized numbers,
  must reject qualified publication.

A new concrete, capability-checked transport method/envelope should return both
legacy Page and paired raw facts. Do not add a permissive attribute that arbitrary
fixture transports can use to qualify themselves. Old `page()` callers remain
legacy and cannot adopt selected evidence mid-window. Routine work here is pure
mapping/validation; new GAQL phases are a separate implementation freeze.

### 2. Distinct Queries And Exact Join

Retain the existing unsegmented traffic/cost query. Proposed additional phases are
owned conversion-action metadata and action-segmented campaign/date conversions and
values, selecting the exact action reference explicitly. Validate the complete GAQL
field combination against the configured version before implementation; this doc
is not a claim that all traffic metrics can coexist with conversion-action segments.

Join only identical capture/advertiser/campaign/local-date keys. Do not multiply
clicks/spend by event-row count. Preserve selected-event rows without a matching
legacy daily row as a controlled qualification gap/rejection until their publication
representation is frozen; never invent a base row or drop unmatched selected facts.
Complete each phase and its pagination independently. A timeout/error is not a known
empty report. No campaign/ad-group performance is inferred from native names alone.

### 3. New Immutable Selected-Evidence Binding

Recommend a versioned, additive `GoogleSelectedEventPublicationV1` (name provisional),
not relaxation of `store_presence` or alteration of PerformanceCompletion/V1/V2 bytes.
Bind the exact existing aggregate completion ID+manifest to a separately immutable
selected-action header/fact digest and verified collection/query/context metadata.
Traffic and aggregate cells validate against existing rows; selected cells validate
against their own actual completed raw-query graph. Distinct totals remain distinct.

An additive schema and serializer/erasure/export/downgrade contract is required.
Owned composite keys must bind account/workspace/source/generation/capture and
campaign mappings. Inserts are all-or-nothing; identical replay is accepted only
for identical graph, changed digest/rebound scope rejects. Readers validate the
complete graph and original manifest before projection, including changes outside
the displayed slice. Old-source absent sidecars remain unqualified forever.

Consumer support also requires a new explicit versioned evidence envelope/policy
capability and retained witness; current V3 header-to-legacy selected-event equality
cannot represent this independent subset. Do not direct-cast or relabel a document
to bypass that invariant. Freeze this consumer change before parallel consumers.

### 4. Whole-Window Publication Choice

Recommended initial collection architecture: an explicitly owned bounded capture
for the exact union of requested closed windows (for the frozen case, August1 through
September30 inclusive), with separate immutable capture context, all query phases,
and atomic terminal publication. Reuse current repository normalization and owned
locking patterns, but do not hijack a scheduled connection's seven-day cursor or
broaden a running legacy import. Limits must be reviewed explicitly against existing
50,000-row/100-page bounds; exceeding them returns a bounded unavailable result,
not a truncated complete claim. No new numeric production limits are approved here.

This is NEW collection/publication architecture, not a routine adapter mapping.
Its terminal aggregate completion must genuinely cover that queried range. Existing
weekly publication may subsequently replace/invalidate it; handle that honestly as
source advancement until a separately reviewed range-aware current-source design
exists. Never keep advertising a stale capture as current to improve availability.

Alternative: retain existing seven-day scheduling but introduce an immutable range
manifest referencing every exact completed partition, with gap/overlap/event/query/
generation/privacy agreement and whole-range currentness checks. This requires a
multi-completion reader/witness, because today's single-current-pointer reader cannot
provide it. It is more extensive than the first explicit-range candidate. Simply
publishing a monthly header over mutable historic DailyMetric rows is rejected.

Neither option is approved or implemented. Root should freeze one before code.

## Transaction, Retry And Privacy Requirements

Capture context is fixed at the actual new-window/capture start, before raw query
I/O; the connection/workspace/source/selection fences are checked again at terminal
publication. Preserve it across transient errors and rejected retries of that same
capture. No mid-window upgrade from legacy, changed API version, changed event,
changed range or changed source generation. Existing dispatcher reset logic must
not erase the proof that a restarted same-window attempt was legacy/unqualified.

Terminal transaction: verify original owned context and complete query phases;
validate legacy numeric pairs and selected graph; write actual metric rows;
invalidate applicable calibration; obtain final post-invalidation privacy revision;
insert completion, graph and current reference plus durable analysis outbox; advance
or close capture, commit. Rejected sidecar/context rolls everything back; no qualified
completion without its complete graph. Capture's original privacy observation and
final completion revision are separate facts, as already required for legitimate
calibration invalidation. Do not globally bypass privacy checks.

Crash before commit leaves no publication; crash after commit replays the exact
receipt, not another imported effect. Simultaneous workers serialize on the same
owned capture. Reconnect/disconnect, event-selection revision and semantic erasure
fence old work before publication and delete relevant erasable graph. Ordinary
correction creates a new completion and makes retained advice stale; it does not
retroactively mutate old plan bytes. Source proofs include absent sidecars and the
entire graph, not merely returned September rows. Current planning identity/session,
paid-read permissions and final authority deadlines remain unchanged.

## Exact Acceptance Before Any Q01/Q02 Claim

Use the unchanged frozen common basis: USD/New_York, September2026 primary,
August2026 comparison, November planning, confirmed$12,000/$8,000 goal basis,
$1,000 ceiling and customer mug/image facts. Source-local half-open API periods are
September1T00:00−04:00→October1T00:00−04:00 and August1T00:00−04:00→September1T00:00−04:00.
Do not replace them with seven-day UTC examples or forge completion dates.

1. Pure parser: explicit10/0, absent/null, independent missing value, decimal
   precision/overflow, conflicting duplicates, swapped advertiser/action/campaign/
   date, copied nested instances; raw exact100clicks/$100 with selected10 does not
   become aggregate-event identity. A different aggregate total, e.g.12, must remain12.
2. Actual MockHTTP importer on SQLite/PostgreSQL: multi-page and all phase joins,
   repeated cursor, phase interruption/retry, stale selection/source/permission,
   forged ownership, terminal rollback, committed replay and concurrent workers;
   immutable graph+manifest and empty/no-sidecar legacy behavior verified by SQL.
3. Actual customer create/generate/read/export with observed campaign+ad-group names
   and IDs: Q01 shows100clicks,10selected,$100 and never a no-conversions finding;
   separately report coverage and comparison gaps. No budget or ad-account mutation.
4. Q02 unit/contract explicit0 remains distinguishable from absence. Actual Google
   action-query suppression cannot yet qualify the full production explicit0 path.
   Missing selected rows must be unavailable even when aggregate0 exists. If a future
   verified provider contract supports explicit or derived zero, it needs its own
   provenance and reviewed contract; do not label derived zero as observed explicit0.
5. Sparse days/month gaps stay visible; September partial selected totals cannot be
   labeled complete-month totals. August has its own exact evidence, not a relabeled
   September response. Unknown attribution prevents comparison claims where relevant.
6. Correction outside displayed slice invalidates the complete original witness;
   reconnect changes generation; semantic erase removes graph/replay/export access;
   unchanged old PlanVersion bytes and legacy report hashes survive ordinary updates.
7. No inferred causal sales, total unique customers, cross-provider CPA ranking,
   financial exposure release, or authority from reports. Human expert judgments and
   complete quality acceptance remain separate from these mechanical assertions.

## Proposed Next Freeze

Approve only a pure raw/parser contract first. Separately choose the selected-action
catalog/choice binding, exact supported API-version/query semantics, additive
selected-evidence storage/consumer envelope, and full-range publication option.
Q16 remains independently implementable now. Q01 positive partial evidence can then
progress, but Q02 explicit-zero live feasibility remains a documented provider gap;
no new provider architecture is authorized by this investigation.
