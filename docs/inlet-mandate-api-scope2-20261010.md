# Current Mandate API Scope Two-Failure Qualification

The shared offline seed keeps approval as its default. The existing API access test
now explicitly requests genuine current unapproved drafts in its two workspaces.
Every original request, response assertion and role loop remains current and exact;
added final checks require draft state, null approval, zero counters and no actions.
Production services and advertising-write guards remain unchanged.

Evidence: `/workspace/inlet-evidence/20261010/mandate-api-scope2/`.
Final command/result are in result.json: entire test_mandates plus both execution and
provider transport boundary files,104 passed,0 failures/errors/skips,20.114s. This
includes current access2 and16 unchanged shared-seed simulation regressions, plus86
current default write-boundary tests. The first command referenced a nonexistent
boundary filename and exited4 before execution; its logs/XML are retained separately.
No assertion failed and no production guard was patched by this repair.

Whole Ruff, configured bare mypy1246 and diff checks pass. source-proof.json records
original current test body equality except the two explicit draft seed arguments
and appended checks/client close; every other test function is AST unchanged. The
seed differs only by its default-true keyword and conditional around the original
approval call. No historical child or registry entry was added.

Credit only the two original API identities. Offline role/isolation evidence does
not establish live deployment or advertising authority. Aggregate/hosted/push hold
continues, and all product readiness gates remain open.
