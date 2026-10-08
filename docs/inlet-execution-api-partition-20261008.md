# Customer Execution API Regression Partition

Base: `8b9d932`. This package changes only the mixed historical execution API
regression module and this ledger. Production advertising writes remain disabled.

Four historical test functions (five parameterized cases per database) explicitly
opt into the existing non-autouse, function-scoped `retained_execution_engine`
fixture and `retained_execution` marker. They retain actual consent, approval,
MockHTTP dispatch, receipt, unknown/no-replay, original-session revocation during
read IO, and admitted-dispatch logout assertions. The shared `setup_api` helper
and fixture implementation remain unchanged. No consent or approval rows are
fabricated, and no new blanket fixture, skip, or production switch is introduced.

Two current-product `planning_boundary` functions use a setup-only patch to create
authentic historical records, then assert that the default capability guard has
been restored before testing customer routes. The existing default-runtime case
now checks exact policy-denial details for ordinary and forged live-environment
requests. The route dependency deliberately returns 409 before body validation;
the historical enabled test separately retains the forged-body 422 assertion.

The added current-product case seeds one genuine coordinator MockHTTP dispatch,
then restores default policy. With a configured historical runtime still injected,
the owner can read the run, review, and verified receipt; another customer cannot;
logout revokes access. Receipt scope denial is the existing 404 from lifecycle
receipt authorization, while run/review denial is 403. Capability status stays
unavailable; mandate, review, approval, start, and advance requests receive the
exact planning-policy 409. All six execution-table row counts and the one historical
provider-post count remain unchanged by these requests.

## Checks Actually Run

Final focused command, with the approved disposable PostgreSQL URL and isolated
fixture schemas:

```text
pytest -q tests/test_customer_execution_api.py tests/test_advertising_capabilities.py tests/test_planning_execution_boundary.py --junitxml=/tmp/execution-api-partition-final.xml
```

**53 passed, zero skipped, zero failures, 29.352 seconds** (JUnit elapsed), including
all 14 customer API cases across SQLite and PostgreSQL. The unpatched boundary
suites ran after the mixed module and passed. Whole-repository `ruff check .`,
prescribed `mypy` (1067 source files), and `git diff --check` passed.

Initial diagnostic runs confirmed the new policy's 409-before-422 ordering and the
existing receipt outsider 404; the final assertions reflect those concrete routes.
The first full module run passed all 12 pre-existing cases; only the new receipt
outsider-status assumption failed before correction.

Raw final log and JUnit:
`/workspace/inlet-evidence/20261008/execution-api-partition/`.
No production defect or production source change was needed. This is local offline
regression preparation, not full-suite, live, or production qualification. Other
historical API/UI partitions and the eventual single aggregate remain separate.
