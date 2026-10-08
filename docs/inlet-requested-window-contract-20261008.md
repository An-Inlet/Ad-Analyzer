# Requested Window Pure Contract — 2026-10-08

Base `f2156f7`; branch `codex/inlet-requested-window-contract`.
Frozen interface: `docs/design/planning-requested-window-contract-v1.md`.

Added only `app/campaign_performance/window_projection.py` and focused pure tests.
`project_requested_window(original, *, requested_window)` returns the independently
validated `RequestedWindowPerformanceV1` with an unchanged V3 source, its original
planning fingerprint, exact sorted campaign-day subset and presence digest, and new
`WindowCampaignSummaryV1`. Summary metrics reuse `MetricSummaryV1`; counts serialize
as canonical decimal strings. Pydantic models are frozen, extra-forbid and revalidate
copies. Requested-window copies are reparsed; numeric authority flags are rejected.

The projector validates the supplied V3 campaign subset, not the whole completion
source graph. It neither accepts whole-graph inputs nor claims source authenticity.
A future owned reader must validate/index the real graph once in its transaction.
The existing V1/V2/V3 models and public summarizers are unchanged.

UTC roundtrips of both local-midnight folds reject ambiguous/nonexistent boundaries.
Requested days are counted by calendar, not elapsed hours. Known valid-source
incompatibilities raise `WindowProjectionUnavailable` with exactly the three frozen
reasons; forged wrappers and invalid source data remain validation failures. No
intersection, fallback totals, date replacement, attribution inference or provider
request is introduced. Per-metric completeness requires the original flags, actual
scope and every requested day/cell. Missing calendar days are separate from absent
returned cells; empty/all-missing is null. Only explicitly selected complete zero
qualifies the zero flag. Decimal work uses explicit `Context(prec=50)`, including
validation of the unchanged V3 under hostile caller contexts.

## Checks

- Pure requested-window + unchanged presence summary/contracts: **102 passed**.
- Whole Ruff passed; configured mypy **1,092 source files** passed; diff check passed.
- Exact tests include 56-day original -> seven-day slice with unchanged original
  bytes, 100 clicks/10 conversions/USD100, complete zero, absent selected cells,
  absent days, empty subset, independent value, partial pagination/closed flag,
  partial original actual scope covering an interior request, DST23/25-hour days,
  ambiguous/nonexistent/nonmidnight boundaries, out-of-range/open days, copied
  summary/subset/digest/identity/window tampering, hostile Decimal traps/exponents,
  and the actual 2MiB wrapper boundary/+1 byte refusal without truncation.
- The real byte-bound fixture pads an existing unbounded legacy decimal zero
  spelling; the original V3 still fits its own cap. This exercises wrapper overhead
  without weakening either cap or changing production legacy parsing.

Commands:

```text
/workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_requested_window_projection.py tests/test_reporting_presence_summary.py tests/test_reporting_presence_contracts.py --junitxml=/workspace/inlet-evidence/20261008/requested-window/pure.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

Raw log/JUnit retained at `/workspace/inlet-evidence/20261008/requested-window/pure.log`
and `pure.xml`. No database, adapter, policy, composer, API, import or UI integration
was changed or qualified. No live/provider, Full, comparison-product, ownership or
source-proof acceptance claim. Next package is the separately reviewed owned reader
and its transaction-bound whole-graph reuse, before policy/evidence consumers.
