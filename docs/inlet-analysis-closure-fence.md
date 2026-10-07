# Analysis Closure Fence

Package branch: `codex/inlet-analysis-closure-fence`, based on integrated foundation
`915fbcc10151e56f7b28d2a1ae5f643c99503007`. This is offline implementation evidence;
no live workers, providers, deployment, purge or accounting release were exercised.

The customer closure transaction and analysis mutations share a refreshed workspace
`FOR NO KEY UPDATE` lock, acquired before owned product locks. Analysis admission
rejects missing or inactive workspaces without a default tenant. A durable run claim
releases its first transaction, so execution reacquires the workspace lock before
producing any local outputs and holds it through success persistence. Direct success
repository calls also require active workspace authority. Closure that wins the
claim-to-execution gap permits only the existing sanitized failed-run receipt.

Historical analysis rows remain readable. A running row does not prove that a worker
has terminated; no old rows are relabeled by timeout, and no publication reservations
are released. This repair therefore does not complete customer closure or resolve
external grant, billing, publication uncertainty or retention/disposition obligations.

## Verification

The corrected baseline produced six assertion failures: selected-before-closure
admission, closure after durable claim, and direct success persistence, each on SQLite
and PostgreSQL. The first fixture draft used an invalid POST_SYNC scope; those earlier
constraint failures are explicitly not product reproduction evidence.

- Baseline: `/tmp/inlet-analysis-closure-before-corrected.log`, six failures in 5.24s.
- Fixed suite: `pytest tests/test_analysis_closure_fence.py tests/test_customer_quiescing.py tests/test_analysis_cadences.py -o addopts='' -q`,
  **45 passed, one SQLite-only row-lock skip** in 18.94s.
- The PostgreSQL test pauses real local analysis and verifies actual customer closure
  waits until its success commit, with workspace NO KEY UPDATE as the first lock.
- Missing workspace rejection and another active workspace's successful analysis are
  covered. Existing cadence/idempotency/retry and customer closure tests remain green.
- Ruff `app tests` passed; mypy passed (404 source files).
- No Full suite run in this package; integrated Full remains the parent's release gate.

## Remaining Local Drain Design

The local closure fence can be verified independently of physical worker termination.
A future reconciliation operation must inspect scoped run/checkpoint/attempt evidence
under the same workspace-first lock, bind its receipt to the closure request revision,
and distinguish admission fenced from observed local work drained. Pending/running
legacy JobRun, AnalysisRun and CRM runs have no authoritative termination lease; mere
age must not establish drain. Unknown production attempts and held reservations remain
protected accounting and cannot be cleared by this reconciliation. No new drain state
transition or retention policy is introduced by this package.
