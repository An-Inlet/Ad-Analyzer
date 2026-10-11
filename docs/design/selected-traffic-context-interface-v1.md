# Raw Range Traffic Alongside Selected Conversions — Interface Proposal

## Concrete Gap And Minimal Recommended Change

CampaignPerformanceV2 contains whole-completion totals, so its61-day total cannot
be relabeled as September or August. Further, ordinary GoogleHTTPRead and the strict
GoogleAggregateRangeHTTP currently share the same query-version string. The former
normalizes missing numeric cells, so query_version alone cannot certify presence.
A RangeReceiptV1 proves a retained owned range publication, but its acquisition_digest
is an opaque commitment, not reconstructable raw response cells. Do not retrospectively
infer cell presence from DailyMetric defaults, receipt existence alone, or that hash.

Recommended minimum: during the existing actual raw range publication transaction,
persist a dedicated traffic-only presence profile using the ALREADY EXISTING immutable
ReportingSemanticsRow/MetricPresenceRow tables. Construct cells from the still-present
validated GoogleAggregateRangeV1 result, not by re-reading numeric SQL defaults.
No new migration or table is needed. Read/projection contracts below require BOTH the
exact RangeReceiptV1 and this new concrete profile; old receipts without it yield an
explicit provenance gap and need a new deliberate range acquisition. Never backfill
a presence sidecar from old mutable rows or reinterpret a legacy producer.

## Atomic Publisher Port

New internal helper (name proposed):
store_raw_range_traffic(db: Session, *, receipt: RangeReceiptV1,
                       result: GoogleAggregateRangeV1,
                       campaign_mapping: Mapping[str,int]) -> None.
No commit, network, identity lookup or caller authority replacement. Caller owns final
workspace/source locks and transaction. Call after actual completion/receipt are
constructed and before final readback/guard/commit. Failure rolls back metrics,
completion/pointer, job, receipt AND sidecar; preserve scheduler fields.

Validate exact result request account/source/generation/native identity/units and
inclusive dates against receipt.original_scope (privacy may advance ONLY through
the existing known publication invalidation). Receipt.final_scope matches resulting
completion; acquisition_digest==result.digest. Mapping is the actual owned campaign
upsert mapping, injective, exactly covers result.campaigns, and matches stored
account/campaign identities. Fact cells come directly from result.metrics:
impressions=present integer, clicks=present integer, spend=present integer micros.
Both selected fields=unsupported/None: metrics.conversions from the aggregate query
are NOT selected conversion counts. Omitted rows stay omitted. All five required
raw aggregate cells remain required by the existing reader; no query weakening.

ReportingSemanticsV1 exact producer_contract:
`google.v24.campaign-day.raw-required-traffic.v1`.
query_descriptor remains `google.v24.campaign-day.metrics-conversions.v1`.
selected_event={provenance:generic,native_event_id:None,label:None}; attribution is
provider_default_unknown with no windows. Exact receipt completion/source/privacy/
manifest/currency/timezone/date bounds; pagination_complete=true and
closed_requested_period=true. actual interval means the queried acquisition interval,
not evidence that every day produced a row; match requested bounds, including empty
results. fact_count and presence_digest cover the whole sorted fact graph.
Existing store_presence already matches every fact to actual manifest rows and exact
local/native campaign ownership and refuses immutable replay differences.

This profile is server-writer provenance, not a Google-signed completeness guarantee.
It certifies the deployed parser required those cells on every returned row and that
the atomic writer retained them. Mock fixtures prove this code path, not live support.

## Shared Pure DTOs (New selected_traffic.py Or Equivalent)

TrafficCampaignBindingV1 reuses SelectedCampaignBindingV1 exactly.

RawRangeTrafficGraphV1(Frozen):
- receipt: RangeReceiptV1 (complete existing canonical receipt, <=16KiB)
- header: ReportingSemanticsV1 (exact new profile; <=existing8KiB)
- facts: tuple[ReportedMetricPresenceV1,...] (<=50,000, sorted unique campaign/day)
- campaigns: tuple[SelectedCampaignBindingV1,...] (<=10,000, complete owned sorted map)
- source_fence: SourceFence
- canonical graph <=32MiB; all copied instances revalidated.

Require receipt/header exact metadata, header fact digest/count, traffic-present and
selected-unsupported cells, exact map/source/scope, every fact in the map/date interval.
No generic conversions included in its exposed traffic summary. Bind the entire
map, even campaigns without a returned metric row. Map commitment must equal the
SelectedPlanCaptureV1 map when composing with selected facts.

SelectedTrafficPinV1(Frozen): source_fence, aggregate: AggregateDependencyV1,
range_request_id: Id, range_receipt_digest: Digest, presence_header_digest: Digest,
presence_fact_digest: Digest, campaign_map_digest: Digest, producer_contract exact
literal above. Source/account/privacy and aggregate metadata must agree. Hash the
header with a new explicit domain, never reuse acquisition_digest as fact proof.

TrafficMetricSummaryV1(Frozen): value strict nonnegative int|None, present_days,
missing_days, unsupported_days, legacy_unknown_days (0..400), coverage Literal
observed_requested_days|partial|unavailable. Count sums <=400*MAX_INTEGER_COUNT;
spend sums <=400*MAX_MONEY_MICROS. No float/rounded money or decimal traffic counts.

SelectedTrafficWindowV1(Frozen): schema literal, pin:SelectedTrafficPinV1,
requested_window:ReportingWindow, campaign_id:Positive,native_campaign_id:NativeId,
starts_on/ends_on exact dates, requested_days1..400,returned_days0..400,
missing_calendar_days0..400, impressions/clicks/spend_micros typed summaries.
No conversion field. It is traffic evidence alongside—not replacing—SelectedPlanWindowV1.

project_raw_range_traffic(graph, *, campaign_id, requested_window)->SelectedTrafficWindowV1
validates the WHOLE immutable graph before slicing, with a prepared validated graph
helper permitted for repeated projections. Reuse selected_local_days for exact
closed local midnight conversion, plus full captured interval containment. All UTC
comparisons include fold/offset correctness. Missing rows produce missing days and
None when no cells observed; a partial observed sum remains visibly partial, never
an exact whole-period total. Only all requested days' explicit cells establish an
observed whole-window zero. No proration from61-day totals.

## Owned SQL Read Seam

load_raw_range_traffic(db, *, account:AccountRef, expected_source:SourceFence,
                      selected_pin:SelectedPlanPinV1)->RawRangeTrafficGraphV1 | KnownTrafficGap
is internal, caller-transaction-owned and original-session guarded before/after.
No network, commit, standalone client scope, or latest receipt/capture lookup.

Selected pin supplies exact aggregate completion/manifest/scope/date dependency.
Resolve receipt by that owned exact completion, with bounded max2 candidate IDs and
reject ambiguity; NOT newest timestamp. Then read_range_receipt(require_current=True),
read_presence(actual completion), full manifest(), all owned campaign rows and current
source/privacy. Repeat complete scalar/digest/cell equality, not only header counts.
The selected map digest must match the complete current owned map. Every retained
presence traffic value must equal the actual DailyMetric value; every SQL metric row
in the manifest must have exactly one sidecar fact. Full manifest validation includes
generic conversion fields only as integrity context; they never enter selected math.
Original-session authority and exact source grant binding remain existing outer rules.

Typed absence gaps: range_traffic_provenance_unavailable (no receipt or no raw profile),
unsupported_traffic_profile (different recognized source/profile),
campaign_outside_captured_mapping. A corrupt/foreign/ambiguous/mismatched current
receipt, sidecar, map or explicitly selected aggregate ABORTS rather than becoming
absence. No old receipt may be assigned this new profile on read.

## Bundle And Retained Binding Integration (Later Reviewed Slice)

Traffic and selected performance pair by exact account, local/native campaign,
requested UTC/local window, currency/timezone and IDENTICAL AggregateDependencyV1.
One raw traffic graph/account is retained once, never duplicate whole graphs perwindow.
Do not sum generic and selected conversions. Unknown attribution remains unknown.

SelectedRetainedAccountProofV1.legacy_reporting_digest already can wrap the existing
qualified local reporting-state commitment, which includes the entire presence
header/facts (retained_sources qualified=True). Verify the actual V4 reader uses that
path; do not assume the unqualified legacy digest includes it. Additionally retain
an optional traffic_pin in the V4 proof/evidence contract with explicit None omission
to preserve already frozen canonical documents. Final currentness recomputes receipt,
profile/presence/map and exact pin; historical validation checks retained immutable
commitments without reconstructing overwritten current SQL. Receipt/sidecar loss or
privacy erasure must invalidate currentness. Existing lifecycle tables cover storage;
add populated export/erasure tests for this concrete producer, not empty-table claims.
No runtime/capability registration in the initial producer/DTO/reader packages.

## Acceptance And Risk Boundaries

Actual MockHTTP→range publisher→sidecar→owned SQL reader→pure local-window projection:
September100clicks/$100, selected10 from a genuinely acquired61-day range produces
separate exact observations; August stays separately sliced, with no same-range total
reuse. Test explicit daily zeros vs missing row vs rejected missing raw metric cell,
partial days, daylight boundaries, ordinary legacy same-query completion without
profile, old range receipt without sidecar, unrelated same-account completion,
all profile/map/fact/source/privacy tampering, atomic rollback and after-I/O races.

No owner policy decision is necessary for this engineering scope. It does NOT prove
provider-delivery completeness, cost finality, causation, attribution alignment or
spending authority. Final Q01 diagnostic wording/composer integration still requires
the paired evidence consumer; this proposal alone does not close Q01.

Capacity qualification: the32MiB private graph cap can reject fewer than50,000
rows because presence envelopes add overhead; no truncation is allowed. Existing
owned selected-map capacity is10,000 campaigns, even though raw acquisition allows
more; exceeding the downstream contract remains explicitly unavailable. For Q01
complete-month fixtures, supply genuinely parsed explicit rows for every requested
day (zeros on other days where returned). If only the100click/$100 row is returned,
report its observed subtotal with partial coverage instead of a whole-month total.

## Review Clarifications

The publisher mapping exactly covers returned inventory; the reader map is the
complete current owned map, which may retain older campaigns. Do not conflate
these sets or delete old campaigns. Final receipt/header use post-publication
privacy with fresh source guards. Missing sidecar is a provenance gap only after
explicit selected aggregate/current privacy checks; corrupt present state aborts.
Historical traffic validation uses immutable receipt/header/facts and saved pin,
not mutable DailyMetric or current-map equality. Qualify rollback after sidecar
insert, raw-delete/privacy currentness, and later-import historical readability.
Only complete returned requested-day cells support exact whole-window totals;
otherwise label observed subtotals and partial coverage.
