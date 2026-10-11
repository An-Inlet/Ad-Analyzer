# Injected Google Aggregate Range Read — Interface Proposal

Baseeaf12e9; isolated branch codex/inlet-google-range-read in reused
/workspace/inlet-selected-catalog. Own only new app/google_connections/range_http.py,
tests/test_google_aggregate_range_http.py and package/interface docs. No resolver,
selected storage, descriptor registration, publisher, API or default factory edits.
Original-session resolver is under separate review; use its frozen catalog callables,
without copying its authority internals. Root owns aggregate SQL finalization.

## Exact Public Python Ports (Trusted Composition, Not Customer API)

    GoogleAggregateRangeHTTP(
        context_reader: Callable[[GoogleReportingCatalogRequestV1],
                                 GoogleReportingCatalogContext],
        revalidate: Callable[[GoogleReportingCatalogRequestV1], None],
        *, transport: httpx.BaseTransport, clock: Callable[[], datetime],
    )
    __call__(request: GoogleAggregateRangeRequestV1) -> GoogleAggregateRangeV1
    performance_contract -> ReportingDescriptor(
        'google_ads', 'google.v24.campaign-day.metrics-conversions.v1')

Mandatory injected transport; no environment fallback/network enabling. Concrete
property describes query mapping only; existing aggregate.descriptor exact-type
allowlist remains unchanged pending root's publisher integration. No selected-event
semantics or event choice is supplied by this aggregate reader.

## Frozen DTO Proposal

All DTOs strict frozen/extra-forbid/revalidate copied instances. UTC-aware strict
instants (no numeric/date/naive coercion), ISO dates via shared _date, native IDs via
strict NativeId; scalar SQL bounds from presence_contracts.

GoogleAggregateRangeRequestV1:
- schema_version literal inlet.google-aggregate-range-request.v1
- base: GoogleReportingCatalogRequestV1 (actual server-owned catalog_request result)
- requested_starts_on / requested_ends_on: inclusive date, 1..400 days, end before
  base.started_at's local account date; both dates within same exact IANA/currency
  account context, never inferred UTC days.
- digest(): domain-separated full request commitment includes base.digest() (which
  privately binds original actor/session) and exact dates/schema. Ordinary JSON
  excludes private original-session digest and cannot reconstruct private request.

GoogleAggregateCampaignV1:
- native_campaign_id strict 1..32 decimal digits
- resource_name strict customers/{10digits}/campaigns/{native_campaign_id}
- name strict1..255 safe observed text (display only), status ENABLED/PAUSED/REMOVED
- channel strict1..64 uppercase native enum token; preserve unknown enum literally,
  no inferred campaign-type support.

GoogleAggregateMetricV1:
- native_campaign_id + exact resource_name, metric_date
- impressions/clicks strict nonnegative Integer<=2^31−1
- cost_micros and conversion_value_micros strict nonnegative bigint<=2^63−1
- conversions exact nonnegative Decimal Numeric(18,6), canonical decimal text JSON;
  shared CountCell validation enforces precision/range; never float or rounding.
All five queried metrics required from original raw row. Missing/null/malformed fields
reject the entire read, NOT convert to zero. Omitted campaign/day rows stay omitted.
Campaign/day aggregate values remain generic metrics.conversions, not selected counts.

GoogleAggregateRangeV1:
- schema_version literal inlet.google-aggregate-range.v1
- request (private-capable nested request), request_digest
- completed_at, expires_at strict aware UTC; base.started_at<=completed_at<expires_at;
  adapter expiry<=min(base.started_at+60s, acquisition_start+60s, context.expires_at).
- pagination_complete strict literal true; page_count strict1..100 including account
  metadata query plus every campaign/metric page, not per-phase budgets.
- campaigns tuple<=50000, metrics tuple<=50000; combined<=50000
- entire canonical result<=32MiB; whole-result digest covers exact request digest,
  dates, all observations, completion and pagination. Canonical order is explicit
  native campaign ID then metric date; reject duplicate campaign IDs/resources or
  campaign/day keys even if equal. Every metric must join exactly one actual returned
  inventory campaign by both native ID/resource and exact same advertiser.
- Completed pagination does not mean every calendar day returned, historical
  conversion maturity, provider-atomic snapshot, selected identity or zero filling.

## HTTP Collection

Fixed https://googleads.googleapis.com/v24/customers/{owned ten-digit ID}/googleAds:search;
POST read queries only, identity encoding, no redirects or inherited proxies.
Required nonempty access/developer tokens; login manager optional private header.
Context resolver receives base request ONLY, and its returned digest must equal
base.digest(); result remains separately bound to full requested range.

1. Account metadata query selects customer.id/resource_name/currency_code/time_zone.
   Require exact one nonpaginated matching advertiser/currency/timezone observation.
2. Complete campaign inventory query selects campaign.id/resource_name/name/status/
   advertising_channel_type. Validate ownership/resource identity before accepting.
3. Complete aggregate query selects campaign.id/resource_name, segments.date,
   metrics.impressions/clicks/cost_micros/conversions/conversions_value FROM campaign
   WHERE segments.date BETWEEN exact request dates. No action segment/filter, no
   ad-group attribution or guessed campaign names.

Parse original bytes via exact_json, preserving duplicate-key rejection and decimal
lexemes. costMicros is already micros: parse an exact integer directly; DO NOT apply
money_cell's currency-unit multiplication. conversionsValue uses money_cell exact
currency-unit→micros conversion. Missing required keys must reject before existing
MetricRow defaults or any normalization; never call legacy GoogleHTTPRead.page.
Account/current source metadata mismatch rejects; no relabeling units or dates.

Per-phase pagination starts empty, opaque cursor<=3000; cycle/repeated cursor reject,
even after intermediate token. Cursor namespaces may overlap between independent
queries and are tracked per phase. Total pages100/combinedrows50000/total response
bytes32MiB; no truncation. Empty successful metric response valid with empty rows,
not observed zero. Empty inventory+nonempty metrics rejects. Sparse inventory metrics
retain omissions honestly.

Timeouts connect5s/read12s; 60s monotonic deadline starts before initial revalidation
and context resolution and is also bounded by base.started_at+60s and contextexpiry.
Fresh clock/authorization checks before/after each blocking read, after callback
returns, after parsing/result construction and before return; check every body chunk.
Revalidator owns scope/session checks, result cannot extend original operation.
Fixed safe unavailable exception, private HTTP flag restored; no raw error, token,
resource identifiers or provider response logs. No automatic retry/credential cache.

## Evidence And Remaining Scope

MockTransport cases: exact61day August1–September30 New_York request; paginated
inventory+metrics;100clicks/10aggregate/$100 exact arithmetic, selected meaning absent;
explicit zero versus missing rejection; sparse/no rows; duplicate JSON/keys/resources,
foreign account/resource, dangling metrics, swapped currency/timezone, bad dates,
fractional/overflow/precision, repeated cursor/total bounds, expired contexts/callback
waits/trickling body/finalization, copied DTOs and private serialization.
No SQL or live tests for this pure package. Whole Ruff/mypy and focused pytest,
logs under /workspace/inlet-evidence/20261011/google-aggregate-range/.

No provider query capability/live qualification is asserted from fixtures. Lack of
explicit metric keys in actual provider zero rows remains a truthful unavailable
profile limitation. Root's later registration/finalizer must verify actual owned
full range and atomically publish current aggregate; no completion fabricated here.
No Q01/Q02 selected-event acceptance merely from this aggregate result.

Preflight workspace1380MiB/scratch5847MiB/memory13434MiB; preserve reserves. No push,
remote/hosted/provider/network calls or existing frozen-checkout changes.
