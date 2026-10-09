# W1 Follow-up: Current Route And Portal Contracts

Isolated branch `codex/inlet-w1-current-shell-contract`, base `e1954f0`.
Authorized package1 only; tests and this ledger change, no production behavior.

Frozen W1 `6a3b0f1` had four relevant failures:
`test_route_boundaries::test_every_assembled_route_has_an_explicit_boundary` and
all three paths of
`test_customer_portal::test_customer_shell_has_strict_headers_and_no_inline_code`.
Their original traces remain in
`/workspace/inlet-evidence/20261008/w1-aggregate/aggregate.xml`, SHA256
`e3263f5e2bca0d484b4657d6672a32dfdc44539ee1cbed8257bf1a7187488037`.
The exhaustive external classification remains unchanged at
`/workspace/inlet-evidence/20261009/w1-failure-classification/`; this package does
not reclassify the frozen run as passing.

## Exact Repair

- Add only `GET /app/planning` to the explicit public-shell inventory. The actual
  `app/portal/router.py::customer_planning_documents` returns inert
  `planning.html`; customer data/mutations remain on authenticated customer APIs.
  The exhaustive assembled-route walk, dependency checks, signed ingress,
  operator/dashboard/worker boundaries and observed-route completeness remain.
- Replace the removed exact sentence “Live advertising execution is disabled”
  with the actual stronger shell statement “Inlet cannot publish, activate,
  pause or change advertising.” Also require the current nonproduction-purchase
  qualification. Retain every no-store/CSP/referrer/token/no-inline-code check.

No retired controls were restored, route prefix was broadly allowlisted, security
assertion removed, advertising guard patched, or shared fixture changed. The
other portal tests still exercise assets/path separation, safe JavaScript
contracts and the actual local Chromium DOM journey. The route module still
runs current customer-session rejection across all operator/worker routes on
SQLite/PostgreSQL in all four existing configuration modes.

## Checks

Using the existing nonaggregate disposable PostgreSQL fixture environment:

```sh
/workspace/inlet-venv/bin/pytest -q tests/test_route_boundaries.py tests/test_customer_portal.py \
  --junitxml=/workspace/inlet-evidence/20261009/w1-current-shell-contract/focused.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

No Full, hosted run, live provider call, frozen checkout/database edit, migration
or aggregate rerun occurred. This is successor qualification of four identified
stale expectations, not a fix or pass claim for the remaining W1 failures.

Final focused result: **20 passed, 0 skipped, 20.578 seconds**.
Raw output and JUnit are retained as `focused.log` and `focused.xml` beneath
`/workspace/inlet-evidence/20261009/w1-current-shell-contract/`.
Whole Ruff passed; bare mypy passed all1125 source files; diff check passed.
No failed successor run occurred. This is the full two-module focused result,
not merely the four previously failing parametrizations.
