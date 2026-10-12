# Bounded Social Selected-Event Semantics — Design V1

Status: design for the next offline package; no producer implementation or activation.
Based on the parent's independent official-source research handoff of2026-10-12,
retained at `social-semantics-research/parent-official-source-handoff.json` in the
external evidence tree. This executor's additional read attempt still received
Meta429/fetch errors and an inaccessible TikTok gateway URL. The supplied research
is the evidence source; it is not independent local retrieval or live qualification.

## Source Precedence

- [Meta2025 out-of-cycle changelog](https://developers.facebook.com/documentation/ads-commerce/marketing-api/out-of-cycle-changes/occ-2025): from2025-06-10,
  `use_unified_attribution_setting` and `action_report_time` are disregarded across
  versions; reporting follows Ads Manager settings. From2026-01-12, `7d_view` and
  `28d_view` return no data. This overrides conflicting older reference/SDK enums.
- [Meta AdsActionStats](https://developers.facebook.com/docs/marketing-api/reference/ads-action-stats),
  [account Insights](https://developers.facebook.com/documentation/ads-commerce/marketing-api/reference/ad-account/insights),
  and [Insights overview](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights)
  establish action types, action/count-value lists, scoped report fields and reads.
- TikTokv1.3 official gateway documents:
  [metrics](https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443967255553&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language),
  [dimensions](https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443956638721&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language),
  [synchronous reporting](https://business-api.tiktok.com/gateway/docs/index?doc_id=1738864778664961&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language).
  Do not substitute v2.0 portal syntax. The
  [conversion discrepancy guide](https://ads.tiktok.com/resources/help/article/conversion-discrepancies)
  describes ordinary impression-time reporting; this alone does not prove every
  account's attribution windows or counting settings.

## First Bounded Candidate Mappings

Only explicit provider event identifiers may be confirmed. Freeform customer labels
are display text, never a mapping rule. A documented field is a candidate contract,
not proof of availability for every report combination or live advertiser.

| Platform/API | Exact selected identity | Count source | Value source | First package |
| --- | --- | --- | --- | --- |
| Meta v26.0 | `offsite_conversion.fb_pixel_purchase` | `actions` item with exact matching `action_type` | Same type in `action_values` | Website purchase count; optional value only under matching context/currency |
| Meta v26.0 | `offsite_conversion.fb_pixel_lead` | Exact type in `actions` | No assumed monetary value | Lead count, kept incomparable with purchase count |
| TikTok v1.3 | `complete_payment` | `complete_payment` | `total_complete_payment_rate` | Website payment/purchase count; value conversion held pending documented units/scaling |

Meta v26.0 is the repository configured target, not a version-qualified report
combination established by the supplied excerpts. Treat these as proposed pinned
profiles until exact field/grain/version support is source-confirmed.

TikTok's supplied value-key mapping does not establish wire units, decimal
representation or currency scaling. Retain its key as documented, but do not
produce MoneyCell/micros or revenue/ROAS from it until those facts are documented.
Pair membership and a `_rate` suffix establish neither unit nor scaling.

Initial scope is advertiser-owned campaign/day reporting, not a specific pixel or
unique customer count. The query owns advertiser scope; event ownership must not
claim a pixel/custom-conversion owner that the response cannot establish. No mapping
from arbitrary Inlet names, generic `conversion`, or campaign optimization goals.

Documented but deferred candidates are Meta `offsite_conversion.custom.<id>`, generic
`offsite_conversion.fb_pixel_custom`, app `app_custom_event.fb_mobile_purchase`, and
grouped `omni_purchase`; TikTok `total_purchase`/`total_purchase_value`,
`custom_app_events`/`custom_app_events_value`, and
`custom_page_events`/`custom_page_events_value`. They are not interchangeable with
the initial website selections. TikTok `purchase` is unique app purchase count,
not `total_purchase`; `complete_payment_roas` is a ratio, never count/value.

Meta `action_target_id` is destination identity, not custom-conversion identity.
TikTok `custom_event_type` may combine one ID dimension and `stat_time_day`, while
`event_source_id`'s documented combinations exclude `campaign_id`. A campaign/custom
row therefore cannot establish pixel identity. Custom-event support waits for a
complete explicit identity contract; no cross-grain join is inferred.

## Requested Context Versus Effective Evidence

The next shared interface must keep three distinct things:

1. **Confirmed selection/profile:** platform/API, exact provider event/count/value
   keys, advertiser owner, campaign/day grain, count versus unique-count meaning,
   requested window/date basis and dimensions/filtering, profile version/digest.
2. **Requested settings:** exact allowlisted attribution-window options and
   report-time flags actually sent (including explicit absence). Retained request
   evidence never becomes proof of effective behavior. Do not send ignored Meta
   flags as an attempt to force reporting time; refuse retired view windows rather
   than interpreting the no-data response as zero.
3. **Effective observations:** separately retained response/account/ad-group evidence
   for effective windows, reporting time and counting mode, or explicit unknowns
   with reasons. An `attribution_setting` field is not enough unless its scope,
   meaning and consistency with the selected row are qualified. A campaign aggregate
   across differing ad-group settings cannot be assigned one invented setting.

Initial effective attribution remains fully unknown in `AttributionBasisV1` unless
actual evidence qualifies it. Never set `verified_request_contract` simply because
Meta received a report-time flag. General documentation about ordinary TikTok
impression-time reporting is retained as a contract note, not invented per-account
windows. Unknown does not become zero or imply comparability.

The current immutable selected-capture request has only one `attribution` object;
its query-profile digest alone is not a readable record of requested settings.
Do not overload that object or modify persisted v1 structures in place. The next
package should first define/test a standalone strict profile and request/effective
projection contract. Persistence/API/history integration then needs an explicit
version/reader-floor decision under
[the existing version boundary](plan-provenance-version-boundary-v1.md), preserving
all legacy bytes/digests. No new table or migration is assumed by this design.
Dependent collectors wait for that concrete integration contract to be reviewed.

## Exact Parsing And Completion Rules

- Meta count and monetary value join by exact `action_type` plus identical requested
  and observed window, breakdown and grain context; never by array position or an
  `omni_purchase` substitute. Reject duplicate ambiguous matching items. Keep explicit
  window cells and counting mode distinct; overlapping windows cannot be summed.
- TikTok request is `GET /open_api/v1.3/report/integrated/get/`, advertiser-scoped,
  with coherent `report_type`, `data_level`, campaign ID/day dimensions and bounded
  account-timezone dates. Retain response dimensions/metrics, request ID and complete
  pagination evidence. `total_metrics` supplies no event or target identity.
- Both providers require exact owned account/connection generation, campaign identity,
  requested closed dates, timezone and currency evidence. Preserve original request
  and response acquisition times; recheck original session/ownership/source after IO.
- A valid explicit numeric zero is present0. Missing event item, field, campaign/day
  row or unavailable metric stays missing/unsupported/unknown as applicable, even
  when pagination is complete. No absent-as-zero contract is established here.
  Invalid/negative/nonfinite/overprecision values are refused, not coerced.
- Exhaustion/count/pagination inconsistencies, foreign scope, duplicate rows or dates
  outside the request refuse publication; no partial retained selected capture.
  A structurally complete report with missing metric cells may truthfully retain
  missing cells without claiming complete selected measurement coverage.
- Deleted-object omissions need the matching documented status filter, including
  `STATUS_ALL` where supported. Do not assume a similarly named filter works at every
  data level. Unverified combinations stay unavailable. No silent generic fallback.
- Count can be present while value is missing; never infer value from count or ROAS.
  Currency conversion, cross-platform deduplication, numeric CPA ranking across
  incompatible bases and causal-lift claims remain outside this package.

## Next Acceptance Package And Boundaries

Implement only a finite set of pure, versioned social profiles and request/effective
contracts first: proposed `meta.website-purchase.campaign-day.v1`,
`meta.website-lead.campaign-day.v1`, and `tiktok.website-payment.campaign-day.v1`.
Each must explicitly retain count meaning, value-key/unit/availability states and
unverified combination status; profile presence never grants runtime capability.
No generic reporting framework or open-ended registry is needed. Work
with fixtures sourced from these exact documented names. Focused cases must cover
exact purchase/lead selection, wrong grouped/custom/app substitutes, exact count/value
join under shuffled arrays, duplicates, missing versus explicit0, retired Meta flags/
windows, unknown effective settings despite requests, TikTok total/unique differences,
no pixel inference, and malformed/incomplete/out-of-scope reports only for a narrowly specified
selected report shape after its exact contract is fixed. These tests qualify
parser/contract behavior, not API availability or live reporting.

Before durable producers: freeze precise interfaces for acquisition output, canonical
serialization and lossless historical/request provenance; specify the compatibility
reader floor. Then bounded real customer selection/acquisition/capture/history tests
can join genuine MockHTTP responses. No provider credential calls or live tests are
authorized. Default V3/private V4–V6 gates, planning-only authority and approved spend
ceiling stay unchanged. No owner decision is needed to keep unsupported mappings
unavailable; human product/live/retention/sharing gates remain separate.

Independent design review requested these refinements: v26.0 is a configured target,
not proof of each report combination; TikTok value conversion awaits exact units/
scaling. Both are incorporated. This design is not a passing implementation.
