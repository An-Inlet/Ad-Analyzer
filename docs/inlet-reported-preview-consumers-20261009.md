# Current Reported Preview Consumers — Phase 3

Branch `codex/inlet-reported-preview-consumers`, base `6baa8b3`.
Reviewed exact28 scope only; configured-runtime10 explicitly deferred and untouched.
No production code, old fixed producer, global acquisition/baseline helper,
ExpectedPlanningConfirmation, auth clock or TTL changes.

New `reported_planning_journey_fixture` brackets the entire consumer with the reviewed
relative original and strict financial finalizer. It acquires current actual reports,
refreshes commerce, prepares/confirms genuine current PlanningConsent and constructs
a genuine V1 preview using the existing read-only native catalog machinery. The
native MoneyContext uses exact checked planning limits period; scope and target-set
match is asserted. Qualification/exposure callbacks are forbidden, current native
requests must all be GET. Historical one POST is the authentic scalar producer
count; it is never added to the current server recorder. Original ledger/effect graph
remains exact, with only the approved planning draft/revision/confirmation addition.

The new default V1 probe verifies actual stored PreviewIntentV1/InitialPreviewV1,
owned readback and46m→47m feedback before consumer edits. It passed on both databases
without a source/profile/period mismatch or guard change.

Consumer edits are setup/fixture imports/parameters plus explicit original POST scalar
and separate current GET recorder assertions. All original post-baseline assertions
and parameter decorators remain. The prior14 negative function is unchanged, including
source formatting; it is excluded from this run/recovery credit. Preserved tests cover
actual populated0078 downgrade/upgrade exact bytes, lossy-history refusal, raw owned
pointer constraints, retention cap, current-only history, physical dependency/pointer
retraction, real V1 regeneration/no compounding, final-authority rollback and actual
independent PostgreSQL races. Existing two SQLite concurrency skips remain unchanged.
No generic deletion or effect allowlist was added; strict finalizers passed intact.

## Exact Evidence

Directory `/workspace/inlet-evidence/20261009/reported-preview-consumers/`.
All DB commands use existing disposable localhost PostgreSQL URL/flag, isolated
schemas and exact owned SQLite files; no aggregate DB/source/reset.

- `pytest -q tests/test_reported_planning_v1_fixture.py`:2passed43.001s
  (`probe.log/xml`, probe-artifacts). This is new fixture acceptance, not recovery credit.
- Collection of the three consumer modules excluding
  `fixed_current_report_requires_retained_owned_terminal_proof`:30nodes=28selected
  failures+2existing skips (`collection.log`).
- `pytest -q tests/test_reported_feedback_real_preview.py tests/test_reported_feedback_preview_guards.py tests/test_reported_feedback_revisions.py -k 'not fixed_current_report_requires_retained_owned_terminal_proof' --maxfail=3 --basetemp=/workspace/inlet-evidence/20261009/reported-preview-consumers/qualified-artifacts --junitxml=/workspace/inlet-evidence/20261009/reported-preview-consumers/qualified.xml`:
  **28passed,2existing skips,0failures, 313.354s**, first invocation.
  `qualified.log/xml` retained; maxfail did not stop the completed cohort.
- `pytest -q tests/test_reported_planning_original_guard.py tests/test_reported_planning_relative_file.py`:
  14passed1.955s (`strict-compat.log/xml`), overlapping guard compatibility only.
- Whole Ruff/bare mypy: passed1,190files (`ruff-final.log`, `mypy-final.log`),
  final mypy uses `MYPY_CACHE_DIR=/tmp/inlet-reported-preview-mypy`. Diffcheck passed.

`selected-original-nodes.json` retains all28 original frozen identity records.
`exact-original-coverage.json` proves exact set equality between those28 identities
and passing JUnit nodes; the only excluded current nodes are the two original SQLite
skips. `assertion-preservation.json` records AST comparison for11 test functions,
including unchanged parameter decorators and exact prior14 function AST. Only the
explicit original server.posts counter assertion becomes verified scalar original count,
with separate current-native GET-only check. All producer IDs/logs/SourceLifetime
manifests and test DBs remain under preserved evidence basetemps; verified immutable
extracts were removed through SourceLifetime.

This is bounded28-node recovery evidence subject to independent review, not a full
aggregate pass or a configured-runtime10 claim. Stage2's16 new durable cases remain
separate regression evidence and are not added to original failure recovery totals.
