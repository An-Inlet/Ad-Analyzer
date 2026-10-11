# Pure selected and traffic paired composer — 2026-10-11

Implementation on `codex/inlet-selected-paired-composer`, based on root traffic
producer `3b8181e`, approved interface `b28b26b`, optional traffic proof
`62a748b` (local `7001b44`) and prepared traffic projector `b2ee4dd` (local
`402cd67`). Only this package's two new pure modules, tests and this ledger are
its implementation delta. No registry, service, reader, schema, execution or live
capability is activated.

## Behavior

`selected_paired_evidence.py` validates the complete selected bundle and exact
saved traffic graph set, including graphs for accounts without successful windows
or catalogs. Every successful selected slot has exactly one matching traffic
window or typed absent-provenance gap. Source, aggregate, account, full campaign
map, native/local campaign, UTC window, arithmetic and reference commitments must
agree. Publication timestamps come from the retained receipt/header completion;
no acquisition start is invented. Each account graph gets one validated prepared
projector reused for its windows. Copied models are revalidated. Overflow rejects
rather than dropping observations/references.

`SelectedPlanComposer` directly consumes that paired DTO under the exact reserved
v4 policy. It produces a manual PlanVersion with the retained proof and all
selected, traffic, catalog, commerce and context references. Legacy composers and
bytes are untouched. It preserves manual constraints, scenarios, fixed allocation,
exclusions, creative capacity and ceilings. No V3 evidence/document is fabricated.

Descriptions distinguish exact selected event resource and metric family from
raw clicks/spend. Both `conversions` and `all_conversions` retain Decimal counts.
100 clicks / 10 selected events / 100 USD is positive reported evidence. Only
complete explicit selected cells summing to zero permit full-window observed-zero
wording. Partial zero is not complete zero; missing traffic is unavailable, and
partial spend is an observed subtotal. These are descriptive observations, not
causal lift, forecast ROI, native financial qualification or spending authority.

## Checks and retained evidence

All evidence: `/workspace/inlet-evidence/20261011/selected-paired-composer`.
All tests are deterministic pure synthetic packets; there are no database,
provider-network, empirical calibration or actual v4 API acceptance claims.

- `final01`: 145 passed, 0 skipped, 22.14s. Exact files:
  `test_selected_paired_composer.py`, `test_window_composer.py`,
  `test_planning_document_contracts.py`, `test_selected_planning_inputs.py`,
  `test_selected_plan_bundle.py`. This includes legacy nested input/full-plan
  canonical bytes and digest tests.
- `final03`: 29 passed, 0 skipped, 9.41s after two additional tests. Exact new file
  `tests/test_selected_paired_composer.py`; includes unsafe copied pairing/map/
  receipt/arithmetic/deadline attacks, both families, complete/partial/unknown
  selected counts, missing/partial traffic, all pinned unused graphs, one prepared
  graph for two windows, and positive evidence under zero ceiling.
- Whole `ruff check .` passed (`ruff-final2.log`).
- Whole `mypy --cache-dir=/tmp/inlet-range-receipts-mypy-cache` passed, 1352 source
  files (`mypy-final2.log`).
- Fresh subprocess imports of both new modules passed. `git diff --check` passed.

Pytest commands use `/workspace/inlet-venv/bin` on PATH, unique scratch basetemps,
`--junitxml=<evidence>/<run>/junit.xml` and `--durations=20`. No Full aggregate or
PostgreSQL lane was used.

Initial failures are retained, not overwritten: `pure01` had nine fixture failures
from duplicate currency/timezone kwargs; `pure03` had one fixture failure from a
partial label on a zero-returned-row window; `final02` had two added-test failures
from a nonexistent header field and an intentionally strict confirmed-goal/ceiling
mismatch. The fixtures were corrected without relaxing guards. `mypy-final.log`
retains the test's implicit reexport error; importing the prepared class from its
own public module fixed it. No application failure was suppressed.

## Remaining assembly

Root owns current/history traffic-proof reconstruction and the future owned
paired collector/service wiring. This commit supplies runnable pure composition,
not registered production v4 generation. Existing gates remain unchanged.

## Independent review correction: UTC instant ordering

Review of `62b3dd3` found same-ZoneInfo fold comparisons could misorder paired
expiry bounds and composer evidence deadlines. The follow-up compares observed,
collected, generated and expiry instants in UTC; the composer normalizes generated
entry time and chooses its minimum deadline in UTC. Existing reference documents
remain unchanged.

Three regressions use a valid reconstructed native/catalog fixture around the
2026-11-01 America/New_York fold: a later instant with an earlier wall-clock label
cannot extend paired evidence, generation after the actual expiry is refused, and
equivalent generation offsets produce identical documents/digests with a UTC
valid-until value. `fold-final`: **32 passed, 0 skipped, 8.69s**. Whole Ruff and
mypy **1352 source files** pass (`ruff-fold-final2.log`, `mypy-fold-final2.log`);
`git diff --check` passes. No database/Full/runtime registration was run or changed.

Retained `fold01`/`fold02` failures are test fixture construction failures: changing
only catalog reference expiry, then neglecting native observation-start rebinding,
correctly failed exact catalog validation. `fold03` then passed all three targeted
regressions. The test-only explicit import repair is recorded by the retained
`mypy-fold-final.log`; no type exemption or application guard was added.
