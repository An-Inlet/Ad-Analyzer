# Initial reported-rule central worker checkpoint

This component composes the existing initial reported-rule source with the
candidate worker, exact review bridge and strict export parser. It does not yet
expose initial automatic Start or grant automatic admission. The separate Start
binding proposal is `docs/design/initial-rule-start-binding-interface.md`.

The strict document unions retain the initial, repeat reported-rule and legacy
learning discriminators. Existing serialized documents and hashes are unchanged.
Generic target selection rejects an initial policy without its explicit preview
basis. The worker uses the original customer principal, current source and policy,
the actual native read, and the complete 0084 dependency relation. It rechecks
source, session, lease, document and expiry before publishing a candidate result.

An exact prepared review is not an exemption to the initial no-prior-admission
rule. Before an admission exists, the central bridge passes no forward exception.
After an admission exists, only the protected review binding can reach the
source's full consumed-origin verification. Request data cannot supply this
exception. Initial decisions are explicitly rejected by automatic admission until
the separate initial authority and Start binding are implemented.

## Evidence

The genuine configured initial fixture uses current V2 preview, calibration,
separate 0080 consent and native MockHTTP. It does not seed candidate jobs,
execution attempts, reservations or receipts. The central test calls enqueue,
worker processing, result read and exact review preparation. Session revocation
and underlying observation deletion then deny the review guard. No execution
attempt or reservation is created by this component.

Local disposable SQLite and PostgreSQL checks:

- `tests/test_initial_rule_worker.py tests/test_reported_rule_worker.py`: 14 passed;
  log `/tmp/inlet-initial-central-actual.log`, slowest PostgreSQL initial
  observation-erasure case 14.81 seconds.
- `tests/test_initial_rule_dispatch.py tests/test_initial_rule_candidates.py
  tests/test_reported_rule_candidates.py`: 25 passed; log
  `/tmp/inlet-initial-dispatch.log`.
- Actual stored initial job/result export checks, rerunning the two current-source
  worker cases: 2 passed; `/tmp/inlet-initial-central-export.log`, PostgreSQL
  15.84 seconds and SQLite 6.11 seconds.
- Whole Ruff, mypy (923 files) and diff check passed. The final export-test loop
  initially produced a mypy common-base `id` error; selecting the same table's
  `c.id` corrected the test typing without changing application behavior.

Initial source/0084 lineage fixes through `366f267` are included: creation and
activation history do not masquerade as a previous budget decision; unresolved
financial obligations remain independent blockers. No production policy or
financial source is registered. No Full, remote, hosted or live action was run.
