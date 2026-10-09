# Native Planning API Regression Split — 2026-10-09

Base root `d89d797`, approved split `10f52aa` and additive accounting seam `8a505a7`. Tests-only; no production, shared first-customer fixture, advertising guard or numeric production policy edits.

## Two Explicit Boundaries

The original V1 API function is preserved byte-for-byte in its AST except for its non-collected historical name. A new closed `initial_native` historical batch runs its exact ten original parameter nodes at `2155ff3e3ab00cd62057dd86cb49d45359d4f49f`. No prior historical batch was rerun. The original runtime/native-catalog environment comparison and original currency precision assertion remain authentic pinned API coverage.

The current customer API always selects V2 when a planning profile exists, while real PlanningConsent requires that profile. New `test_initial_planning_native_current` therefore explicitly tests current V2 equivalence, not the old route. Local `confirmed_native_case` configures a validated test profile before unchanged first-customer setup, actual config loading, calibration, budget preparation and planning confirmation. No synthetic consent, execution consent fallback or activated mandate is introduced.

Nominal current result preserves10m→11m, increase, review unavailable, provider-acceptance-unverified and explicit no spending authority. Session/generation changes occur during final native GET. Precision uses a coherent1micro test rule from initial setup and reaches exactly `native_budget_proposal_outside_consented_limits` after native IO. It does not accept an early profile mismatch as precision evidence. Real PlanningConsent exists and limits stay draft; zero execution consent/review/attempt/response/receipt/reservation rows and zero provider POSTs are asserted.

Current environment mode changes only the final local native reader factory to the actual owned reader built with a separately validated live profile. The saved/runtime contract-test profile remains unchanged. The actual reader's compound profile/environment request binding rejects before HTTP, mapped to `native_budget_unavailable`. This does not claim an environment-only check independent of digest; that exact original comparison is retained at the pin. V2 uses its current native budget contract rather than the original optimization MoneyContext; genuine prepared limits retain their actual goal period.

## Historical Accounting

Successor accounting is four wrapper batches/259 children:142+19+88+10. The collection manifest allowlist, planner's closed count contract, mapping invariant and synthetic partition expectations were updated together. All three prior manifest files are byte-identical to base. The frozen6a3/249 artifacts and old N3 candidate/tool bindings were not modified or requalified. New current and pinned case counts are separate, not replacements for lost assertions.

## Exact Evidence

Evidence root: `/workspace/inlet-evidence/20261009/native-planning-confirmation/`.

- Unmodified exact SQLite positive baseline: **1 failed**,3.657s, execution-consent planning guard409 (`baseline.log/xml`).
- Current precision probe: **1 passed**,6.180s (`precision.log/xml`); overlaps the following cohort.
- Current V2 ten cases plus unchanged planning-consent sixteen cases, both databases: **26 passed,0 skips**,91.583s (`current.log/xml`).
- Authentic new historical batch: **10 passed**,21.19s child pytest output; source/provenance/collection/log/JUnit retained under `historical-tmp/test_pinned_pre0086_execution_0/retired-execution/`. Only this new batch ran.
- First historical-wrapper/mapping/partition invocation:72 parent cases,66 passed/6 failed,36.127s (`historical-partition.log/xml`). The new historical wrapper and mapping passed; six synthetic partition cases exposed the remaining planner closed3/249 constant. This failure was retained, then corrected to explicit4/259 without changing source artifacts.
- Final narrow partition+mapping: **71 passed,0 skips**,5.920s (`partition-final.log/xml`), overlapping the earlier invocation. No DB/current/pinned repeat for that correction.
- Whole Ruff, bare mypy **1131 source files**, and diffcheck passed after the final planner change (`ruff-final.log`, `mypy-final.log`).
- Independent local AST comparison: original function at PIN equals renamed function after restoring its name; all prior manifest bytes unchanged. The passing mapping test checks this correspondence as well.

## Commands

Using `/workspace/inlet-venv/bin` tools from this worktree, XML paths beneath the evidence root:

```sh
pytest -q 'tests/test_initial_planning_native.py::test_exact_native_preview_and_fresh_io_fences[sqlite-None]' --junitxml=<evidence>/baseline.xml
pytest -q 'tests/test_initial_planning_native_current.py::test_confirmed_native_preview_current_api[sqlite-precision]' --junitxml=<evidence>/precision.xml
pytest -q tests/test_initial_planning_native_current.py tests/test_planning_consents.py --junitxml=<evidence>/current.xml
pytest -q 'tests/test_retired_execution_snapshot.py::test_pinned_pre0086_execution_contracts[initial_native]' tests/test_retired_execution_snapshot.py::test_every_retired_invocation_has_explicit_historical_and_current_coverage tests/test_partition_evidence.py --basetemp=<evidence>/historical-tmp --junitxml=<evidence>/historical-partition.xml
pytest -q tests/test_partition_evidence.py tests/test_retired_execution_snapshot.py::test_every_retired_invocation_has_explicit_historical_and_current_coverage --junitxml=<evidence>/partition-final.xml
ruff check .
mypy
git diff --check
```

The two DB-bearing qualified commands used `AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci` and `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`, with isolated UUID schemas. No aggregate source/database, Full, live providers or advertising writes. These focused results do not convert the original failed aggregate into a pass.
