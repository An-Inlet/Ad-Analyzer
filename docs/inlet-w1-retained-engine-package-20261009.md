# W1 Retained Engine Regression Package

Implementation base `d665feb`. Root approved the
[23-function classification](design/w1-retained-engine-next-package-20261009.md).
Only explicit function-level `retained_execution` and
`usefixtures("retained_execution_engine")` decorators were added across six
modules. The existing test-only fixture and all production guards are unchanged.

An AST comparison against the original source removes only these two added
decorators and proves exact equality of every original statement, signature,
parameter and decorator. Proof: `/workspace/inlet-evidence/20261009/w1-retained-engine-package/ast-preservation.json`.
Shared helpers remain unmarked, so importers do not inherit execution capability.
Default planning boundary tests remain unmarked and execute in the same pytest
process to detect capability leakage. Actual existing fixture consent, scope,
review, financial hold and MockHTTP behavior is preserved; no grants or approvals
were synthesized outside those original fixtures.

## Scope And Corrected Coverage Baseline

The original frozen aggregate's1,247 shared-seed failures already have138 account/
native-read repairs plus72 TikTok read repairs (`ae470f1`, integrated`64c5fbc`):
**1,037 remain before this package**, as confirmed by exact original identities in
`successor-coverage-244.json`. The original proposal omitted that72-node credit;
its copied design ledger now corrects the stale1,109 figure. Root's29 direct-sink
transport repairs intersect none of these shared-seed failures. Other concurrent
repairs must be reconciled separately, never by summing whole test cohort counts.

This package targets147 exact frozen failed identities in23 functions; unchanged
collection includes one additional intrinsic SQLite PostgreSQL-lock skip. No
successor pass is retroactively attributed to the failed frozen aggregate, and
this package does not qualify current customer/read/privacy modules sharing helpers.

## Exact Focused Invocation

```sh
PATH=/workspace/inlet-venv/bin:$PATH \
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
python -m pytest \
  tests/test_publication_core.py tests/test_google_action_plans.py \
  tests/test_google_request_terminal.py tests/test_social_activation_journeys.py \
  tests/test_exposure_qualification.py tests/test_google_replacement_source.py \
  tests/test_planning_provider_transport_boundary.py \
  tests/test_planning_execution_boundary.py --tb=short --maxfail=2 \
  --junitxml=/workspace/inlet-evidence/20261009/w1-retained-engine-package/focused.xml
```

This uses existing disposable fixture schemas, not the frozen aggregate database.
No Full, hosted test, external provider call, workflow or current consumer ID change.
The current default boundary cohort retains86 separate cases.

## Terminal Result

**233 passed, one existing SQLite concurrency skip, zero failures/errors;399.48s
pytest (399.472s JUnit), exit0.** This comprises147 retained-engine passes and86
unchanged default-boundary passes, plus the intrinsic skip. Exact XML identity
intersection with original frozen failures is147, verified in
`frozen-node-coverage.json`; it is not233 repaired failures. Independent review
must close before integration/credit in the cumulative successor ledger.

Artifacts under `/workspace/inlet-evidence/20261009/w1-retained-engine-package/`:
`focused.log/xml/exit`, `ast-preservation.json`, `frozen-node-coverage.json`,
`ruff.log`, `mypy.log/exit`. Whole Ruff passed; bare mypy passed1128 source files;
`git diff --check` passed. The single focused run had no failures or repairs, and
no original assertion or parameter was changed after launch. No new test was skipped,
removed or weakened. Once independently accepted, these147 directly matched
shared-seed failures can be credited against this package's1,037-node baseline;
other concurrently reviewed packages need their own union reconciliation.

The materially longer successful retained paths are not comparable to fast frozen
setup failures as a CI capacity forecast. This package adds no runtime cap or timing
promise. The original aggregate remains1,330 failed and no new Full was run.
