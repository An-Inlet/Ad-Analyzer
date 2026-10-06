# Final Emission Context Authorization

Base: `c602a1b`, isolated branch `codex/inlet-emission-context-fence`.

Creation, activation and optimization previously evaluated the runtime credential
context callback after the final authority check and durable emitting commit. A
blocking callback could return after session revocation or qualification expiry,
then emit a provider write without reacquiring current authority.

Resolve emission context before the final workspace/session/claim check and reuse
that exact context for apply_once. Creation verifies the original owned dispatch
claim both before credential lookup and after it, releasing product locks during
lookup. Activation resolves after graph preflight; optimization resolves after
provider validation. Existing late response/receipt lanes and retained reservations
are unchanged. This does not claim physical cancellation after emission, solve
provider compare-and-swap, or qualify a mock profile as production exposure proof.

Baseline evidence:
- Six optimization failures: Google/Meta/TikTok on SQLite/PostgreSQL, session revoked
  during the third execution context lookup, then execute returned rather than401.
- Two activation failures: revoke during context resolution after real graph preflight.
- Two corrected creation failures: revoke during emission context resolution.
- Initial creation test used the wrong claim method; those two AttributeErrors were
  fixture failures, not product evidence. Corrected baseline in separate untouched
  c602a1b checkout reproduced DID NOT RAISE on both databases.

Logs: `/tmp/inlet-context-before.log`,
`/tmp/inlet-context-activation-before.log`,
`/tmp/inlet-context-creation-before-corrected.log`.

Fixed checks include actual session revocation with mocked provider HTTP and expiry
advancing ten minutes during context resolution for all optimization platforms;
assertions require no writes. Forged creation attempt lineage is rejected before
credential resolution. Final results and PR are reported with the delivery commit.
Full and hosted CI remain parent-coordinated; no live calls, deployment or merge.

Validation: combined authority/creation/activation/optimization suites91passed,
1SQLite-only skip in126.56s. After final creation guard factoring and forged-claim
assertions, authority+creation rerun43passed,1SQLite-only skip in57.62s.
Ruff app/tests, configured mypy466files and git diffcheck passed.
Logs `/tmp/inlet-context-combined-final.log`, `/tmp/inlet-context-final-claim.log`,
`/tmp/inlet-context-mypy-final.log`. An earlier mixed run had83passed,1skip and
two fixture AttributeErrors; it is not counted as a successful run.
