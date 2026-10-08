# Requested Reporting Windows And Comparisons — Proposal Only

Review base: `471bb83`. No implementation, tests, provider requests, or qualification
are included. This proposes an additive interface for review before dependent work.
Existing report DTOs, provider headers, imports, policies, and stored artifacts keep
their meanings and bytes. No advertising writes are introduced.

## Observed Current Behavior

- `app/meta/sync.py` chooses the closed rolling interval ending yesterday and
  starting 55 days earlier. Ordinary Meta import therefore covers 56 local days.
- `planning_documents/evidence_adapter.py` reconstructs the completion's full
  inclusive date interval as local-midnight instants. Unless that interval exactly
  equals the input primary or comparison window it emits
  `reporting_window_mismatch` with a verified original document pin. A contained
  seven-day request is currently a gap, even with useful rows in the completion.
- `campaign_performance/presence_report.py` deliberately binds V3's original
  presence header to its legacy report's full dates, completion, generation,
  manifest, selected event, currency, timezone, and complete campaign row set.
  Its summary is of that original window. Changing the header dates or replacing
  its whole fact digest with a requested-window digest would falsify this contract.
- `presence_summary.summarize_presence` validates a whole graph, then calculates
  counts against the header's provider-requested dates. It cannot be reused with
  a relabeled header. `campaign_summary`'s private campaign-only commitment is
  explicitly a recomputation detail, not a replacement for whole-source proof.
- `PerformanceEvidence.exact` binds evidence windows to the report's dates.
  `EvidenceBundle.assert_ticket` allows primary/comparison windows but the adapter
  emits only its one current completion window and an additional comparison gap.
  Keys `performance:<account>:<campaign>` do not distinguish two requested windows.
- `composer.py` uses the primary-window entry when constructing an action; it does
  not calculate a paired descriptive performance comparison. The existing portal
  comparison renderer concerns plan versions, not reporting-period comparisons.
- `portal/static/planning.mjs` submits `comparison_window:null` and refuses to edit
  an existing non-null comparison. `input_resolution.prepare` already preserves
  API comparison input. `PlanInputRevision` requires comparison end no later than
  primary start; its general `ReportingWindow` does not enforce local midnight.
- `retained_sources._reporting(qualified=True)` independently validates the current
  completion and recomputed legacy manifest, plus the whole presence header/facts
  or exact absence. Its `local_reporting_v2` fingerprint includes scoped account,
  source/generation, privacy, completion, and bounded local/native campaign mapping.
  Policy selection is currently exact equality with `inlet.descriptive-review.v2`.

## Recommended Smallest Additive Contract

Introduce **RequestedWindowPerformanceV1**, schema
`inlet.requested-window-campaign-performance.v1`, rather than alter V1/V2/V3 or
pretend that a new provider query occurred. Start with projections backed by an
actual V3 presence graph. Keep all three platforms selectable; absence of such a
graph is an explicit per-window gap, not zero or a source authorization failure.
Existing full-window legacy metrics can remain available under their existing
qualified/unqualified semantics; never copy a 56-day total into a seven-day field.

Proposed strict, frozen, revalidated DTO fields:

| Field | Binding / Meaning |
| --- | --- |
| `schema_version` | Exact new literal above. |
| `projection_version` | Exact `inlet.reporting-window-projection.v1`; a local derivation, not provider query version. |
| `original` | Unmodified `CampaignPerformanceV3`, including original legacy report, original provider header, and all original campaign facts. |
| `original_document_digest` | Existing `fingerprint('campaign-performance', original.model_dump(mode='json'))`; validate equality. |
| `requested_window` | Exact aware half-open customer window; no rounding or date truncation. |
| `requested_starts_on`, `requested_ends_on` | Derived inclusive dates in `original.time_zone`, not independently accepted claims. |
| `selected_facts` | Exact stable ordered subset of `original.campaign_facts` within those dates; maximum 400; equality checked, no dropped or introduced row. |
| `selected_fact_digest` | Digest of exactly `selected_facts`, explicitly distinct from original header's whole-completion digest. |
| `summary` | Deterministically recomputed requested-day counts and metric cell aggregates; new `WindowCampaignSummaryV1` type, not reinterpretation of existing summary DTO. |
| `derivation` | Literal `local_projection_of_imported_campaign_days`. |
| `causal_attribution`, `spending_authorized` | Literal `unavailable` and `False`. |

New summary fields mirror useful metric/count fields of `CampaignSummaryV1` but
are explicitly about the requested window. Strict numeric bounds, fixed decimal
`Context(prec=50)`, null-vs-zero rules, duplicate/date/native-identity checks, UTF-8
byte limits, and model-copy revalidation are required. Keep the existing 2 MiB
per-report and 32 MiB collection bounds; measure both primary/comparison wrappers,
including duplicated original bytes. Capacity failure aborts without truncating
or claiming complete coverage. No schema migration is expected: the DTO is
transient; plan evidence references and immutable local witnesses already persist.

### Private Interfaces To Freeze Before Implementation

Proposed new module: `app/campaign_performance/window_projection.py`.

```python
def project_requested_window(
    original: CampaignPerformanceV3,
    *,
    full_header: ReportingSemanticsV1,
    full_facts: tuple[ReportedMetricPresenceV1, ...],
    requested_window: ReportingWindow,
) -> RequestedWindowPerformanceV1: ...
```

This is pure and non-authorizing. First validate the complete original header and
whole fact graph with `validate_presence`; require header equality with
`original.presence`, exact original campaign/local/native mapping and campaign
subset equality. Then derive the requested subset. Do not manufacture a temporary
`ReportingSemanticsV1` with different requested/actual dates, even privately.
Extract or introduce a pure per-cell aggregation helper if needed, while keeping
existing public summarizers' outputs and validation unchanged. Full source graph
inputs remain server-owned and never arrive as a customer's supplied proof.

Proposed DB-facing helper (new module or additive function, not a change to old
`read_current_with_presence` behavior):

```python
def read_current_requested_window(
    db: Session, workspace_id: int, actor: str, account_id: int,
    campaign_id: int, expected_completion_id: str,
    authorize: Authorize, *, requested_window: ReportingWindow,
    context: PresenceReadContext | None = None,
) -> RequestedWindowPerformanceV1: ...
```

Use the actual current owned completion/manifest reader and whole presence reader,
then the pure projector. Reuse only a transaction-bound context under the existing
source locks. Unsupported projection has a dedicated typed known-data condition;
authentication, scope, manifest, mixed graph, capacity, or source changes abort.
No generic HTTP 409 or storage error may be converted to a benign gap. Identity
refresh stays before DB contexts; final authority/source/expiry checks remain after
all waits. No DB transaction spans provider I/O and no new I/O is required here.

## Window And Qualification Rules

1. Convert input instants into the source's actual IANA timezone and require exact
   local midnight, including seconds/microseconds. Compare the resulting boundary
   instants with constructed local calendar boundaries using a UTC round-trip;
   reject nonexistent or ambiguous midnight boundaries rather than guess a fold.
   Do not compute day count as elapsed seconds / 86,400: DST days can be 23/25 hours.
   Require 1–400 distinct calendar days and containment in the original requested
   interval. Do not silently intersect an out-of-range input with available data.
2. The requested last day must precede the original completion's local date. Time
   passing now cannot retrospectively qualify an originally open day. Keep the
   original closed-period flag visible; proposed conservative v1 complete coverage
   additionally requires original `closed_requested_period=True`.
3. Complete metric coverage requires original pagination complete, requested dates
   fully inside the original actual interval, every requested day represented once
   for this exact campaign, and that metric's cell present on every such day.
   An original actual interval narrower than the original query can still cover an
   interior requested subset; expose original bounds unchanged. Outside actual
   coverage may yield partial observed sums, never full coverage or observed zero.
4. Missing returned dates increment `missing_calendar_days`; returned rows with
   absent selected action increment that metric's missing-cell count. Neither is
   filled with zero. All-missing/unavailable metrics have `value=None`. Partial
   observed sums are labeled partial. Positive 10 remains positive; a partial sum
   of zero never yields `selected_zero_for_requested_window=True`.
5. Selected zero requires explicit original selected-event provenance and complete
   requested-day selected-count coverage with exact total zero. Generic conversion
   totals, provider defaults, missing action arrays, and unavailable Google/TikTok
   selected-event presence are not selected zero. Count and value stay independent.
6. Attribution is copied as original metadata, including unknown click/view windows
   and report-time basis. A local slice does not establish attribution, causality,
   delivery timing, reconciliation with Shopify, or cross-platform comparability.
7. Comparison and primary windows must be disjoint with comparison ending no later
   than primary start, and individually satisfy the same local/date rules. Do not
   require equal duration just to display two labeled totals. Any delta/rate
   comparison needs an explicit comparable-duration/metric-basis rule; initially
   prefer labeled side-by-side values and reasons over inventing normalized lift.
   The same UTC input may fail local-midnight alignment for another account's
   timezone: report an explicit account/window gap, never shift that account's dates.

## Policy, Evidence, And Retained Proof Integration

Reserve an explicit new composition pair, proposed
`inlet.descriptive-review.v3` / `inlet.descriptive-planning.v3`. Do not reinterpret
existing v2 or change its golden outputs. Add a new evidence document union branch
only for this pair; old policy branches reject the new DTO. Preserve input schema
bytes/defaults. If comparison output needs structured public fields, give that
output a separately versioned section/DTO rather than add default fields to old
hashed plan documents. This public comparison shape requires its own reviewed
interface before UI work; source slicing alone is not comparison completion.

Evidence references use the projection schema/digest and exact requested window;
source-binding digest stays the original manifest. Retain original generation,
completion time, native identity, selected-event/attribution metadata. Keys must
include account, campaign, and a canonical requested-window digest so two windows
cannot collide. `assert_ticket` must require exactly the requested account/campaign/
window entries or explicit per-window gaps, and reject duplicate, swapped, or
unrequested window references. Current account-level gap shapes need an additive
window-qualified gap type rather than silently changing old mismatch-pin meaning.

Collect primary and comparison from the same verified current completion when it
contains both. Missing/out-of-range comparison does not erase valid primary
metrics. No searching historical completion IDs or stitching imports with changed
semantics is proposed. Current-only storage remains honest about unavailable
historical windows. Final generation recheck reconstructs both requested projections
from the actual current source and checks exact new document digests, complete
whole-graph reporting pins, native mapping, privacy, and final time boundaries.
It must also reconstruct known gap predicates, not only successful projections.

`local_reporting_v2` can be reused **unchanged** for this new explicit policy
because it commits the whole source state independently of a requested slice.
Replace scattered equality tests with one explicitly reviewed policy capability
mapping for v2 and proposed v3; leave v1 on `local_reporting_v1`. Do not broaden to
arbitrary unknown policy strings. Preserve the existing fingerprint domain and
state fields exactly, including sidecar absence. Stored input windows plus new
projection evidence digests distinguish derived outputs; the local witness remains
source integrity, not a claim that old v2 produced subset reports. Changes outside
the requested subset still invalidate currentness because the whole graph changed.
Legacy/missing/duplicate witness rules, viewer DB-only reads, immutable dependency
lifecycle, original deadline, and privacy/export behavior remain unchanged.

## Required Future Qualification Matrix

- Pure: contained seven-day projection from a genuine 56-day graph; exact originals
  retain bytes/digests; verify no private header replacement. Boundary equality,
  out-of-range, non-midnight, DST transition, invalid zone, ambiguous/nonexistent
  midnight, open-day, >400 days, tampered/cross-campaign/duplicate/swapped facts.
- Per-metric: positive 100 clicks / 10 selected conversions / $100; seven explicit
  zero days; one absent selected action; one absent calendar day; all missing;
  independent selected value; partial pagination/actual bounds; fixed arithmetic
  under hostile ambient Decimal context. Positive never becomes no-conversions.
- Actual Meta MockHTTP rolling import -> real owned planning API -> requested
  primary seven-day and preceding seven-day comparison -> current/history/export,
  SQLite and PostgreSQL. Distinct evidence keys and preserved original 56-day header.
  Do not replace the real producer header with a synthetic seven-day header.
- Source races: same-pointer fact corruption, mapping/generation/privacy changes,
  new completion, missing sidecar, and changes outside both slices must prevent
  commit or make retained output stale. Missing comparison becoming available must
  invalidate its old gap. Revocation/final expiry rollback and viewer reads remain.
- Google/TikTok actual current sources without selected presence stay explicit gaps
  or their existing exact-full-window generic reports, never qualified selected
  zero. Future producer support needs separate original-presence evidence; no
  cross-platform common-event/attribution claims from platform labels.
- Golden legacy V1/V2/V3, v1/v2 policy plan bytes and stored digests unchanged;
  unknown policy/new DTO with old policy rejected. No mutation of migrations or
  historic completion/header rows. Bounds checked before partial persistence.
- Later actual HTTPS UI: choose primary/comparison, preserve both on edit, show
  original queried interval separately from requested analysis interval, display
  gaps and date/timezone labels, and clear stale/out-of-order/session-changed data.
  Keep plan-version comparison separate. No automatic provider reread or silent
  account-date adjustment.

This proposal does not close Q01/Q02/Q09 or any frozen quality case. It addresses
requested-window availability while retaining the selected-event producer gaps,
unknown attribution, honest native-budget limits, and separate read-observed
progress requirements. Implementation and all checks above remain pending review.
