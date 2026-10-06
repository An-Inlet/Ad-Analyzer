# Customer Analysis Session Repair

PR147's new workspace guard exposed a preexisting cross-session design in
`jobs.customer_runtime._analyze`: the caller held workspace authority while
`run_post_sync_analysis` opened a second session that now needed the same lock.
Actual PostgreSQL observation showed the second backend waiting on its caller.
The original interrupted runtime test was not a passing check; its orphan pytest
child was explicitly terminated.

The cadence entrypoint can now borrow the existing Session. It passes a scoped
revalidation callback to the analysis service, which runs after the durable claim
commit and after reacquiring workspace authority. Customer runtime refreshes the
source job, active native connection/integration, account ownership, analysis controls,
and fresh paid entitlement before producing outputs. Closure/revocation in the
commit gap yields only a sanitized failed-run receipt. It does not release authority
and trust a stale pre-claim check.

Validation:

- Existing customer runtime/cadence/analysis-closure suite:63 passed,1 SQLite-only
  row-lock skip,23.49s; PostgreSQL statement timeout15s bounds accidental waits.
- New direct customer runtime and three post-claim races:8 passed,5.25s across
  SQLite and PostgreSQL. Healthy PostgreSQL execution uses statement timeout5s,
  so the original self-deadlock becomes a bounded failure.
- Race changes use actual closure and persisted source/billing state; no provider
  calls. A rejected initial fixture price did not satisfy the existing price_ schema;
  its setup failures are not counted as product evidence.
- Ruff app/tests and mypy408 source files pass. Integrated Full pending.

This package is independent of the later local closure observation/queue/UI work.
It does not claim physical worker termination, deployment or external cancellation.
