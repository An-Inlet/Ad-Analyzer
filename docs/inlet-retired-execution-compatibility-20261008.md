# Retired Execution Compatibility Qualification

This test-only package preserves the planning MVP's immutable advertising-write
prohibition. It does not restore retired customer controls, enable execution, or
qualify hosted behavior. The current application source is unchanged.

## Exact Historical Scope

`tests/retired_snapshot.py` pins local ancestor
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`, application tree
`6507ee4da861c63ebbc9ce0210c558c0de19d873`, and tests tree
`06cc6a9ecb7466c3e94a5bd6558ea73befbbe4cc`. This is the integrated pre-0086
initial execution implementation. Its bridge can create the original execution
consent and its original UI contains the tested execution controls. Current
planning-only consent is deliberately incompatible with that bridge. No contradictory
active/draft mandate is fabricated and no current capability guard is patched by
this historical runner.

The same installed Python/dependencies run an unchanged `git archive` in a separate
interpreter and temporary root. There is no fetch/install, shared database reset,
or external provider call. Existing historical fixtures own separate PostgreSQL UUID
schemas and SQLite databases. CI already checks out full history (`fetch-depth: 0`).
Missing local objects, prerequisites, changed collection, missing/incomplete JUnit,
child failures, unexpected skips, timeout, and excessive output fail qualification.

The final aggregate invokes three named, bounded subprocess batches:

| Batch | Exact Nodes | Manifest |
| --- | ---: | --- |
| Original bridge and execution UI | 142 | `nodes-2155ff3.json` |
| Additional retired UI controls | 19 | `nodes-supplement-2155ff3.json` |
| Initial forward execution/source contracts | 88 | `nodes-forward-2155ff3.json` |

All 249 nodes are explicitly listed under `tests/fixtures/retired_execution/`.
Each batch retains the original 1,800-second and 16-MiB output bound; the expansion
is not an increased timeout for one process. Only the original three named SQLite
row-lock limitations may skip. There are no new skips, xfails, collection-ignore
hooks, or blanket capability overrides. Original test bodies remain in current
files as `historical_contract_*` callables, and run under their unchanged original
names from the pinned source. `coverage-map.json` accounts for every invocation;
a current test validates unique complete mapping, actual current coverage names, and
AST equivalence against the pinned original function including decorators and body
(normalizing only its preserved local name). All 36 preserved functions match.

## Current Coverage

Actual current HTTPS/Chromium execution and optimization pages expose retained
history only, preserve session/tenant boundaries, and create no execution rows.
The current initial-review API checks default and configured cases: valid and forged
review requests return the planning-policy denial before runtime resolution.
These are unpatched `planning_boundary` tests. Other current route, provider-sink,
source-freshness and session tests remain active and are linked in the map.

`test_session_automation.py` retains its actual current engine assertions through
explicit per-function `retained_execution_engine` fixtures; its master-disabled
case remains an unpatched planning-boundary test. No global fixture is introduced.

Current schema, erasure, privacy, export and restore assertions are NOT archived.
Their genuine archived producer-to-current-schema fixture is independently frozen
at `fb40d8a`; see `inlet-retired-producer-current-lifecycle-20261008.md`.
Current lifecycle adaptation is a separate package. In particular, the original
historical populated-0085 downgrade assertion is supplementary; it cannot replace
the separately required CURRENT populated-0085 refusal test.

## Checks And Evidence

- Current HTTPS history and initial-review API: 8 passed, 2 intentionally deselected
  historical invocations, 21.02 s. `current-boundary.log/xml`.
- Current session engine: 49 passed, 1 original SQLite row-lock skip, 350.78 s.
- Exact historical UI supplement: 19 passed, 410.44 s.
- Strengthened coverage-map/unchanged-AST validator: 1 passed, 0.92 s.
- Whole Ruff, bare mypy (1,107 source files), current browser-driver Node syntax,
  and `git diff --check` passed before final ledger freeze.

Raw durable artifacts are under
`/workspace/inlet-evidence/20261008/retired-compatibility/`.
The original142 and forward88 terminal outcomes are recorded after their active
bounded qualification completes. No aggregate/full-suite pass is claimed here.

Final reproducible entry points use the disposable PostgreSQL URL and explicit disposable acknowledgement
from the repository test environment, plus `/workspace/inlet-venv/bin` tools:

```text
pytest -q -o addopts='' tests/test_retired_execution_snapshot.py
pytest -q -o addopts='' tests/test_current_advertising_history_browser.py tests/test_initial_preview_review_api.py -k 'not historical_contract'
pytest -q -o addopts='' tests/test_session_automation.py
ruff check .
mypy
node --check tests/javascript/current_advertising_history_browser.mjs
git diff --check
```

The first qualification began before expansion with the original142 batch only.
The19 UI and88 forward supplements run directly from the identical pinned detached
tree, each with exact collected node lists and separate JUnit/logs. The final current
pytest entry point invokes all three batches; no combined aggregate result is inferred
from their separate qualification. Original historical test bytes are unchanged.

The lifecycle author's distinct current0085 node is
`tests/test_retained_initial_rule_lifecycle.py::test_current_populated_0085_refuses_downgrade`.
It must be integrated and qualified with its real pinned initial-rule producer before
W1 aggregate; its future pass is not claimed by this package.
