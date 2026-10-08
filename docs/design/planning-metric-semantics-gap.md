# Planning Metric Semantics — Q01, Q02 And Q09 Investigation

Read-only investigation at root `dcdce0d`. Proposal only: no implementation, migration
reservation, provider request, external documentation lookup or test run. The frozen
quality cases are unchanged. In particular, an unavailable TikTok metric is an honest
gap, but does not satisfy Q09's supplied purchase-event/different-window fixture.

## Finding

Current imports preserve useful owned campaign totals and current-source integrity, but
lose the event-presence and effective attribution information needed for these cases.
A scalar zero cannot recover whether a selected event was explicitly reported as zero.
A completed paginated import does not prove every day/entity/event was reported.

The smallest safe next package is additive, versioned reporting provenance captured
BEFORE normalization, published atomically with the existing completion, and separately
hashed. Keep existing DailyMetric values, V1/V2 documents and manifest bytes intact.
Do not relax the planning port's positive-only legacy qualification to admit zeros:
that would promote existing defaulted zeros into evidence.

## Concrete Existing Lineage

| Platform / layer | Local code and current behavior | Information absent downstream |
| --- | --- | --- |
| Google HTTP | `google_connections/http.py:GoogleHTTPRead.page` queries campaign-day `metrics.conversions` and `metrics.conversions_value`, without a selected action dimension/filter. `m.get("conversions", 0)` and equivalent traffic/spend/value defaults erase field absence before MetricRow construction. | Exact selected event/action identity; per-field presence; explicit effective attribution/time basis. Aggregate positive conversions do not prove purchases. |
| Google import | `google_connections/contracts.py:MetricRow` requires normalized numeric values. `service.py` stages page JSON, atomically replaces the finished window's DailyMetric rows, then calls `campaign_performance.aggregate.publish`. | Staging and final rows cannot distinguish defaulted versus present zero. No selected-event read/configuration contract exists locally. |
| Meta HTTP / normalize | `meta/client.py:page` requests campaign-day insights including actions/action_values with provider defaults. `normalize.py:action_value` returns Decimal(0) for None or no matching selected action; duplicate matches reject. `metric_values` uses the connection's chosen action type. | Missing actions field, empty array, absent selected member and explicit selected member value=0 collapse together. Count and value presence are independent, but both are discarded. No effective attribution windows or action reporting-time declaration is requested/captured. |
| Meta staging / publish | `meta/models.py:MetaStagedMetric` stores only numeric fields. `sync.py:_publish` replaces campaign-day rows only after terminal staging, then `service.publish_meta` pins source generation, selected event, requested interval and manifest. | Terminal page completion and source coverage interval are available; per-field/event presence and effective reporting semantics are not. |
| TikTok HTTP / normalize | `tiktok/wire.py` requests BASIC campaign/adgroup/ad daily reports with impressions/clicks/spend/generic conversion. It indexes `values["conversion"]` (missing fails parsing), sets conversion_value_micros=0, and validates bounded page_info. | A present generic count is not a selected purchase count; value is a placeholder. No selected purchase-event or attribution-window producer is established in this repository. |
| TikTok import | `sources/contracts.py:SourceMetric` and `sources/advertising.py` stage bounded pages, reject repeated cursors, map native hierarchy and replace metrics at terminal completion. Concrete `TikTokHTTPRead` descriptor permits aggregate completion publication. | Generic metric field presence is implicitly required at parse, but not recorded as reusable typed provenance. Unsupported goal/value semantics must remain unavailable. |
| Shared storage | `ads/models.py:DailyMetric` has non-null numeric defaults (conversions Decimal(0), value 0). `campaign_performance/models.py:PerformanceCompletion` stores source, generation, privacy, interval, query version, event label, basis, row count and manifest. CurrentPerformance names exactly one current completion per account. | No per-cell presence, pagination/coverage descriptor, effective attribution or qualified selected Google/TikTok event. No history of report bodies behind old completion metadata. |
| Manifest | `campaign_performance/service.py:manifest` hashes sorted campaign/day numeric rows under `inlet.campaign-performance-manifest.v1`; at most 100,000 campaign rows. | It validates stored totals, not omitted raw fields or selected-event meaning. New metadata must not be inserted into this old hash domain. |

`campaign_performance.aggregate.stage_contract` correctly refuses to upgrade legacy or
unqualified staged pages mid-import. Only concrete GoogleHTTPRead/TikTokHTTPRead carry
accepted query descriptors; a duck-typed transport declaration is not qualification.
Preserve both safeguards when introducing richer producers.

## Current Reporting And Planning Guards

* `campaign_performance.service.read_current` validates Meta ownership, connection,
  source generation/event/privacy/currency/time zone, current completion, coverage or
  existing fixed-window lineage, then recomputes the actual manifest. No campaign rows
  gives null totals; rows with a selected event may still contain normalized defaulted
  zeros. `CampaignPerformanceV1.reporting_basis` is literally
  `provider_defaults_unspecified`.
* `campaign_performance.aggregate.read` does equivalent owned/current manifest checks
  for Google/TikTok. V2 labels both `provider_aggregate_unspecified`. Google exposes the
  generic conversions/count/value; TikTok exposes reported_generic_conversions only,
  leaving goal conversion/value/CPA/ROAS null. These are correct limitations to preserve.
* `analysis/platform_evidence.py:has_platform_conversion_metrics` returns True for
  Google unconditionally; Meta uses selected event + covered interval. These legacy
  availability booleans are NOT presence or qualification evidence for the new planner.
* `planning_documents/evidence_adapter.py:collect` joins exact native campaign IDs,
  matches the requested primary window, and accepts only positive V1 selected-event
  counts as `reported_only`. Zero and all Google/TikTok V2 counts stay unqualified.
  Report coverage remains partial/reported_rows_only; attribution unavailable.
  `PerformanceEvidence.exact` in ports.py enforces the same positive V1 restriction.
* `composer.py:reported_summary` prints positive provider-reported counts, never infers
  a no-conversions finding from zero/missing, and asks to verify the selected event and
  basis when qualification is absent. It does not currently distinguish a proven zero
  or emit a campaign-specific tracking/landing-page investigation from such a zero.
* `evidence_local.recheck_local_sources` rereads exact owned current reports at commit.
  `retained_sources._reporting` captures actual completion fields, manifest and bounded
  native/local campaign mapping, including current-report absence. These checks must
  also cover new semantics state; a copied hash alone is insufficient.
* Only one current reporting window is available. Requested comparison_window currently
  adds `only_current_reporting_window`. This proposal does not secretly turn old
  completion metadata into replayable period bodies or solve comparative history.

B01's 100-click/10-conversion/$100 analyzer regression remains valid and must keep passing.
It does not establish Q01's selected-event semantics through the customer planning API.
Likewise, protecting the composer from a false zero does not complete Q02's useful
response to a genuinely observed zero.

## Proposed Shared Reporting Types

Freeze exact schemas before changing collectors. Suggested names describe a new version,
not optional defaulted fields added to existing hashed documents:

* `ReportingSemanticsV1`: owned account/connection/source-generation/privacy tuple;
  legacy completion ID and legacy manifest digest; concrete producer/query descriptor
  version; requested reporting interval and time zone; actual queried interval;
  selected event identity and its provenance (`explicit_selected`, `generic`, or
  `unavailable`); bounded native event identifier/label when known. A label such as
  “purchase” alone must not stand in for a Google conversion-action identity.
* Explicit attribution descriptor: effective click/view windows (nullable), report-time
  basis (interaction/conversion/unknown), effective-setting provenance
  (`observed_response`, `verified_request_contract`, `provider_default_unknown`), and
  applicable platform configuration revision/digest. Requested settings are not treated
  as applied settings unless the concrete pinned adapter contract proves that behavior.
  Maturity and causal attribution remain unqualified/unavailable.
* Coverage descriptor separates `pagination_complete`, requested versus returned entity
  scope, closed versus open requested dates, and present/missing field/day counts.
  `pagination_complete=True` is not `every campaign/day/event observed=True`.
* `ReportedMetricPresenceV1` per exact campaign/day: local AND native campaign identity;
  presence states for impressions, clicks, spend, selected conversion count and selected
  value (`present`, `missing`, `unsupported`, `legacy_unknown`); nullable exact Decimal
  count and nullable integer micros value; event identity/query descriptor binding.
  Required invariant: present has a value including zero; missing/unsupported/unknown
  has null. Value presence is independent of count presence. Generic TikTok counts can
  remain separately labeled generic values, never copied into selected conversions.
* `CampaignPerformanceV3`: explicit new document wrapping/binding the verified existing
  owned report plus the semantics header/fact digest and derived presence-aware totals.
  Do not mutate V1/V2 schemas or claim their defaulted zeros gained provenance. A V3
  selected zero requires actual present zero cells and an explicit scope over which
  that statement is made. If some cells/dates are missing, retain partial coverage and
  do not claim zero for the entire requested window. No returned campaign rows is null.

The planner's new PerformanceEvidence variant must carry V3 with those bindings. Legacy
V1 positive-only behavior stays intact. V3 may qualify a selected count of zero as
reported evidence, without qualifying causal attribution, revenue or platform
comparability. Displaying a numeric observed partial sum must state that scope;
report-wide CPA/ROAS remains unavailable when its required denominator/numerator cells
are missing or the semantic basis is unqualified.

Google needs an explicit selected-event read specification; its existing aggregate
query cannot supply one. The specification must come from an owned, confirmed measurement
choice or an explicitly versioned server read policy, not a guessed event based on the
Shopify sales goal. Meta's existing connection selection can supply its event identity.
TikTok requires a new concrete supported selected-event producer, not relabeling its
generic conversion counter. Local code does not establish the exact Google/TikTok
selected-event query or effective-window request semantics; those details require a
separate approved protocol/documentation verification step before a producer is frozen.
No external claims or unverified GAQL/API parameter names are proposed here.

## Smallest Additive Persistence Package

Recommend the next unreserved migration after 0088; root assigns its actual number.
Use TWO owned tables, avoiding new default columns on PerformanceCompletion (retained
proof currently enumerates all its columns, so even a default can silently change old
proof bodies):

1. `campaign_reporting_semantics`: one immutable versioned header per completion;
   composite FK `(completion_id, account_id, workspace_id)` to the existing completion
   scope, and owned account/connection FK. Store bounded canonical typed descriptor,
   legacy manifest pin, semantics schema/query version, facts count and separate
   semantics/facts digest. No raw response, credential, cookie or personal event data.
2. `campaign_reporting_metric_presence`: bounded campaign/day fact rows belonging to
   that same exact header/completion/workspace/account; exact scoped campaign FK and
   native campaign ID, presence states and selected metric values. Use explicit unique
   campaign/day keys and a deterministic independent manifest domain. Enforce no
   cross-account campaign join. If an existing campaign tuple is not FK-unique, add
   the required unique parent constraint rather than a weak unscoped FK.

Reuse existing bounded staging channels with NEW versioned staged envelopes: Google's
and source transport's staged JSON can carry a parallel typed provenance envelope;
MetaStagedMetric needs additive nullable provenance JSON (or an equivalently scoped
staging sidecar if JSON cannot preserve its bounded cleanup invariants). This is an
explicit additional staging change in the same migration, not reconstructing evidence
from final numeric rows. Legacy staged pages without provenance may still finish their
existing import but cannot publish a qualified semantics header. Do not adopt metadata
mid-window. Validate the entire selected specification/descriptor consistently across
pages; changed event/window/source or duplicate/conflicting facts aborts qualification.

At terminal import, publish existing DailyMetric + existing completion/manifest + new
header/facts + current pointer atomically under existing workspace/source locks. Google
selected-action counts may come from a separate qualified query: never overwrite its
legacy aggregate count or repeat campaign spend once per action segment. Pin both query
lineages and the same owned window; do not join by campaign name. Unsupported provenance
leaves existing import/reporting usable and explicit planning gaps, with no synthetic
qualified header. All rows/pages/bytes remain bounded; overflow cannot claim completion.

Keep fact bodies CURRENT-ONLY on replacement, matching today's reporting storage intent;
old metadata must not become a new report replay mechanism. Preserve already persisted
plan documents as historical summaries. Include the new tables and staging field in
workspace/account privacy erasure, closure, bounded archive/export, import cancellation,
reconnect and source-generation cleanup. Header/fact availability is not authority.
Exact retention/delete predicates and column-level constraints need storage review.

## Private Read And Final-Proof Interface To Freeze

Proposed separation:

```python
publish_reporting_semantics(db, *, completed_import, validated_staged_provenance) -> None
read_planning_current(db, *, workspace_id, actor, account_id, campaign_id,
                      expected_completion_id, authorize) -> LegacyReport | CampaignPerformanceV3
```

Both are DB-only with caller-owned transactions. Publisher accepts only concrete
validated producer output bound to terminal import, never a browser “complete” flag.
Reader first performs existing read_current ownership/source/current-pointer/manifest
validation, then recomputes exact new header/fact integrity and coverage. Missing legacy
metadata returns explicitly unqualified legacy evidence, not zero; corrupt/present-but-
invalid new metadata aborts, never silently downgrades into a harmless gap.

Generation final recheck must compare the exact V3 document/new digest again after all
IO. Add an absence-aware, account-scoped local semantics witness for NEW plan policy
versions, separate from existing `local_reporting_v1`, covering the current header/fact
set or its proven absence. Recompute actual rows on retained-version read. This catches
same-pointer metadata corruption, missing→available provenance, replacement, or event/
window correction even when the old numeric manifest is unchanged. Do not rewrite old
witness hashes or manufacture witnesses for legacy plans; historical content stays
readable, while missing proof prevents a new “currently qualified” claim. Preserve
fresh session/role/billing/privacy and expiry checks, with no identity/provider IO under
DB locks and no execution anchors.

## Quality Behavior And Actual API Acceptance

Qualification must go through each concrete mocked provider transport → actual staged
import → terminal publication → authenticated customer catalog/input/generate API.
Constructing a ready PerformanceEvidenceV3 in a test is useful pure coverage but cannot
stand in for these source-path cases. Run SQLite and PostgreSQL.

* **Q01 unchanged:** Google campaign and observed ad group are locatable by name/account/
  native ID; exact event and reporting basis are produced by the new qualified adapter.
  Campaign totals are 100 clicks, 10 selected conversions, 100,000,000 spend micros.
  Generated advice cites the event, dates and limits; no no-conversions finding, forced
  budget change, or inference that the ad group shares campaign-level performance.
* **Q02 unchanged:** same actual request/row, explicit selected value 0 versus omitted
  conversion field, omitted action array/member, missing campaign/day and unsupported
  metric. Only explicit zero is displayed as zero for its qualified reported scope.
  For positive spend plus proven selected zero, generate a specific campaign/event/date
  tracking/landing-page investigation; missing evidence instead requests the exact
  absent report/setting. Both retain honest unknown sales effect. Keep B01 positive and
  valid true-zero analyzer tests, and reject duplicate conflicting selected-event rows.
* **Q09 unchanged:** actual Google purchase, Meta lead and TikTok purchase with a different
  effective attribution window; one incomplete reporting interval. Preserve all three
  event/window/coverage tuples visibly in API output. No cross-platform CPA ranking,
  numeric transfer recommendation or summed unique customers/Shopify attributed sales.
  Name concrete alignment steps (select the same business event, verify effective
  reporting time/windows, close/import the missing dates) while allowing a useful
  qualitative plan. The full case remains blocked until TikTok's selected-event producer
  is real; do not weaken the fixture to generic/unavailable and call it complete.
* Distinguish click/view windows, report-time bases, currency/time zone and partial field
  coverage even where event labels happen to match. Matching those fields is necessary,
  not sufficient, for causal or cross-platform deduplicated comparison.
* Import adverse cases: resumed legacy pages, mixed descriptors, incomplete pagination,
  wrong account/native campaign, missing field with positive traffic, explicit Decimal
  zero, negative/nonfinite values, duplicate pages and source reconnect mid-import.
  Failure rolls back the new qualification and never upgrades the old metric manifest.
* Final/retained races: same numeric manifest but changed event/presence/window header,
  corrected zero→positive, missing semantics→available, same-pointer fact corruption,
  source generation/privacy change and expired catalog. Current advice becomes stale
  or generation aborts; original plan/decision remains historical without carryover.
* Golden tests: old native inventory and V1/V2 performance schema/manifest bytes remain
  byte-identical. Existing unqualified imports still complete. Legacy availability
  booleans cannot be used to populate new presence states. No new ad-platform writes.

This proposal neither qualifies Q01/Q02/Q09 today nor reduces their requirements. It
identifies the producer and provenance work needed before useful source-grounded advice
can replace the current conservative descriptive output.
