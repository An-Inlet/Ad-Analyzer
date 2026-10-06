# B19 Runtime Observations

Branch: `codex/inlet-runtime-observations`; base `06dab9a`. Contracts frozen at
`0fcf7bc` before binding runtime consumers. Migration `20261006_0070` branches
from `20261006_0060`; the integration owner supplies the final merge revision.

The actual scheduler loop and private-media factory/read/write paths now emit
fixed observations. The opt-in setting `OPERATIONAL_OBSERVATIONS_ENABLED` defaults
to false. The production sink is PostgreSQL only and constructs its separate pool
without opening a socket. No storage probe, retry, advertising request or scheduler
recovery is introduced.

The table has exactly three allowed components and three slots per component:
latest start, completion and failure. Its composite key and check constraints cap
storage at nine global rows. Each row contains fixed enums, timestamps, a saturating
occurrence counter and (scheduler only) an internal random process epoch. No
workspace, customer, object key, provider identifier, exception text, payload,
credential or stack trace is recorded. Model registration and lifecycle policy
classify these records as global operational data, excluded from customer exports.
The table does not match the lifecycle worker-family suffixes and grants no work
or deletion authority.

The recorder uses an independent transaction and fixed advisory lock, never
customer or provider locks. PostgreSQL statements time out after 250ms and lock
waits after 200ms; the dedicated pool waits at most 250ms and initial connections
have a one-second connection timeout. Failures roll back only that transaction and
produce a fixed sanitized warning. No retry occurs. Tests use the same PostgreSQL
recorder and SQLite's serialized transaction for local coverage; the runtime
factory does not install a SQLite sink.

Scheduler start is emitted immediately before an actual cycle. Completion means
that the cycle and subsequent independent tick invocations returned without an
observed exception or explicit failed stage. It does **not** mean every account
imported, data is fresh, providers are healthy or the process remains alive.
Independent customer-runtime stages reporting `failed` are distinguished from
cycle invocation failures. Failure records persist separately from later progress.
An older scheduler epoch cannot overwrite a newer observed epoch. Timestamps
assume the application's clock; they never prove a worker terminated or authorize
replay. Missing scheduler deployment and never-started work without a persisted
obligation remain unobserved.

The existing authenticated, no-cache operator attention response adds at most nine
sanitized observations via one bounded query under its existing PostgreSQL timeout.
No epoch is exposed. Empty means `unobserved`, never healthy. Fixed incomplete-
storage and non-liveness caveats remain even when observations exist. Latest
failure slots are not an exhaustive error history; a later read does not prove
write recovery. External alert destination and delivery remain a separate live gate.

Private-media wrappers call the existing Local/GCS implementation exactly once.
The existing GCS preconditions, private-policy checks, bounded reads and no-retry
behavior remain authoritative. Intentionally disabled storage is not reported as
an initialization failure. Enabled but unavailable storage is recorded, and its
original sanitized exception behavior is preserved even if telemetry fails.

## Verification

- Combined contract, recorder, actual migration, Attention, GCS, customer scheduler,
  model registry, customer lifecycle and scheduler reliability suite: **287 passed,
  3 expected SQLite skips**, 3 existing Alembic configuration deprecation warnings.
- After adding the actual PostgreSQL telemetry-lock-timeout/customer-commit and
  all-nine-slots regressions: recorder suite **19 passed, 2 expected SQLite skips**.
- After preserving lazy scheduler imports behind sanitized startup: recorder,
  customer scheduler and scheduler reliability suites **205 passed, 2 expected
  SQLite skips**. Separate clean-process import regression **1 passed**.
- `ruff check .`, `mypy` (**568 source files**) and `git diff --check`: passed.

The initial new GCS test expected four bucket checks; the existing implementation
correctly performs five for initialization, upload verification and the subsequent
read. The wrapper issues no additional calls; the test now asserts the actual
existing contract. A transient exec transport disconnect interrupted a status read,
not tests; one bounded harmless retry recovered the completed logs.

Logs: `/tmp/inlet-runtime-observations-tests2.log`,
`/tmp/inlet-runtime-observations-final.log`,
`/tmp/inlet-runtime-observations-last.log`.

No Full run, live provider or storage call, deployment or advertising mutation was
performed. Default-disabled instrumentation and migration require release review;
no operational alert delivery or live qualification is claimed.
