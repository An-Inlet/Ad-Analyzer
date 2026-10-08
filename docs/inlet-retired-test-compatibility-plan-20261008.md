# Retired Execution Test Compatibility — Bounded Repair Proposal

Current base: `4fc2b94`. Investigation only; no product, fixture, marker or collection changes yet. Do not run the aggregate until reporting-window integration and this repair are frozen together.

## Verified Historical Runtime

Pin `2155ff3e3ab00cd62057dd86cb49d45359d4f49f`:

- app tree `6507ee4da861c63ebbc9ce0210c558c0de19d873`;
- tests tree `06cc6a9ecb7466c3e94a5bd6558ea73befbbe4cc`.

This is the integrated initial-Start implementation immediately before the planning transition. The subsequent `2155ff3..3377fa6` diff contains four documentation files only. At the pin, `app/initial_planning/preview.py` uses `execution_mandates.checked` for both preview creation and read; the review bridge consequently uses the same actual active execution consent. It does not combine an active execution mandate with the current 0086 draft-only planning confirmation. Its old UI assets and routes are present together. The pin has none of today's immutable planning capability guards.

Current dependency requirements equal that pin's pyproject requirements; only pytest strict-marker configuration changed. A detached read-only checkout at `/workspace/inlet-retired-runtime-2155` successfully collected the 13 modules below: **144 nodes in 4.81s**. This is import/collection compatibility, not execution acceptance. Raw collection: `/tmp/inlet-retired-2155-collection.txt`.

CI already uses `actions/checkout@v4` with `fetch-depth: 0`. The harness must verify the exact local object and ancestry before extraction, fail explicitly if absent, and never fetch an arbitrary URL/commit or fall back to current code. No dependency installation/network is needed inside the test.

## Single Historical Harness Proposal

One clearly named current pytest historical-contract entry invokes a single bounded subprocess in an isolated extraction of that exact git tree. Preserve original app, schema, conftest, test and JavaScript bytes; record pin, tree hashes, selected node IDs and child JUnit. Use the current Python interpreter/dependencies, distinct basetemp/output directories, and a recursion sentinel. Do not import old modules into the current process, patch current advertising guards, rewrite historical assertions, or change current production settings.

The child uses the frozen real fixtures: SQLite in memory, PostgreSQL unique `inlet_test_<uuid>` schemas with schema-only teardown. Require the existing disposable PostgreSQL environment/flag; no shared DB reset or migration against an active schema. Browser/native/identity IO remains localhost and existing MockHTTP/FakeProvider fixtures. Child failures, nonzero exits, missing results or unexpected collection fail the parent test. Existing intrinsic SQLite concurrency skips must be reported, not enlarged. Preserve the complete manifest and do not select only passing nodes.

Initial manifest (all original assertions retained):

- `tests/test_initial_preview_review.py` (all nine functions).
- `tests/test_initial_preview_review_api.py::test_configured_review_uses_owned_digest_and_never_approves`.
- `tests/test_initial_planning_browser.py` (both unavailable and review scenarios against their matching original UI).
- `tests/test_initial_automatic_browser.py`.
- `tests/test_customer_execution_ui.py`.
- `tests/test_customer_optimization_ui.py`.
- `tests/test_customer_social_execution_ui.py`.
- `tests/test_configured_google_execution_browser.py`.
- `tests/test_configured_meta_execution_browser.py`.
- `tests/test_configured_tiktok_execution_browser.py`.
- `tests/test_configured_optimization_browser.py`.
- `tests/test_v2_execution_browser.py`.
- `tests/test_session_automation_ui.py`.

The exploratory 144-node collection included the full preview-review API module, so the final exact manifest must recollect the narrower configured function and record its actual node count. Do not present 144 as that final manifest's count.

Current discovery must explicitly replace the retired runtime invocations with the named historical runner and substantive current assertions, not silently ignore/deselect them. A provenance manifest explains where every original function/parameter runs. Keep shared helper imports available for still-current tests. Merely adding retained-execution opt-in to the old browser tests cannot repair removed DOM controls.

## Current-Policy Coverage That Must Remain Current

- `test_initial_preview_review_api.py::test_owned_status_default_off_and_session_binding` already validates actual preview bytes, status, CSRF, session binding and exact planning 409 with zero approvals/attempts. Add a configured-runtime variant which proves the guard runs before runtime construction/financial IO; do not invoke the incompatible old fixture.
- Existing planning boundary suites and real planning/catalog/progress browsers remain unpatched. Initial planning/browser unavailable cases need current no-review/no-Start control assertions, not a historical asset substitution on current routes.
- Current execution/optimization pages are owned history-only views. Add or retain real current history/foreign/session and no-control/no-write checks beside archived action-control assertions. Existing customer execution/optimization/session API partitions already establish their server-side denials.
- `tests/test_initial_budget_mandate_browser.py` is already marked `planning_boundary`; retain it on current code and current independent planning confirmation.
- Pure initial/session contracts and migration tests stay current. No wholesale `initial*` exclusion.
- Existing explicitly marked current retained-engine suites keep their per-function/nonautouse opt-in. Never mark a mixed module globally merely to repair one historical function.

## Additional Fixture Dependencies Requiring Explicit Resolution

`ready_preview_review` -> `test_initial_preview_review.ready` is also consumed by:

- `tests/test_initial_review_lifecycle.py`;
- `tests/test_initial_execution_proof_storage.py`;
- `tests/reported_feedback_lifecycle_fixture.py` -> `tests/test_reported_feedback_lifecycle.py`;
- `tests/test_populated_planning_restore.py::test_native_restore_real_protected_meta_review`.

Do not claim that archiving only the 13-module manifest makes these pass. Their historical producer coverage can run unchanged in the pinned cohort; their current lifecycle/schema/privacy assertions must remain qualified on current code. A concrete next seam is a genuine historical producer output generated in the isolated pinned process, restored only into its own disposable schema and migrated through the real current migrations, then inspected by current export/erasure/history code. This is a separate bounded fixture task: it must preserve exact row provenance, original sessions and original holds, never insert synthetic approval/authority rows or reuse an old runtime object inside current code. First inspect which existing current history fixtures can replace these dependencies without that bridge.

Also unpartitioned by static inspection: `tests/test_session_automation.py`, `tests/test_initial_rule_start.py`, `tests/test_initial_rule_acceptance.py`, and `tests/test_initial_concurrent_start.py`. Their current planning denial cases must remain unpatched; forward-engine cases require either explicit retained fixtures where the current semantics remain reachable or the pinned cohort where 0086 makes them historical. This inventory is not a claim of exhaustive aggregate failures.

## Concrete Validation Sequence

1. Freeze the historical manifest, runner/provenance contract and current-case replacement map; root approval precedes implementation.
2. Run collection-only for that exact frozen manifest in the pinned tree; no aggregate.
3. Qualify current-policy replacement cases on SQLite/PostgreSQL and one historical subprocess cohort using the same two backends. Preserve failures and repair fixtures only where justified. Run Ruff, bare mypy, JS syntax and diff checks once final.
4. Integrate reviewed reporting-window work and compatibility repair into one candidate; freeze its hash. Parent executes the normal complete command with no marker exclusion: `python -m pytest -ra --basetemp <unique-current-temp> --junitxml <aggregate.xml>`. Its named historical test invokes the exact separate child cohort and retains child JUnit/provenance.
5. CI safety/migration/security gates remain as declared in `.github/workflows/ci.yml` and `scripts/validate.sh`. Do not substitute `-m planning_boundary`, `-m 'not retained_execution'`, skip/xfail, or a hand-picked pass list for the complete aggregate.

No tests executed during this investigation; only the named bounded collection ran. No guard weakened, coverage deleted, live IO, remote fetch, deployment or aggregate run.
