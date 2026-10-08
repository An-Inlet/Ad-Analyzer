# Customer Optimization API Regression Partition

Base: `66019e5`. Only `tests/test_customer_optimization_api.py` and this ledger
change. Production advertising capability, schemas, shared setup helpers, and
fixtures remain unchanged.

Four historical functions explicitly opt into the existing function-scoped,
non-autouse `retained_execution_engine` fixture and `retained_execution` marker.
Their original assertions remain intact: all-three-provider budget/pause and
repeat journeys, actual customer consent/approval and MockHTTP receipts,
original-session/role revocation during reads, forged/stale choices, shared
consent topology changes, and unsupported review rejection. No synthetic consent
or approval rows, blanket fixture, collection skip, or production bypass was added.

The existing owned account-choice/disconnected-source test is `planning_boundary`.
Only its genuine historical setup is temporarily enabled; the policy guard is
explicitly verified restored before current account-read assertions. The shared
`setup` and `bootstrap` functions are not modified or globally patched.

A new `planning_boundary` case covers each of Google Ads, Meta Ads, and TikTok Ads
with a configured historical runtime. After setup-only authority creation and
restoration of the default guard, owned semantic target reads remain available
and expressly not dispatch-qualified. Another customer cannot read target options
or historical mandates; logout revokes access. Runtime capability responses still
report writes, initial/repeat execution, and catalog capability unavailable.
Mandate creation/edit/consent and initial/repeat review requests receive the exact
planning-policy 409 before input validation. Five execution-table row counts stay
unchanged and actual MockHTTP mutation counts remain zero.

The new target-options outsider assertion uses the existing 404 from bound
workspace authority, whereas mandate-list access uses 403. The first diagnostic
run passed all 26 existing cases and found only this overly specific 403 assumption
in the new test; no production defect or behavior change was needed.

## Checks Actually Run

Approved disposable PostgreSQL environment; fixtures create isolated schemas:

```text
pytest -q tests/test_customer_optimization_api.py tests/test_advertising_capabilities.py tests/test_planning_execution_boundary.py --junitxml=/tmp/optimization-api-partition-final.xml
```

**71 passed, zero failures, zero skipped, 49.267 seconds** (JUnit elapsed), including
32 optimization API cases across SQLite and PostgreSQL. Default capability and
execution-boundary tests ran after the mixed module. Whole `ruff check .`, prescribed
`mypy` (**1069 source files**), and `git diff --check` passed.

Raw final log and JUnit:
`/workspace/inlet-evidence/20261008/optimization-api-partition/`.

This is bounded offline regression preparation. Export suites and other historical
partitions are unchanged; the eventual single aggregate remains separate. No Full,
live provider, hosted CI, remote, merge, or deployment action occurred.
