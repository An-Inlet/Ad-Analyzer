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
- Original historical142: 139 passed, 1 original SQLite row-lock skip, 2 failed,
  1,570.06 s. Outer harness correctly failed, 1,603.51 s.
- Exact historical UI supplement: 19 passed, 410.44 s.
- Strengthened coverage-map/unchanged-AST validator: 1 passed, 0.92 s.
- Whole Ruff, bare mypy (1,107 source files), current browser-driver Node syntax,
  and `git diff --check` passed before final ledger freeze.

Raw durable artifacts are under
`/workspace/inlet-evidence/20261008/retired-compatibility/`.
The forward88 terminal outcome is recorded after its active qualification completes. No aggregate/full-suite pass is claimed here.

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

## Preserved Historical Failures

The original142 batch failed only
`test_v2_execution_review_browser[sqlite-False]` and `[postgres-False]` at the
final browser result assertion: dynamically importing `optimization.mjs` failed.
Source inspection identifies a historical fixture omission: `optimization.mjs`
imports `candidate-read.mjs`, which imports `reported-rule-view.mjs`; the pinned
fixture's asset allowlist omits the latter, and its replicas application has no
static fallback. This is a source-supported explanation, not a newly captured
browser network trace. The original qualification did not modify pinned files, asset routing, assertions,
skips or timeouts to conceal the failure. `original-historical.log/xml` and
`original-outer.log/xml` preserve the child failure and outer propagation.

These historical failures block an all-pass qualification statement. They do not
establish a current planning application defect; the actual current history/UI/API
boundaries passed independently. W1 must include and report these assertions.

## Bounded Historical Fixture Asset Repair

Root subsequently approved an explicit child pytest plugin for only the two exact
`test_v2_execution_review_browser[sqlite-False]` / `[postgres-False]` nodes. It adds
a single GET fallback to each case's actual replicas application for
`/app/assets/reported-rule-view.mjs`, serving unchanged pinned file bytes. It checks
the pinned child sentinel and asset SHA256, then removes the route at teardown.
It neither changes the pinned tree/tests/assertions nor intercepts other paths,
capability guards, runtime construction, or provider calls. Outside those exact
nodes its autouse fixture immediately yields without resolving any application.

The harness records the plugin source digest, exact participating nodes, and asset
digest in child provenance. The19 and88 supplemental cohorts do not use the route.
The original142 failed evidence remains intact; only the two affected nodes are
requalified, not the entire142 batch.

Plugin SHA256: `0f391c23834544fba8d2f27274eee3b6df662f7ae932b9a59ae981dce9c899da`.
Asset SHA256: `5c9b6722b2717c9f38afc347ff9cd1b0b03fa50397ddd89e9588e3262f4e72a2`.

The exact two repaired browser cases passed on SQLite/PostgreSQL in36.81s;
`asset-repair.log/xml` retains the terminal result. Whole Ruff and bare mypy
(1,108 files) passed after the plugin addition. The original142 was not rerun.
