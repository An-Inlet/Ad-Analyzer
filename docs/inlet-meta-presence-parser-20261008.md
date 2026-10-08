# Pure Meta Reporting Presence Parser

Base `66019e5`, isolated branch `codex/inlet-meta-presence-parser`. Owns only
`app/meta/presence.py`, `tests/test_meta_presence.py`, and this ledger. Implements
the parser seam in `docs/design/planning-reporting-presence-storage-v1.md` using
reviewed pure presence contracts. No collector, staging, SQL, legacy normalizer,
manifest, reader, or public API changes.

`parse_meta_presence` validates the native campaign ID, exact advertiser, currency
and ISO day scope, then calls the unchanged `metric_values` numeric validator.
Original parsed action-list membership determines presence independently for count
and value. An explicit selected entry of zero is present; an absent/null/empty list
or missing selected entry is missing. No selected event produces unsupported cells.
Selected value is supported only for existing `PURCHASE_ACTIONS`; lead counts are
supported while lead monetary values remain unsupported. Unsupported value lists
are not inspected or promoted, preserving the existing normalizer's policy.

Supported lists retain existing malformed/duplicate/1,000-entry rejection. Selected
count preserves exact Decimal and fails qualification beyond six fractional places;
money retains the existing decimal-to-micros ROUND_HALF_UP conversion. Present
selected values must equal the original normalizer's numeric outputs. Required
impressions/clicks/spend retain its numeric validation. Errors are bounded MetaError
codes without provider response content. No response dictionary is changed.

Frozen `MetaPresenceCellsV1` supplies the native campaign, day, event descriptor and
five reviewed cells. Nested unsafe copies revalidate; generic/unavailable events
cannot qualify present selected cells, and nonpurchase value cannot become present.
`PRESENCE_PRODUCER_CONTRACT` is `meta.campaign-day.presence.v1`;
`QUERY_DESCRIPTOR` derives from the existing local pinned Meta API version using
the unchanged campaign-day query-version format. `UNKNOWN_ATTRIBUTION` explicitly
has null click/view windows and unknown report-time basis. No provider default or
causal interpretation is inferred.

## Checks Actually Run

- `/workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_meta_presence.py tests/test_reporting_presence_contracts.py`: **125 passed in 0.37s**, comprising 64 parser cases and 61 shared contract cases.
- `/workspace/inlet-venv/bin/ruff check .`: passed.
- `/workspace/inlet-venv/bin/mypy`: passed, 1,071 source files.
- `git diff --check`: passed.

Initial combined 120 cases passed before five added event-profile/list-bound/money
maximum cases. Initial static checks found a test constant comparison style issue,
an Any return annotation and test access to an imported symbol; all were corrected
before the final checks above. No product or legacy behavior was changed to pass.

Coverage includes 100 clicks/10 selected conversions/USD100 spend, explicit zero,
independent missing count/value, both supported purchase event IDs, overlapping
unselected event exclusion, lead value unsupported, precision/malformed/duplicate
errors, wrong advertiser/currency/date/native ID, missing required metrics, integer
limits, money rounding/max, JSON roundtrip, unsafe nested copies, selected numeric
disagreement and unknown attribution. Pure tests supply synthetic response objects;
there are no network calls, HTTP mocks, databases, grants, or persisted records.

This parser does not establish trusted ownership or persisted provenance. Import,
immutable original-window context, staging token binding and atomic publication
are deferred to separately reviewed 0090 work after finalized storage qualification.
Legacy in-progress no-context windows must remain legacy. This package does not
qualify import-to-API behavior, complete data coverage, planning quality, or launch.
