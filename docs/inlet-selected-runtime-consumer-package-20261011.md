# Private selected-v4 consuming runtime — 2026-10-11

Lane A implementation based on reviewed root `4cd8fb1`, with reviewed Lane B
`8f80d6a` locally cherry-picked as `7003dc4`. Lane B owns retained-source dispatch;
this commit changes only generation ports, policy capabilities, service, repository,
focused tests and this ledger. No migration, public default switch, environment
flag, native writes, live provider access, hosted run or Full aggregate.

## Runtime behavior

- `GenerationEvidence` includes the distinct `SelectedPairedEvidenceV1`.
- The closed capability registry recognizes only the canonical v4 pair/digest as
  `selected_requested_window` / `local_reporting_v3`; old pairs remain unchanged.
- `PlanningDocumentService(..., policy=...)` accepts an explicit internal canonical
  policy. Omission remains canonical v3. The ordinary API factory is unchanged.
  Tests inject only this constructor policy; real auth, source collection,
  composition, SQL witnesses, input routes and persistence still execute.
- v4 input save/generation requires explicit selectors, including meaningful empty
  selection. Legacy pairs still reject any non-None selectors. Unknown capture IDs
  fail with a fixed 409; no latest-capture fallback or missing-data substitution.
- Service dispatches the actual paired reader/composer and rechecks complete paired
  SQL evidence plus saved catalog receipts under original refreshed authority.
  Expected selected integrity ValueError/RetainedSourcesChanged becomes fixed409;
  HTTP authority errors are not converted to missing evidence.
- Repository checks exact candidate selected proof, all selected/catalog/context/
  commerce and traffic references, native targets and UTC deadlines. Final evidence
  expiry is checked again after flush, before final authority and commit. A late
  expiry rolls back the complete generation graph.
- Current retained witnesses use Lane B's separate dispatcher. Existing historical
  selected validation in repository/export remains intact; this package does not
  replace historical integrity with currentness.

## Genuine API fixture for dependent qualification

`tests/test_selected_runtime_api.py::configured(engine, configuration, replicas,
monkeypatch, *, value="10", family="conversions")` returns
`(f, root, body, native_calls, reader)`. It uses `prepared_range_plan`: actual
61-day range API, owned event options/confirmation, selected capture and real
native MockHTTP. `create(f, root, body)` uses the actual public input-save route;
`generation()` supplies a bounded generation intent. Only private policy selection
and low-level external HTTP/identity fixtures are injected. No positive evidence,
collector, composer, source witness, execution record or public input receipt is
fabricated. The helper supports subsequent actual TLS/history/archive tests;
those dependent qualifications are not claimed here.

## Verification and evidence

Durable logs/JUnit: `/workspace/inlet-evidence/20261011/selected-runtime-consumer`.

- `pure01`: 19 passed, 2.53s: constructor/selector contracts.
- `legacy-pure`: 119 passed, 13.46s: paired composition plus legacy plan/ports/
  input canonical behavior.
- `sqlite-positive`: actual public input→v4 generation→current read→manual
  decision→idempotent replay passed, 9.47s.
- `api01`: 31 passed, zero skipped, 232.23s, SQLite and PostgreSQL. Both conversion
  families and positive/zero/missing observations; current read and replay without
  another provider read; original session revocation, deleted range receipt,
  changed candidate proof/reference, authenticated cross-workspace and CSRF denials,
  explicit empty and nonexistent selectors. No execution runs or attempts created.
- `regression01`: 14 passed, 14 deselected, zero skipped, 58.47s. Added late-flush
  expiry tests, actual default-v3 positive generation, unknown/mixed/sibling dispatch
  refusal, and existing legacy-selector input API behavior.
- `atomic-final`: 10 passed, zero skipped, 64.63s after strengthening atomic
  assertions: no version, dependency, generate receipt or head advance on all five
  failure modes, both databases. This includes DB-clock expiry after actual flush.
- Whole `ruff check .` passed (`ruff-final4.log`). Whole mypy passed, 1360 source
  files (`mypy-final4.log`), cache in scratch. Standalone imports and diff check pass.

Tests use `/workspace/inlet-venv/bin`, unique `/tmp/selected-runtime-*` basetemps,
`--junitxml=<durable-run>/junit.xml --durations=20`. PostgreSQL used the existing
local disposable `inlet_candidate_migration_ci` database with explicit disposable
marker and fixture-created isolated schemas, never reset/dropped the database or
used a root qualification database. PG lane released after the last test.

## Retained failures and corrections

`sqlite-denials` selected zero tests due an overbroad `not empty` filter; it is not
counted as qualification. `sqlite-denials2` had one fixture failure: Bob was not
logged in, producing401 before ownership. Explicit ordinary outsider login then
proved exact404 (`sqlite-foreign`). `sqlite-missing` reproduced an actual new
consumer error boundary: missing capture raised SelectedReportingUnavailable out
of collection. The selected service branch now returns fixed409 while preserving
authority failures; `sqlite-missing2` passed. Static draft logs retain test import/
typing errors; final whole checks passed without exemptions. No failure logs were
removed or overwritten.

## Remaining obligations

Canonical v3 remains the deployed default. Root's capability/UI, actual selected
TLS journey, and dependent historical/archive/erasure qualification remain separate
packages. No production release or default-policy activation is asserted.
