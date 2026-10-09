# Configured Candidate Current-Policy Regression Qualification

Approved interface: `docs/design/configured-candidate-current-session-v1.md`
(parent review of `9fa212e`). Implementation starts from `bf0d240`.

The fixed producer uses the verified `2155ff3` app/tests/scripts trees and the
original `configured_candidates_customer` for Google and Meta in four closed
modes. It stops before enqueue. Only bounded typed scalar IDs and commitments
cross the process boundary; the actual original optimization preparation,
consent, ledger and commerce publication remain in the owned database. Parent
code verifies the immutable preparation, policy/account/goal and manifest
bindings. Both processes enforce fresh owned storage; current DDL is unchanged.
The new closed SourceLifetime profile removes only verified reaped source trees,
retaining IDs, manifests, media, SQLite and logs outside the extraction.

Current composition performs an actual same-owner login, verifies its session is
new, and proves the actual queued job binds that session. It uses the original
controlled read-side qualification/observation callbacks, actual native MockHTTP,
current API, real customer tick and result serialization. No financial executor
or advertising sink is patched. Review and approval routes reject with the
current planning-only 409. Child and parent assertions prove zero provider writes,
reviews, approvals, runs, steps, attempts, receipts, responses and holds; only the
actual current candidate job/result is allowed after enqueue. Revocation before
and during the read retain the original result-suppression assertions.

Original successful scenario review/approval assertions remain byte-equivalent
at the AST level in the local renamed function and execute against the pinned
historical runtime. The new exact 16-node manifest adds a seventh batch: 349
unique historical child nodes, with explicit current coverage. No prior historical
batch was rerun. This is regression compatibility evidence, not live qualification.

## Evidence And Initial Failures

Durable root: `/workspace/inlet-evidence/20261009/configured-candidates16/`.

- Initial probe: two failures, 31.987 seconds. Actual current read/worker succeeded;
  approval returned 404 because the reconstructed test app omitted the ordinary
  `customer_execution` router. A mistaken URL-only repair produced two earlier
  capability 404 failures (19.034 seconds). Final reconstruction retains the
  original `/execution` base and mounts the unchanged actual execution router.
- Final Google/Meta SQLite scenario probe: two passed, 21.289 seconds.
- Historical new batch: 16 passed, no skips/failures/errors, 63.946 seconds; parent
  wrapper passed in 72.673 seconds. Exact collection and original provenance are
  retained under `historical-artifacts`.
- Partition qualification initially caught five stale aggregate-count assertions,
  then one remaining oversized-identity-count assertion. All original negative
  checks remain; the final 75 tests passed in 7.444 seconds. Seven wrappers now
  correctly yield ten entries in the three-current-item synthetic fixture.
- `ast-manifest-proof.json` proves unchanged original function AST (name normalized)
  and all seven manifests' exact disjoint 349-node union.

## Prior Static-Claim Correction

The earlier candidate-review package `8118669` incorrectly claimed whole Ruff
passed. Its preserved `candidate-review-link/ruff-final.log` actually reports E501
at `candidate_review_link_retained_fixture.py:109`. The shell command continued
to successful mypy and its final exit status masked the Ruff failure; the earlier
review failed to inspect that separate log. This package includes only the parent
formatting repair from `e61d553` for that file. No semantic or pytest change is
implied. Original logs remain intact. Each final static command here is checked
separately, with its own exit status.

## Completed Current And Static Checks

- Full bounded current cohort: **102 passed**, no skips/failures/errors, 243.233
  seconds (`qualified.xml`): 16 current configured cases plus 86 unchanged default
  planning execution/provider transport boundary tests.
- Whole Ruff passed (`ruff-qualified.log`); bare mypy passed, 1195 source files
  (`mypy-qualified.log`); standalone collection-plugin mypy passed, one file
  (`plugin-mypy.log`); `git diff --check` passed.
- Source-lifetime pure regression module: 16 passed (`lifetime.xml`).
- After the full cohort finished, review required an additional exact financial
  graph invariant. The fixture snapshots every physical `provider_*` table plus
  `mandate_actions`, `optimization_mandate_preparations`, and
  `google_original_completions`, including all values and rows, before current
  login/enqueue and compares them in its finalizer. Candidate jobs/results and
  authentication sessions are separate domains; no financial/provider delta is
  allowed. The original 102-case result remains evidence of its tested source;
  the strengthened finalizer is qualified separately below.

Commands use the local disposable PostgreSQL test database and loopback MockHTTP,
with evidence-local basetemp paths. Exact test selections:

```text
pytest -q tests/test_configured_candidates_current.py tests/test_planning_execution_boundary.py tests/test_planning_provider_transport_boundary.py
pytest -q 'tests/test_retired_execution_snapshot.py::test_pinned_pre0086_execution_contracts[configured_candidates]'
pytest -q tests/test_partition_evidence.py tests/test_retired_execution_snapshot.py::test_every_retired_invocation_has_explicit_historical_and_current_coverage
pytest -q tests/test_configured_candidates_current.py -k 'scenario or revoked_during_read'
pytest -q tests/test_producer_source_lifetime.py
ruff check .
mypy
mypy scripts/inlet_partition_collection.py
```

No frozen W1 source, result, database, production capability or external account
was changed. This package closes the bounded configured-candidate regression
split; it does not establish comprehensive product quality or live readiness.

Final strengthened financial-graph cohort: **8 passed**, no skips/failures/errors,
109.668 seconds (`financial.xml`), Google/Meta scenario and during-read
revocation on SQLite/PostgreSQL. Original consent, ledger, preparation and all
provider rows remained exact through current reads/tick. No exceptions to the
snapshot comparison were needed. Sixteen original current-cohort source copies
were verified removed after reap (278,394,352 logical bytes); resolved-path
provenance avoids counting pytest's `current` symlink twice. Historical extraction
is excluded and retained.
