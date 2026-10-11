# Google daily budget hypotheses: input-only admission

This package adds optional original-receipt owner hypotheses to saved planning inputs. It does not enable budget edits, generated owner recommendations, a new policy, or a public/default UI. Every non-null tuple, including an explicit empty tuple, is refused by all generation entry points and the PlanVersion invariant. Absent fields retain existing nested serialization and digest bytes.

Admission rederives the full owner witness from the actual original catalog receipt and checks its opaque selection commitment against the original actor/session/authentication epoch. Both resolution passes carry exactly the validated resolved intents; the final link checks repeat the complete active binding before committing input and links together. Existing capability-before-replay order is preserved. The existing constructor already enforces exact canonical policy bytes; no new normal-runtime policy flaw is claimed.

Historical read, request recovery, replay, and export use original retained receipt scalars and the strict historical kernel. They do not invent source fences for unrelated unselected accounts, consult current paid eligibility or receipt TTL, or adopt the current session as the original observer. Missing or altered linked evidence refuses the read. Real link deletion is qualified as missing-dependency erasure, not full workspace privacy erasure.

## Qualification evidence

Durable evidence: `/workspace/inlet-evidence/20261011/google-budget-owner-inputs`.

- `pure01`: 15 passed in 4.599s (JUnit), including the unchanged nested legacy byte/digest golden; no pure repeat planned.
- `sqlite01`: 12 passed in 40.125s (JUnit). This initial smoke predates stronger flushed-row and history tests.
- `ruff-initial.log`: initial test line-length error, fixed by formatting. `ruff02.log`: whole Ruff passed.
- `mypy01.log`: configured no-path mypy passed, 1455 source files.
- `collect-final01.log`: wrong Q08 file path; no tests executed. Corrected `collect-final02.log` selects 36 cases: 34 new actual API/history cases and two unchanged Q08 positive cases.

The controlled service-clock sentinel is placed after the original receipt deadline while authentication keeps the real wall clock. Completed replay/history never sample that clock or call current `_load`. This proves no current TTL dependency; it is not a natural elapsed-wall-clock expiry test. Scalar-corruption probes change only detached original loaded receipt rows; they do not disable immutable SQL triggers. The post-link fault asserts both an input and a receipt link were flushed before raising, then verifies complete rollback.

- `sqlite02`: seven new/strengthened cases passed in 18.917s (JUnit), overlapping the original positive and rollback scenarios plus five new history cases.
- `both03`: exact 36-case cohort passed in 163.240s (JUnit), zero failures/errors/skips. This repeats the 17 SQLite scenarios qualified above and adds their PostgreSQL counterparts plus unchanged Q08 positives on both databases.

Commands use `/workspace/inlet-venv/bin/pytest`, unique `/tmp/inlet-owner-input-*` basetemps and durable JUnit/log paths. PostgreSQL uses the existing disposable local test database with the existing per-test isolated-schema fixture; no database reset or production schema change. The final cohort consists of `tests/test_google_budget_input_api.py`, `tests/test_google_budget_input_history.py`, and unchanged `tests/test_creative_q08_runtime.py::test_actual_v5_q08_empty_owned_query_zero_goal_preparation`, with `-x --durations=20`.

Independent source review approved the production implementation and expanded test boundaries. Final whole Ruff, configured no-path mypy (1455 source files), and diff checks passed. Parent independently verified the final JUnit totals. Immutable final source review is requested at freeze. No elapsed expiry, cancelled-paid-account acceptance, or full workspace erasure claim is made by the new history probes; existing authorization and lifecycle boundaries are preserved.

## Reviewed Integration

Author `d0fa80272c3d20cb127131f6cabd92a1cf434607` integrated as `cd65fdd`.
Independent immutable source/evidence review CLOSED with no remaining P1/P2.
Root independently verified all16 evidence hashes and four XML summaries;
root-verification.json records this without adding overlapping test counts.
Root whole Ruff and configured no-path mypy passed over1,455 files; diff passed.
No API/browser or exhaustive rerun at integration. Original9d7aa2e qualification
remains separate; these local checks do not qualify a live provider or release.

Next: Q09 bounded baseline on this integrated consumer, plus design-only owner
hypothesis output. Current generation refusal remains in force. The next output
contract must not equate a non-increasing daily request with compliance with the
confirmed total spending limit. Six human judgments and R01 remain open.
