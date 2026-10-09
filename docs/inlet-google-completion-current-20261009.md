# Current Google Completion Privacy And Source Regressions

Approved interface: `3f778e6`,
`docs/design/google-completion-current-source-v1.md`. Implementation uses isolated
base `a9a7681`, with exactly fourteen current original failures targeted.

A fixed original producer calls untouched pinned `emitted` from `2155ff3`. A
scoped record-only wrapper delegates to the original `ready`, returns its exact
tuple unchanged and retains the actual GoogleServer solely to measure its one
MockHTTP mutation. No current advertising capability, sink, response or financial
coordinator is bypassed. All current original readers, serializer, malformed
payload checks, idempotent capture, closure and protected inventory assertions
remain in the parent. Only thirteen bounded scalar IDs/commitments/counts cross
the child boundary.

The parent validates original request, response, receipt, mandate/consent/ledger,
held reservation and completion using current code. It snapshots every provider
row plus mandate_actions, optimization preparations and original completions.
Five corruption branches allow only the exact original committed field/path
change. The no-tamper branch permits no delta, including original timestamp and
response rows after actual current idempotent record_response. Closure permits
only the observed current mandate revocation, original run cancellation/time and
mandate-action cancellation fields; original attempts, responses, receipts, holds
and completion stay exact. This does not pretend closure releases exposure.

Parent and child require fresh owned schemas, explicit local disposable
PostgreSQL with exact schema/URL validation, or a new evidence-local SQLite file.
No child DDL or schema bootstrap exception was needed. SourceLifetime removes
only the verified reaped source extraction; retained evidence and databases are
outside it. The shared emitted helper, native restore tests and previously closed
legacy acknowledgment/capture cases remain unchanged.

## Evidence

Durable root: `/workspace/inlet-evidence/20261009/google-completion14/`.

- Initial SQLite no-tamper reader and PostgreSQL closure probes: **2 passed**, no
  skips/failures/errors, 44.576 seconds (`probe.xml`). Closure transformations
  matched the approved narrow expected graph without exemptions.
- `assertion-proof.json`: all original assertions remain AST-identical (13 reader,
  6 closure), original decorators remain, every other function in the consumer
  module including emitted is AST-identical.
- Initial mypy reported two fixture/implicit-export typing findings. Explicit
  `Any` casts at existing fixture/module boundaries fixed both without changing
  behavior. Whole bare mypy then passed, 1207 source files (`mypy-final.log`).
- Initial manual formatting found long lines; formatter fixed these before the
  probes. The later cast-only repair lengthened one line and final Ruff correctly
  reported E501 (`ruff-final.log`); its formatting-only repair follows the bounded
  cohort, with its own final Ruff log. No false static success is inferred from
  another command's exit status.

Exact bounded command selections, with disposable test environment and
evidence-local basetemp/JUnit paths:

```text
pytest -q 'tests/test_google_completion_evidence.py::test_durable_reader_and_export_never_release_hold[sqlite-None]' 'tests/test_google_completion_evidence.py::test_customer_closure_retains_original_completion_and_financial_hold[postgres]'
pytest -q tests/test_google_completion_evidence.py::test_durable_reader_and_export_never_release_hold tests/test_google_completion_evidence.py::test_customer_closure_retains_original_completion_and_financial_hold tests/test_planning_execution_boundary.py tests/test_planning_provider_transport_boundary.py tests/test_producer_source_lifetime.py
ruff check .
mypy
```

No historical assertion partition expansion, aggregate rerun, W1 mutation,
external provider access or live advertising change occurred. This package
qualifies current protected-evidence behavior using authentic historical rows;
it does not establish financial finality or live product readiness.

## Final Qualification

The final bounded cohort passed **116 tests**, no skips/failures/errors, in
133.412 seconds (`qualified.xml`): fourteen current original failures,
86 unchanged default boundary tests and sixteen SourceLifetime tests. All five
committed tamper forms and the exact closure transformations passed on both
SQLite and PostgreSQL. All fourteen source copies were verified removed after
reap (238,546,694 logical bytes); unique logs, scalar IDs and file
databases remain.

Final source differs from that tested cohort only by formatting the long driver
call after it completed. Whole Ruff passed (`ruff-qualified.log`); whole bare
mypy passed, 1207 source files (`mypy-qualified.log`); `git diff --check` passed. The existing own
mypy cache was moved intact to `/tmp/inlet-google-completion14-mypy-cache` to
follow shared workspace capacity guidance; no original evidence/cache was deleted.

## Independent-Review SQLite Guard Repair

Review of `49527e6` found that SQLite aliases were resolved rather than rejected,
and parent DDL preceded full owned-file validation. The successor fixes both
parent and child before database factory/access: exactly plain `sqlite`, no query,
username/password/host/port, exact absolute `current.sqlite`, regular nonsymlink
file, every ancestor nonsymlink, and no normalized path alias. Parent rejects an
artifact-directory alias before directory creation, creates a new file exclusively
with `xb`, then validates it before engine creation and DDL. The fixed child
validates the unresolved output-parent spelling rather than resolving symlinks.
PostgreSQL and source/financial semantics are unchanged.

- Pure parent/child guards: **34 passed**, 2.567 seconds (`guards-final.xml`).
  Initial two failures (`guards.xml`) were negative-test construction errors:
  SQLAlchemy omits a password-only URL when no username is supplied. The repaired
  negative retains both fields. No guard was weakened.
- Representative actual SQLite no-tamper reader plus PostgreSQL closure:
  **2 passed**, no skips/failures/errors, 22.414 seconds (`guard-db.xml`).
- Whole Ruff and bare mypy passed (1208 source files), separately recorded in
  `ruff-guards-final.log` and `mypy-guards-final.log`; diff check passed.
- The earlier 116-case `49527e6` evidence remains distinct and unchanged. No full
  fourteen-case repeat was needed for this storage-guard-only successor.
