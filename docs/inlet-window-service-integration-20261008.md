# Requested-Window Customer Service Integration — W1

Base: `d3092a5`. Branch: `codex/inlet-window-service`.
Worktree: `/workspace/inlet-window-service`.
Frozen scope: `docs/design/planning-window-service-integration-v1.md`.

## Implemented

`generation_ports.py` is a consuming evidence union/reader protocol. It does not
change old ports or serialized evidence. The service dispatches only canonical
policy/digest capabilities to the actual legacy or requested-window owned reader.
A separate `window_composer` receives the genuine generation ticket. Wrong evidence
branch, unknown policy and mixed candidate generator fail with bounded conflicts;
there is no legacy fallback. The repository independently binds candidate policy,
generator, exact references and actual bundle branch before its existing CAS,
idempotency, session, privacy, goal, paid ownership and persistence gates.

The final requested-window check receives the service's live clock and a DB-only
callback bound to the final refreshed identity fact/current principal. Identity
refresh remains outside SQL. Account contexts close before source-witness capture
or inserts. Existing final five-second authority and database-clock expiry checks
remain before/after persistence. No TTL, clock limit, authority rule or billing
policy changed.

Retained source capture dispatches by the closed policy/generator pair. V3 uses
exactly the existing `local_reporting_v2` formula; V1/V2 formulas and source bytes
are unchanged. Unknown/mixed retained pairs yield typed unavailable proof, never
current-by-default. Actual owned-source tests compare V2/V3 witness fields excluding
the independently sampled observation time. No migration is required.

**Production defaults remain V2.** Tests explicitly inject canonical V3 and assert
that the default service starts on V2. The existing pure assertion was renamed to
accurately state that the legacy composer rejects V3, rather than implying no
explicit V3 service path exists. No fake policy aliases or old artifact bytes were
changed. No comparison form/controller files were touched.

## Actual Offline Acceptance

The API tests use authenticated routes, saved inputs, native MockHTTP collectors,
owned source reads, the genuine composer, final rechecks and SQL repository.
`tests/window_service_fixture.py` provides reusable real Meta 0090 56-day import
setup and returns the original header/completion, mutable offline provider-response
queue, synthetic runtime and original pre-import ticket. That ticket is only a
source of customer goal/account IDs; it is not reused as fresh generation authority.
The fixture also establishes actual offline billing checkout and signed webhook
reconciliation, then enables the paid-work gate for the API journey. No real payment
or production commercial profile is claimed.

Coverage includes:

- Primary last-seven-day 100 clicks, 10 selected conversions and USD100, with a
  separate preceding-seven-day explicit-zero comparison; complete zero versus
  missing selected cell versus absent calendar day. The immutable original 56-day
  import header is preserved. Both requested-window references survive customer
  current/history/export; positive conversions never produce a no-conversions claim.
- A real reimport correction outside both requested subsets invalidates the whole
  retained source proof. A successor retains requested values and the old ancestor
  remains exportable. An actual zero-to-missing reimport withdraws the zero claim.
- All three platforms retain actual native catalogs with per-window unsupported
  reporting gaps. Actual missing-presence to available-presence transition stales
  the retained version and permits a new, explicitly linked version. Viewer reads
  and exports use local proofs without native provider reads.
- Actual receipt acquisition/saved target inputs: generation uses the original
  catalog without native rereading, including success-primary/unavailable-comparison;
  advancing the service clock after real composition to the original receipt expiry
  rejects final persistence.
- Post-composition session revocation, goal unconfirmation, privacy cleanup,
  owner suspension, source generation change, malformed presence and paid cancellation
  abort generation. A real independent input revision through the service wins the
  input CAS and rejects the older generation. No generation version/dependencies/
  success receipt are stored. Privacy cleanup independently removes the previous
  graph; it is not undone by the failed generation.
- A real PostgreSQL transaction holds the owned goal row; `pg_blocking_pids` confirms
  the final generation SELECT waits. The holder releases after 5.2 real seconds;
  unchanged authority freshness rejects the transaction with
  `planning_authority_expired` and no persisted generation. SQLite intentionally
  skips this PostgreSQL-only lock-wait case.
- Adverse injected unknown policy, mixed generator and sibling evidence return 409
  with no legacy composer fallback. Forged evidence is used only as a rejection
  test, never as positive pipeline evidence.

## Qualification

Evidence directory: `/workspace/inlet-evidence/20261008/window-service/`.
Source/API checkpoint `f681f1a` was independently reviewed by the root reviewer,
with no P1/P2 findings. The final successor contains only the obsolete-message test
repair and this terminal evidence update; independent closure of that successor is
recorded by the parent after review. Artifact files are actual pytest logs/JUnit, not reconstructed
terminal excerpts.

- `api-qualified.log/xml`: **40 passed, 3 failed, 1 expected SQLite skip, 251.88s**.
  The three failures were test harness issues, not relaxed production gates: the
  PostgreSQL monitor held a statistics snapshot hiding a newly opened blocked
  backend, and two receipt-expiry tests encountered the correctly enabled paid
  snapshot expiry first (402). The monitor now clears its own statistics snapshot
  per bounded poll. The receipt test independently performs actual signed billing
  reconciliation at the explicit advanced test-clock instant, leaving the original
  receipt expiry unchanged, so the receipt's own 409 boundary is measured.
- `timing-repair.log/xml`: **5 passed, 1 expected SQLite skip, 40 deselected, 48.03s**.
  These six cases include all three repaired failures and existing receipt successes.
  They overlap the earlier cohort: this is not a clean 44-case module pass, and
  counts are not summed. Production source was unchanged by these fixture repairs.
- `io.log/xml`: **2 passed, 44 deselected, 17.70s**. Actual engine transaction hooks
  assert planning identity refresh and native reads occur outside SQL, including
  generation and retained read. This is separate from the API authentication layer.
- `policy-final.log/xml`: **2 passed, 38 deselected, 2.52s**. Canonical legacy digests,
  legacy composer rejection of V3, and the V2 production default remain explicit.
- `compatibility.log/xml`: **114 passed, 2 failed, 3 expected SQLite skips,
  16 serializer warnings, 433.23s**. Both failures are the obsolete error wording in
  `test_resolve_owned_customer_intent_and_reject_unread_selection`. The underlying
  409/actionable message already exists at base `d3092a5`. The test-only successor
  updates that assertion and adds zero-plan-row proof. Its actual both-DB rerun
  `compatibility-repair.log/xml` passed **2 cases, 20 deselected, 8.42s**.
  The three skips are PostgreSQL-only independent transaction races. The serializer
  warnings originate in existing unsafe-copy presence contract tests. No other
  compatibility failure occurred. This is scoped repaired qualification, not a
  clean 119-case aggregate; the overlapping results are not summed.

The reusable fixture was frozen separately as helper-only commit `ee889ec` for
parallel browser preparation. No consuming production source changed during the
compatibility run. Final checks after the test-only repair: whole `ruff check .`
passed; bare `mypy` passed **1105 source files**; `git diff --check` passed.
Artifacts: `qualification-ruff.log`, `qualification-mypy.log` and
`qualification-diff.log`.

Development iterations are not full qualification: initial assertions used the
wrong evidence-kind label, an incomplete composite PlanRow key, and incorrect
404 expectations for privacy cleanup/owner suspension. A paid-race test exposed
that inherited offline fixtures had the optional gate disabled; the fixture was
corrected to actual checkout/reconciliation plus the enabled gate, without changing
production. One stale development run was intentionally interrupted after 7 passes
when a test-only helper block needed relocation. Static annotation/import/format
errors and an unnecessary non-overlapping identity assertion were corrected. Logs
remain in the evidence directory; failed/interrupted/overlapping runs are not summed.

## Remaining Gates

This is offline integration, not production activation, provider certification,
expert planning qualification, deployment or a purchasable release. Source review closed at `f681f1a`; the parent reviews the test-only qualification
successor before package integration. Actual authenticated V3 browser
acceptance and the separate reviewed default-activation package follow. The one
frozen aggregate remains pending; no Full/hosted/live checks were started here.

## Later Default-Activation Compatibility Seams

Keep the production V2 default in this package. The later activation package must
handle these explicit legacy/default distinctions rather than adding aliases:

- `tests/test_planning_document_repository.py::test_generation_revoked_during_actual_reads_rolls_back`
  hooks `OwnedPlanningEvidenceReader.collect`; a V3 default would bypass that hook.
  Port the adverse hook to the selected genuine reader or explicitly keep a V2
  legacy-path test, while preserving a V3 revocation test.
- `tests/test_planning_qualified_reporting.py::test_collection_to_final_recheck_never_saves_changed_presence`
  similarly hooks the old reader. Its positive API case explicitly asserts V2
  policy and legacy rationale wording. Preserve that version's acceptance by
  injecting the real canonical V2 pair, or deliberately add distinct V3 assertions;
  do not globally substitute fixture bundles.
- `tests/test_meta_import_planning_presence.py` asserts the V2 policy and exact
  legacy wording after real 56-day imports. Pin canonical V2 for historical path
  coverage if the application default changes; the new window API test covers V3.
- `tests/test_planning_retained_sources.py::prepare` already injects the composer
  constants and genuine legacy reader/composer explicitly. Preserve those constants
  and stored witness/DTO bytes; changing the service default should not change it.
- `tests/test_planning_evidence_adapter.py::setup_evidence` returns a directly
  constructed old reader and a test-only `1` policy. Service/API tests generally use
  its owned account/goal fixture and let the service construct its own canonical
  ticket; do not turn `1` into a production alias. Generic pure artifact fixtures
  using `test-v1` remain generic serialization tests, not new runtime policies.
- `tests/test_planning_documents_api.py`, `test_planning_service_error_boundaries.py`
  and most repository flows instantiate the default service without composer fakes.
  They should rerun under the final default. The original authenticated browser
  journeys remain separate default-activation acceptance, alongside the new real
  import/window browser journey owned by the root lane.
- `tests/test_window_service_api.py::configure_v3` and the explicit service-default
  assertion currently prove V2 is still the default before V3 injection. Update
  these assertions deliberately in the reviewed activation package, not silently
  during this integration package.

Source checkpoint static checks: whole Ruff passed; bare mypy passed **1105 source files**; `git diff --check` passed.


Exact compatibility command (with disposable PostgreSQL fixture schemas and the
same environment variables as the API runs):

```sh
pytest -o addopts='' -q tests/test_planning_documents_api.py \
  tests/test_planning_document_repository.py tests/test_planning_retained_sources.py \
  tests/test_planning_service_error_boundaries.py tests/test_planning_qualified_reporting.py \
  tests/test_meta_import_planning_presence.py tests/test_planning_contract_imports.py \
  --junitxml=/workspace/inlet-evidence/20261008/window-service/compatibility.xml
```

API cohort: `pytest -o addopts='' -q tests/test_window_service_api.py` (44 cases at
that checkpoint). Subsequent focused selections on the final file were
`-k 'real_postgres or final_original_expiry'` (six cases) and
`-k 'identity_and_native'` (two cases). Compatibility repair selection:
`tests/test_planning_document_repository.py -k resolve_owned_customer`. Policy
selection: `tests/test_window_evidence_contract.py -k 'legacy_policy_digests or production_service_default'`.
All final commands retained separate log/XML paths listed above. This does not
claim performance qualification under controlled load or a full suite run.
