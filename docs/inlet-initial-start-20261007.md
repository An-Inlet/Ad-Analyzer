# Initial operational Start — 2026-10-07

Branch `codex/inlet-initial-start-binding`, isolated from root's 0083 qualification.
Base `50b47b8`; reviewed runnable-inventory repair `51e55e0` retained as `0de1f46`.
Exact shared API contract frozen at `15e8ad4`. No remote push, live verification,
provider call, credential action, merge or deployment.

## Implemented backend

- 0085 protected scalar Start links original session-run to exact initial work/preview,
  policy and stable opportunity commitment. Composite scoped FKs, immutable insert/update
  guards, protected deletion and genuine candidate-erasure paired SET NULL are enforced.
  Derived evidence remains erasable; source deletion blocks forward work while retaining
  protected financial/reconciliation audit. Populated downgrade refuses.
- Additive exact initial Start plus separate preview-specific named policy/mandate choices.
  Initial choices never enter legacy/repeat candidate/automation menus. No numeric or
  production source is registered by default.
- Native catalog/source reads run outside admission locks; final authority/source fences
  atomically insert candidate, run and link. A second check after IO closes concurrent
  duplicate Start races. Worker takes only the exact linked job. Admission binds its
  current result and calls `consume_origin` after admission flush and before provider-run
  creation in the same transaction, without fabricating a human approval.
- Read-result initial reconstruction is deferred to its mandatory final full initial guard;
  standalone `current` remains unchanged. Review guard metadata checking can use the same
  freshly validated locked tuple within the automatic guard; no cache or IO boundary reuse.
- Configured manifest/policy/source unions reconstruct the actual initial runtime. Customer
  API tests use configured pinned files and source registration, actual owned report/native
  reads with MockHTTP, real preview/consent/Start/worker/admission; no seeded execution rows.

## Checks actually run

Common environment for DB tests:
`PATH=/workspace/inlet-venv/bin:$PATH`
`AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci`
`AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`.
All PostgreSQL cases use isolated disposable fixture schemas; no reset.

- Positive paths: SQLite internal case passed (16.01s); remaining
  `pytest -q tests/test_initial_rule_start.py -k 'configured or postgres' -x --durations=5`
  passed 3 (SQLite configured 19.46s, PostgreSQL internal 42.62s/configured 45.88s).
  Each asserts one automatic admission and native attempt, zero human approvals.
- Adverse cohort SQLite six passed before a PostgreSQL fixture exception-class mismatch.
  Corrected expected DBAPIError (SQLite IntegrityError / PostgreSQL ProgrammingError);
  `pytest -q tests/test_initial_rule_start.py -k 'postgres and (erased or session or expired or source or rollback or unknown)' -x --durations=5`
  then passed all six. Cases cover source/observation erasure, original session revocation,
  explicit expiry, transaction failure after real origin consumption (rollback of admission
  and origin), unknown response, Stop and historical reconciliation without a second send.
  Erasure checks nullable link; altered preview digest and raw link mutation are denied.
- `pytest -q tests/test_initial_start_migration.py tests/test_initial_start_contracts.py`
  passed 3 (actual SQLite/PostgreSQL round-trip and exact contract); one existing Alembic
  path-separator deprecation warning.
- Ruff and repository `mypy` passed (933 source files); `git diff --check` passed.
- Final post-guard erasure verification is recorded in the following checkpoint.

## Performance evidence and remaining acceptance

Positive flow explicitly pins a **fixture-only** 120-second native observation/preview
policy before invoking the actual producer. It changes no production default/lifetime.
The ordinary 30-second profile correctly expired before provider emission in PostgreSQL.
Retained profile log: `/workspace/inlet-evidence/20261007/initial-start/pg-30second-profile-failure.log`.
One measured worker reached processing at 0.09s, review at 4.39s (7,638 queries), admission
at 6.25s (11,034 queries), claim at 12.80s (23,440 queries), execute at 21.36s (39,182 queries),
and failed the expired-preview guard afterwards. This is a material performance gap;
functional success under the explicit fixture is **not usable-latency qualification**.
Independent source-only factoring will reduce nested full calibration reconstruction,
retaining current source/dependency/session/expiry checks.

Pending: initial UI/actual HTTPS browser flow; explicit concurrent Start/admission race;
standalone 30-second expiry regression; configured-worker maintenance entry point; broader
existing automation compatibility; independent review and root integration. No initial
package Full run or live/purchasable completion claimed.

Final backend checkpoint: `pytest -q tests/test_initial_rule_start.py -k erased -x`
passed both databases after the protected delete guard and exact policy-to-linked-work
check. This includes raw update/delete refusal, genuine evidence deletion paired SET NULL,
blocked worker, zero admissions/attempts/approvals and successful owner Stop/read.
Final Ruff, mypy (933 files) and diff checks passed.

## Initial customer UI checkpoint

Source factoring `144786f` was independently inspected and integrated as `8948b64`:
private freshly validated calibration inputs remain confined to locked database reads;
public readers and the post-mandate second preview validation remain guarded. No cached
permission crosses requests, commits or provider I/O. Its separate ledger records 50
source/compatibility checks and the measurement method.

The actual Initial Planning page now reads separately scoped initial choices and displays
the exact preview, named rule, separately consented execution plan, total limit, maximum
nominal adjustment, environment, duration and cadence. Confirmation starts unchecked.
The strict request includes exact preview/policy digests and the original consent binding.
Input/workspace/session changes clear pending consent. Recent-run status and Stop remain
available after the preview is cleared. An unavailable Start response clears confirmation;
recovery reads the original run without retrying Start. Existing manual review remains.

Checks on this checkpoint (same isolated-database environment above):

- `pytest -q tests/test_initial_automatic_browser.py --durations=8`: **4 passed**,
  real HTTPS/Chromium, SQLite and PostgreSQL, normal and lost-after-commit Start response.
  Uses actual capture/calibration/native preview, configured options/API/worker, owned
  original session and MockHTTP provider. Each asserts exactly one Start request, one
  native budget POST, one admission/attempt/reservation, verified target receipt, zero
  human approvals, status read, Stop, recovery history and logout. PostgreSQL whole-test
  calls 35.77s/33.94s; SQLite 14.33s/14.89s. These are not worker-only timings.
- `pytest -q tests/test_initial_automation_ui.py tests/test_initial_execution_ui.py`:
  **4 passed**. DOM contracts include late stale options, same-owner session rotation,
  uncertain response without automatic retry, recovery and Stop, existing V1/V2 handoff.
- `pytest -q tests/test_initial_rule_start.py -k expired30`: **2 passed**.
  Actual producer uses the ordinary 30-second native observation lifetime; moving the
  injected authority clock forward 31 seconds denies Start, with zero sessions,
  admissions, attempts, approvals or sends. No clock rollback or production change.
- `ruff check app tests`, repository `mypy` (**936 files**), Node syntax checks for both
  initial modules and `git diff --check` passed. Three initial line-length lint errors
  were fixed before this checkpoint; the first lost-response harness attempt omitted
  placeholder replacement, corrected before the four-case successful run.

Worker-only independent source measurements use `perf_counter` around `worker.advance`,
with identical SQL counters: three runs 22.204/21.272/20.503 seconds (median21.272),
including profiling overhead and concurrent root validation load. This remains a material
latency limitation and does not qualify the ordinary 30-second happy path. The 120-second
positive fixture is explicit, not a changed production policy.

Pending independent concurrency/stale-consent/spent-budget/populated-downgrade/maintenance
checks, existing-page browser compatibility, further reviewed source optimization, and
root review/integration. No Full, deployment, live provider action or product release.

Post-freeze compatibility on `9e3ea5a`:

- `pytest -q tests/test_initial_budget_mandate_browser.py tests/test_v2_execution_browser.py -k False --durations=4`:
  **4 passed**, actual successful SQLite/PostgreSQL initial budget and manual review
  browser journeys after the new module import. Whole PostgreSQL calls 6.06s/11.84s.
- `pytest -q tests/test_session_automation.py::test_start_to_actual_provider_effect_with_zero_human_approvals tests/test_reported_rule_automatic.py -k 'start_to_actual or True-none' --durations=4`:
  **8 passed**, existing Google/Meta/TikTok session automatic execution and reported-rule
  automatic positive path on both databases. Offline MockHTTP only.
- Parent independently reviewed `9e3ea5a` UI and host-page integration: no concrete P1/P2;
  independently ran Node syntax and initial automation DOM successfully. Backend
  concurrency/financial acceptance and latency qualification remain separately tracked.
