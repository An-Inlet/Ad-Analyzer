# Session Automation API History Under Planning Policy

Base: `0e44282`. Changes only `tests/test_session_automation_api.py` and this ledger.
Both tests are explicitly `planning_boundary`; no retained-execution fixture or
module-wide capability override is introduced.

The existing actual Start/worker journey creates authentic historical records in
a bounded setup context: original mandate/consent fixture, real customer login,
Start CSRF/ownership checks, actual Start and worker, and one Google MockHTTP write.
Both temporary capability overrides end before current history, foreign access,
logout, and fresh-session Stop assertions. The shared fixture is unchanged; no
consent or approval records are fabricated. The original zero-human-approval check
remains, because the retained automatic journey operates within its actual mandate.

After the guard is restored, owned history excludes session digests and is no-store.
A configured historical runtime still reports no available policies or mandates.
Another Start receives the exact planning-policy 409; direct worker advance raises
the write-disabled exception. Run count and provider writes stay unchanged. Stop
remains a safe revocation action: missing CSRF, unrelated owner, and logged-out
requests fail; a newly authenticated owner can read the blocked original-session
run and Stop it. Stopped-by attribution persists, with no additional provider write.

The default-runtime test also uses only setup-time historical authority and asserts
the unconditional guard is restored before reading unavailable capabilities. No
production route, worker, authority, schema, or feature behavior changed.

## Checks Actually Run

With the approved disposable PostgreSQL URL and isolated fixture schemas:

```text
pytest -q tests/test_session_automation_api.py --maxfail=1 --junitxml=/tmp/session-api-partition.xml
```

**4 passed, zero skipped/failures, 16.982 seconds** (JUnit elapsed), SQLite and
PostgreSQL. Separate minimal default capability/boundary regression:

```text
pytest -q tests/test_advertising_capabilities.py tests/test_planning_execution_boundary.py --junitxml=/tmp/session-api-boundary.xml
```

**39 passed, zero skipped/failures, 0.709 seconds**. Whole `ruff check .`, prescribed
`mypy` (**1071 source files**), and `git diff --check` passed. No runtime test failure
or production defect was found. Ruff formatting corrected indentation-related line
length before checks completed.

Raw logs/JUnit: `/workspace/inlet-evidence/20261008/session-api-partition/`.
This is bounded offline regression preparation. No Full, live provider, remote,
hosted, merge or deployment action occurred. Remaining partitions and the eventual
single aggregate qualification are separate.
