# W1 Aggregate Freeze

Implementation integration: `753238a90c63a2b7b0c0289e68dc8406f43b0aa8`.
The commit containing this record is the immutable validation checkout; its exact
hash is also written to the external evidence manifest before execution.

The frozen W1 scope is complete: real requested-window generation is now the
customer default; primary/comparison form, original target and session behavior,
source corrections, historical artifacts, customer progress and current lifecycle
checks are preserved. No further feature changes enter this validation checkout.

Closed successors include service `bc76205`, actual browser `44307cb` with evidence
clarification `2a8244f`, default `8533b45`, current lifecycle `62d0033` and historical
harness `68a7271`. Each package's ledger retains exact failed attempts, focused
repairs, skips and final independent review. Default acceptance passed 85 API/contract,
17 browser/form and 115 compatibility cases in separate cohorts; these are not an
aggregate result. The current lifecycle and pinned historical runtime remain distinct.

## Known Result To Preserve

The unchanged historical test
`tests/test_initial_rule_start.py::test_exact_start_and_worker[postgres-unknown]`
failed in its 88-case qualification: the worker returned `blocked`, while the
assertion requires `completed`. The retained trace does not establish why. That
assertion stays in the full run with no skip, xfail or weakened expectation.
Two other historical browser failures were traced to a missing fixture asset route;
the reviewed exact-two-node plugin serves unchanged pinned asset bytes, and both
repaired cases passed. The original failed cohort remains recorded separately.

## Execution Isolation And Evidence

The aggregate uses newly created task-owned database
`inlet_w1_20261008_aggregate_1402a845_ci`; reversible migrations use separate
`inlet_w1_20261008_migrations_e3c06015_ci`. Both are on the existing local PostgreSQL16
test container at port 55432. The previous development database is not reset.
This isolation is necessary because the complete suite contains public-schema teardown.

Evidence root: `/workspace/inlet-evidence/20261008/w1-aggregate/`.
`isolated-databases.json` records creation. `cache-cleanup.json` records removal of
312 ignored, reproducible mypy cache directories from inactive local branches;
source, test artifacts, evidence, database state and the active worktrees were kept.
Free disk space increased from about 1 GB to over 11 GB before validation.

Verify the frozen tree, installed tools, pinned authentication bundle reproduction,
actual browser/media decoding, disposable target safety, Alembic head/base/head on
the separate migration database, whole Ruff, bare mypy and whitespace. Record any
local-versus-CI prerequisite difference explicitly. Then run once, with no marker
exclusions or test deselection:

```text
python -m pytest -ra --basetemp <evidence>/pytest --junitxml <evidence>/aggregate.xml
```

Keep stdout/stderr, exact environment/tool versions, exit status and complete JUnit.
Do not change the checkout or silently restart the aggregate. A failure is a valid
observation and must be reported. Any subsequent implementation or repair belongs
on a successor branch and cannot be presented as this frozen run's result.

Hosted diagnostics, remote pushes, deployment, live provider/model calls and all
advertising writes remain held. No full-suite pass, expert acceptance, live operation
or purchasable SaaS claim follows from this freeze.

## Preflight Whitespace Correction

Candidate `35aced79d46ed3bf2419cd6063b8e740479de6c7` passed auth bundle
reproduction, actual Chromium H.264/AAC decoding, isolated Alembic head→base→head,
whole Ruff and bare mypy (1,117 files). The baseline whitespace check identified
one extra EOF blank line each in `tests/retired_snapshot.py` and
`tests/test_plan_target_picker.py`. The successor removes only those blank lines;
no executable statements or test expectations change. The original candidate
checkout/evidence is kept, and a separate final checkout is used for the still
unstarted single aggregate. This is a preflight formatting correction, not another
feature package or a repeated aggregate.
