# Initial Objective Reuse — 2026-10-07

Isolated branch `codex/inlet-initial-objective-factoring`, source base 144786f.
Private interface was frozen before implementation at 6cca08a in
`design/initial-objective-input-context.md`.

Calibration now returns the already validated current report, same-transaction locked
goal and exact stored-definition digest. The immediate preview input consumer compares
the selected completion against that report and reuses the goal/digest. It retains
`goals.expect`, the SECOND actual `goals.assessment` with freshly sampled time, final
original-session authorization, and fresh expiry. The later full preview input pass
after mandate validation is unchanged. Public `current_objective` still performs its
complete independent guard. No context crosses a request, transaction or IO boundary.

Retaining late assessment matters: confirmed-goal validity depends on source freshness
and rolling measurement retention even when database rows remain locked. No business
freshness formula, numeric policy or observation lifetime was changed. This is a source
implementation change only; initial Start/service/UI files remain untouched.

## Profile Limitations And Evidence

Same configured PostgreSQL positive path, unchanged explicit fixture-only 120-second
profile, same external statement listener and perf_counter worker/test-call timers:
worker 34,308 SQL statements (previous 36,884), whole test 47,044 (previous 50,348).
That is about 7% fewer statements; it does not imply lower elapsed latency.

The first new measured run PASSED with worker 36.349s and whole test-call 54.076s,
which is SLOWER than the preceding three samples (worker 20.503–22.204s). Concurrent
adverse/static/R3 work was active, with a subsequent host load-average snapshot 4.83
versus 1.98 during earlier samples. Neither comparison is an isolated benchmark;
instrumentation overhead is included and not independently quantified. No elapsed
improvement or ordinary 30-second usability qualification is claimed.

Raw evidence: `/workspace/inlet-evidence/20261007/initial-objective-after.jsonl`,
`initial-objective-after.log`, and `initial-objective-profile-load.txt`.

## Validation

Terminal regression/check results are recorded below. New regressions use actual
configured inputs and inject adverse source/goal revision changes at the post-mandate
boundary. A selected historical completion cannot substitute for the current report.
Actual Shopify baseline staleness introduced AFTER calibration validation must still
fail the later real goal assessment. Existing erasure/revocation/expiry/standalone-read
checks remain. No Full, hosted retry, remote action, live call, merge or deployment.

- `pytest tests/test_initial_source_fresh_boundaries.py tests/test_initial_rule_source.py
  --durations=5 -x`: **26 passed in 172.47s**, no skips, SQLite/PostgreSQL. Log:
  `initial-objective-adverse.log` in the evidence folder above.
- `pytest tests/test_initial_calibration.py tests/test_initial_preview_v2.py
  tests/test_initial_preview_binding.py tests/test_initial_rule_worker.py --durations=5 -x`:
  **31 passed in 47.02s**, no skips. Log: `initial-objective-compatibility.log`.
- Profiled PostgreSQL configured positive test: **1 passed in 57.89s** (test-call 54.08s), log above.
- Whole Ruff, repository mypy (**934 files**) and diff checks passed. The initial mypy
  run required an explicit missing-definition rejection to narrow the stored optional
  type before fingerprinting; the check preserves denial rather than fabricating a digest.

Total **58 successor checks passed**. PostgreSQL used isolated disposable fixture
schemas in `inlet_oct07_next_integration_ci`; no qualification database was touched.
