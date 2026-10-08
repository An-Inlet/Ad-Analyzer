# Reporting Presence Contracts V1

Isolated `codex/inlet-reporting-presence-contracts` from `fd8a111`. Pure new module
`app/campaign_performance/presence_contracts.py`; no collector, legacy model/report,
SQL schema, manifest, source reader, policy, or API changes. Root must review these
exact types before dependent storage/producer work. Migration0089 is not in this lane.

## Concrete Fields And Limits

All types forbid extra fields, are frozen, and revalidate existing model instances.
`validate_presence(header, facts) -> None` and `presence_digest(facts) -> str` revalidate
unsafe copies, including nested cells and event/attribution metadata.

- `CountCellV1(presence,value)`: exact Decimal selected count. Python Decimal/integer
  and plain decimal strings accepted; bool/float/bytes/nonfinite/negative/excess
  fractional precision rejected. Existing **Numeric(18,6)** gives maximum
  `999999999999.999999`. Root corrected the freeze's original Numeric(20,6) typo
  after inspecting DailyMetric and MetaStagedMetric; the design document is corrected.
- `IntegerCountCellV1(presence,value)` is the explicit additional strict integer cell
  for impressions/clicks, maximum `2147483647`, matching existing SQL Integer.
- `MoneyCellV1(presence,value)`: strict integer micros, zero through signed-bigint max
  `9223372036854775807`. No float/string/Decimal coercion for integer cells.
- Presence is `present|missing|unsupported|legacy_unknown`. Only present requires a
  value, including0. Every other state requires null. Selected value and count are
  independent; a zero value never establishes count presence.
- `SelectedEventV1`: provenance, `native_event_id` (nullable, 1–128characters), optional
  label (1–160). Explicit selected requires ID; unavailable has neither. Generic may
  describe an aggregate but cannot qualify present selected-count/value facts.
- `AttributionBasisV1`: nullable strict click/view day counts0–400 (operational bound,
  not a provider default), report-time basis, provenance, and producer_contract≤200.
  Provider-default-unknown requires both windows null and basis unknown. Even observed
  metadata grants no causal, maturity, complete coverage or unique-customer claim.
- `ReportingSemanticsV1`: exact workspace/account/connection IDs, platform,
  `source_connection_ref` nonempty≤32 (Meta integer references serialized as strings
  as well as Google/TikTok UUIDs), generation/privacy, completion32hex and legacy
  manifest64hex; producer_contract/query_descriptor≤200; requested/actual inclusive
  date ranges, currency/time_zone, selected_event/attribution, strict pagination and
  closed-period booleans, literal returned_campaign_day_rows scope, aware completed_at,
  fact_count/fact_digest. Positive SQL IDs/generation≤2^31−1; privacy0..2^31−1.
- Requested dates at most400inclusive days; actual interval is inside requested.
  Dates accept date objects or exact ISO date strings, never epoch/datetime coercion.
  Closed-period true requires requested end before completion's local ZoneInfo date.
  Unknown time zones and naive/epoch completion instants reject. Pagination never
  implies missing campaign/day observations are zero.
- `ReportedMetricPresenceV1`: completion/workspace/account/campaign IDs, numeric
  native_campaign_id1–32characters, metric_date, independent impressions/clicks/spend/
  selected_conversions/selected_value_micros cells. Exact account-level scope and a
  one-to-one local/native campaign mapping hold across the entire fact set.

## Canonical Commitments And Bounds

Fact JSON is sorted-key compact UTF-8, no nonfinite numbers. Decimal JSON is a plain
string with fractional trailing zeros removed, no exponent notation; any zero becomes
`"0"`. Thus10,10.000000 and Decimal1E+1 commit identically. Missing and legacy_unknown
remain distinct. New SHA256 domain is bytes `inlet.metric-presence-set.v1` plus NUL,
then canonical JSON array of revalidated facts sorted by campaign_id/metric_date.
Duplicate campaign/day keys reject; order permutations do not alter the commitment.

Operational ceilings:100000facts (existing reporting maximum),4KiB per canonical fact,
128MiB canonical fact-array bytes (including separators),8KiB header. These bound this
contract only; they do not raise archive quotas or promise an archive can contain the
maximum graph. Explicit tests reduce byte thresholds to exact serialized length and
one byte below to exercise both sides without manufacturing giant provider documents.
The actual100001-row count rejection is also tested. Empty facts have a distinct
commitment and remain unknown evidence, not a zero observation.

The trusted publisher still must bind actual raw-field presence, exact source/import/
completion/manifest/campaign mappings and producer query semantics. These pure schemas
cannot turn client input, defaulted legacy cells or a complete-pagination boolean into
owned qualified evidence. No historical rows gain retroactive provenance.

## Executed Checks

- Initial focused suite:60passed0.19s; final independent-count/value case and static
  rerun results recorded below.
- Actual unchanged `campaign_performance.service.manifest` called through an isolated
  SQL-result seam and checked against fixed legacy domain/row bytes, including six-place
  conversion formatting. It remains distinct from the new digest. This is a pure golden
  check, not an import/DB/collector integration claim.
- Whole Ruff and configured mypy passed after test-only heterogeneous mapping
  annotations were corrected; initial mypy errors were confined to those annotations.
- No Full suite, live provider call, remote action or runtime/production qualification.

Next after exact type review: separately reviewed immutable0089 storage/privacy/archive
and concrete Meta staging producer; current V3 reader and absence-aware retained proof;
trusted planner evidence and useful zero investigation. Google/TikTok selected-event
producers and actual import→API Q01/Q02/Q09 remain separately required.

Final commands on frozen source:
`/workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_reporting_presence_contracts.py`:
**61 passed in0.17s**. `/workspace/inlet-venv/bin/ruff check .`: passed.
`/workspace/inlet-venv/bin/mypy`: **1069 source files passed**.
`git diff --check`: passed. No database or provider was used by this suite.
