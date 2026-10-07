# Executor Recovery And Frozen Full Repairs

Recovery confirmed at 2026-10-07T17:57:09Z. Executor uptime 12h27m; saved integration
`e444a27765a37161b007e5daf5ca682216eb18a5` was clean. The frozen qualification
checkout remained clean at `bb836c207c8fb846d8e184b2736f618f3bf49806`, tree
`b1a6a9d55370857b17af6b12b2aa83789fff45ed`. No interrupted shell process or lost
committed work was observed. This does not establish why the service was unavailable.

## Terminal Full Evidence

Prescribed `bash scripts/validate.sh Full` completed at16:21:56.662998 UTC,
exit1, total6407.665094 seconds. Primary pytest: **5175 passed,77 skipped,11 failed,
161 warnings in6203.57 seconds** (5263 collected test cases). Reset and upgrade0082
passed. Because primary pytest failed, the subsequent prescribed stages did not run.
A separate nested six-test JUnit is retained; it is not an additional Full stage.

Artifacts remain under `/workspace/inlet-evidence/20261007`: `linked-full.log`,
`linked-full-terminal.json`, `linked-full-start.json`, `linked-full-resources.jsonl`,
`linked-full.exitcode`, and both timestamped JUnits in `linked-full-timings`.
SHA256/byte counts are recorded in `linked-full-artifact-hashes.json`. The frozen
checkout and its `inlet_oct07_linked_r2_ci` database were not altered or restarted.

## Repair Package

Branch `codex/inlet-full-recovery-fixes`, based on clean integratione444a27:

- Eight Google completion archive failures: the archive input projection omitted
  internal `fence` and `request_digest` scalars needed by the exact ownership
  validator. Select them for bounded validation only; keep them out of exported
  scalar fields. Actual archive tests also reject each mismatched original binding.
  Both historical and new completion document schemas retain strict validation.
- Registry failure: already repaired by2e35851. Required acquisition metadata guards
  remain installed separately from the exact declared-model inventory.
- Populated0057 migration fixture: current receipt producers now append later0066
  protected original-response captures. Scope the historical fixture's capture
  omission to its initial seed only, restoring real producers immediately afterward.
  No protected row is deleted and the populated downgrade refusal remains intact.
- Explicit route classification: classify `/app/tiktok-linked` as an inert public
  HTML shell, consistent with other customer pages. Its data APIs remain guarded.

Actual local checks on disposable `inlet_oct07_next_integration_ci`, per-test schemas:

`python -m pytest -ra tests/test_export_execution_domains.py tests/test_export_optimization.py tests/test_export_owned_domains.py tests/test_model_registry.py tests/test_owned_outcome_migration.py tests/test_route_boundaries.py::test_every_assembled_route_has_an_explicit_boundary`

**27 passed,5 Alembic deprecation warnings in69.26s**, zero skips. Includes all11
failed Full IDs. Log `recovery-focused.log`.

After adding explicit original-binding corruption assertions:
`python -m pytest -ra tests/test_export_execution_domains.py::test_owned_execution_json_export_is_complete_and_strict`:
**2 passed in9.88s**, SQLite/PostgreSQL, log `recovery-export-binding.log`.
Whole `ruff check .`, prescribed `mypy` (923 files), and `git diff --check` passed.
No successor Full has been launched and these results do not replace failed Full.

## Preserved Work And Next Package

- `/workspace/inlet-learning-requirement-trace`: clean50b47b8, including configured
  repeat runtimeacc1d57, own-successor admission7a89035, initial0084 source through
  366f267, and initial candidate/worker/review/export dispatch. Its local check
  records survive in docs/inlet-progress.md and /tmp logs. These have not been
  independently requalified or integrated by this recovery package.
- `/workspace/inlet-initial-rule-runtime`: clean366f267.
- `/workspace/inlet-operational-customer-ui`: clean da587d6; strict rule display,
  exact Start consent and session-rotation fence. Independent review closure was
  not recovered; do not claim it closed.
- No subordinate agents were active in the recovered agent listing. Saved branches
  are the source of truth; no background development is assumed.

Next: assemble and review preserved reported-rule runtime/UI, actual configured
HTTPS customer→worker coverage (including session/source retraction and unknown
responses), then exact initial Start binding and usable initial automatic flow.
The proposed initial Start relation is described in scheduler branch
`docs/design/initial-rule-start-binding-interface.md`; no0085 reservation or
implementation is made by this recovery package. Full MVP remains the goal;
production numeric policies and live qualification remain distinct requirements.

No hosted dispatch/retry, live provider action, remote push, merge or deployment.
