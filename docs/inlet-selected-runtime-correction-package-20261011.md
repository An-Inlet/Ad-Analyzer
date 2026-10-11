# Actual Selected Correction And Successor — October 11

Test-only bounded Q11 coverage on `codex/inlet-w1-followup`, based on `32fb055`.
The existing actual range/selected/private-v4 API fixture generates a plan with
100 clicks, 10 selected conversions and $100 spend, then records a customer
decision. A changed injected provider HTTP response supplies four conversions.
The test publishes a new actual requested-range import, discovers and explicitly
confirms the selected event, captures its observations, saves a new input revision
and generates V2 through customer routes. No reporting rows are edited directly.

Checks establish that the import makes V1 stale and blocks a new decision against
it; V2 preserves 100 clicks/$100 and reports four selected conversions. Stable
native campaign identity is unchanged while snapshot selection, aggregate and
capture lineage change. V2 names V1's exact parent digest. Comparison exposes the
changed rationale and explicitly carries no decisions forward. V1 read/export
and its event history remain identical; no execution run or attempt exists.

## Verification

Evidence: `/workspace/inlet-evidence/20261011/selected-runtime-correction/`.

- Final SQLite/PostgreSQL cohort: **2 passed, zero skipped/failed/errors**, 50.379s
  (`final-bothdb.xml`), including unchanged traffic assertions.
- Prior SQLite run:1 passed, 25.906s; overlapping, not an additional unique case.
- Whole Ruff and configured no-path mypy: passed, **1,364 files**.
- Initial failed fixture attempt retained: confirmation correctly required the
  previous selection identity. Test now reads it through the actual state route
  before confirmation; no production condition was weakened.
- Independent source review found no P1/P2; final frozen-head closure recorded
  in the integration acceptance ledger.

This is actual offline acquisition-path qualification, not a live provider call
or the entire frozen Q11 Common Basis. Reconnect, refund correction, exact product
basis and expert usefulness remain separate. No production code, default policy,
credentials, hosted run, advertising write, push, merge or deployment changed.
