# Reporting Presence V1 — First Implementation Boundary

Implements the additive contract portion of the reviewed metric-semantics gap
proposal. This package supplies typed facts and canonical validation only. It does
not alter legacy Completion columns/manifests/V1/V2 reports, collector behavior,
retained witnesses, planner policy or public response schemas. No migration in this
package;0089 remains reserved for subsequent reviewed storage integration.

Own module `app/campaign_performance/presence_contracts.py` and focused tests.
Use immutable extra-forbid Pydantic models with strict IDs/integers, finite bounded
exact Decimal counts, ISO dates/aware instants and deterministic canonical JSON.
Never use a float to represent counts or money. Model/API names below are frozen;
field details must implement these specified concepts and be documented with code.
No dependent lane starts until root reviews the exact committed models.

`CountCellV1` and `MoneyCellV1`: presence `present|missing|unsupported|legacy_unknown`,
value exact nullable Decimal count / integer micros. Present requires a nonnegative
bounded value including0; every other state requires null. Boolean/float/nonfinite/
excess precision are rejected. Counts support at most6fractional places and values
within existing SQL Numeric(18,6); money uses existing nonnegative bigint-compatible
limit. Presence of selected value is independent of selected count.

`SelectedEventV1`: identity provenance `explicit_selected|generic|unavailable`,
bounded native event ID and optional human label. Explicit selection requires native
ID; unavailable has neither. A generic label/ID cannot qualify selected conversions.
`AttributionBasisV1`: click/view windows nullable nonnegative integers, report-time
basis `interaction|conversion|unknown`, effective provenance
`observed_response|verified_request_contract|provider_default_unknown`, bounded
producer contract/version descriptor. Unknown defaults carry no claimed windows or
known time basis. No causal/maturity/unique-customer qualification is implied.

`ReportingSemanticsV1`: schema `inlet.reporting-semantics.v1`; workspace/account/
connection IDs, platform, source connection reference/generation/privacyrevision,
completion ID, legacy manifestdigest, producer/querydescriptor, requested and actual
inclusive dates, currency/timezone, selected event, attribution, paginationcomplete,
returned-rows scope, closed-requested-period flag, completed_at, fact count/digest.
Dates are bounded/ordered, actual within request, and closed flag requires end before
completion's local calendar date. Pagination completeness is never all-day/all-entity
coverage. Use exact scope `returned_campaign_day_rows`; absence of a row is unknown.

`ReportedMetricPresenceV1`: schema `inlet.metric-presence.v1`; completion/workspace/
account/campaign IDs, native campaignID and metric date; independent impressions,
clicks, spend_micros, selected_conversions and selected_value_micros cells. Integer
impressions/clicks, decimal selectedcount. It is owned evidence only after trusted
publisher binding, not because a client can construct this schema.

`validate_presence(header, facts)` validates exact complete bindings, native/local
campaign identity consistency, unique campaign/day keys, date bounds, fact count
and canonical digest. Generic/unavailable events cannot have present selected
count/value cells. Empty facts preserve unknown evidence, never zero evidence.
`presence_digest(facts)` sorts deterministically bycampaign/date, rejects duplicates,
and uses a new versioned digestdomain without changing legacy manifests. Bound facts
to existing100000row maximum; canonical serialized fact size and aggregatebytes are
bounded explicitly (choose limits that fit the above fields and document them).
No raw provider responses, credential material or customer-level conversion events.

Tests: present0 versus missing/legacy, positive100click/10count/$100 cells, missing
value with presentcount, generic selectedrejection, precise decimals, invalidcells,
duplicate/foreign/mismatchedcampaign/native/date/scoperef, canonical permutations,
emptyfacts, count/digest/bytebounds, and unchanged legacy manifest golden behavior.
This is contract acceptance only; actual import→API Q01/Q02/Q09 remains pending.

Next dependencies: reviewed exact models→0089 immutable owned storage/privacy/archive
and Meta staging producer→V3 current report/trusted sidecar witness→planner evidence
and useful zero investigation. Google explicit selected-event and TikTok selected
producers require separately verified read profiles; legacy aggregate values remain
unqualified. No defaulted historical row gains provenance retroactively.
