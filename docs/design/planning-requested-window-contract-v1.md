# Requested Window Contract V1 — Frozen Pure Package

Rootc1cc08e. This freezes only pure DTO/projector work from the broader
[window proposal](planning-requested-window-projection.md). Database reader,
policy/adapter/composer and customer comparison UI remain separate later packages.
Do not change their production behavior or existing V1/V2/V3 bytes in this package.

Module: `app/campaign_performance/window_projection.py`.

```
project_requested_window(
    original: CampaignPerformanceV3, *, requested_window: ReportingWindow
) -> RequestedWindowPerformanceV1
```

Important reviewed refinement to the proposal: this pure projector validates the
original V3 document and its campaign subset; it does NOT accept/scan the entire
completion graph or claim to prove the original whole-graph commitment. The later
DB reader must use actual current owned legacy/V3 readers and one transaction-bound
PresenceReadContext to validate/index the full graph once. Never do full graph
validation/scanning per campaign/window. DTO construction conveys no ownership or
source authenticity; a caller can construct data and cannot thereby authorize it.
The unmodified original header/digest remain visible and retain their original scope.

Freeze DTO fields exactly as proposed: schema_version
`inlet.requested-window-campaign-performance.v1`, projection_version
`inlet.reporting-window-projection.v1`, original (unchangedV3),
original_document_digest (existing planning common fingerprint domain
`campaign-performance`), requested_window (existing half-openReportingWindow),
requested_starts_on/requested_ends_on (inclusive derived localdates), selected_facts
(exact sorted subset, <=400), selected_fact_digest (presence_digest of subset),
summary (newWindowCampaignSummaryV1), derivation
`local_projection_of_imported_campaign_days`, causal_attribution='unavailable',
spending_authorized=False. Strict frozen extra-forbid/revalidate-copies; no additional
implicit flags, persistent fields or changed defaults on old DTOs.

WindowCampaignSummaryV1 fields: requested_days, returned_days,
missing_calendar_days; impressions, clicks, spend_micros, selected_conversions,
selected_value_micros (reuse strictMetricSummaryV1 shape, count strings canonical);
selected_zero_for_requested_window. Recompute every field from exact selectedfacts,
never accept summary/zero flags as proof. Keep numeric integers exact and Decimal
arithmetic under explicit Context(prec=50), independent of caller traps/exponents.
Allmissing => null, not0. Missingcalendar and missingreturnedcells are separate.
An empty campaign subset is unavailable observations, never full-windowzero.

Window rules follow the proposal: 1–400 exact unambiguous source-local calendar days,
requested half-open instants exactly localmidnight with UTC roundtrip/fold checks,
containment within ORIGINAL queried dates, last day before originalcompletionlocalday.
No silent intersection, rounding, shiftingtimezones or elapsedseconds/86400 daycount.
Complete per-metric coverage additionally requires original closedperiodflag and
paginationcomplete, actualscope covers requestedsubset, everyrequestedday present,
and thatmetric present every day. Thus partialoriginalactualscope may fully cover an
interior requestedsubset; retain originalbounds. Selectedzero additionally needs
explicitselectedevent and total0. Unknown attribution remains unknown.

Raise new typed `WindowProjectionUnavailable(ValueError)` with a bounded reason in
`outside_imported_window`, `unaligned_local_days`, `requested_days_not_closed` for
known valid-source/request incompatibilities. Invalid/tamperedDTO, mixedidentity,
malformedfacts, bounds or summary mismatches remain ordinaryvalidation errors, never
benign known-data gaps. ReportingWindow already rejects invalid/nonpositive ranges;
do not hide those errors. Validation of a manually supplied wrapper must independently
recompute its subset/dates/digests/summary, rejecting forged known-gap transformations.

Enforce 2MiB UTF-8 serialized wrapper bound (includes duplicated original+selectedfacts)
with no truncation. Lateradapter owns unchanged32MiB collection bound. No fallbackto
legacyaggregate, implicit conversionselection, FX, rate/delta/causalcomparison,
recommendations, storage/I/O or authority in this pure package. Do not manufacture
any temporary ReportingSemanticsV1 with changed query/actual/request dates.

Qualification: pure full56day→7day exactoriginalbytes; positive100/10/USD100;
fullzero/missingselected/absentcalendar/allmissing/independentvalue; originalpartial
pagination/actualscope/openflag; DST23/25hour days countedbycalendar, ambiguous and
nonexistentmidnight/nonmidnight/outofbounds/openrequestedday; native/summary/subset/
digest/copytampering; capacityrefusal and hostileDecimalcontext. Preserve oldpublic
summary/report fixture outputs. No DB/API/import/comparisonproduct acceptance claim.

Ownerinitial_start: newmodule + newfocusedtests +ledger only. No edits to existing
contracts/summarizers unless root reviews an unavoidable purehelper seam first.
Newreader/policyintegration is not yet authorized by this frozen purepackage.
