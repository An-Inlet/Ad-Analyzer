# Social Execution API Historical/Current Split — 2026-10-10

Implements reviewed `ba33ba4` against merged `d878264`. No production changes,
capability exemptions, current advertising writes, identity-row rewrites or TTL changes.

The original two functions (ten nodes) are renamed only; mapping validation compares
complete ASTs/decorators with PIN `2155ff3e3ab00cd62057dd86cb49d45359d4f49f`.
The new `social_execution_api` batch preserves paused creation/activation and all six
mid-I/O races at that historical runtime. A current early denial does not claim those
callbacks ran. Existing helpers and all thirteen prior batches remain unchanged.

Four new current cases cover both platforms/databases: actual owned options,
configuration review/confirmation, exact retained review/run history, confirmed
configuration hash, no-store, same-email foreign caller, CSRF, ordinary logout and
post-logout privacy. Only after positive reads are complete do forbidden execution
runtime/media factories enforce zero dependency resolution on blocked mutation paths.
`configured_social_review` resolves its optional execution dependency even when a
read runtime is supplied: that dependency returns `None` during the positive phase;
no execution runtime is constructed. Foreign reads return exactly 403; foreign
mutations return exactly 404 through `guard_customer_mutation`.

The closed `execution_api` producer consumer independently validates one exact
current configuration review/approval, two actual login sessions/token receipts,
one new foreign user, and only the real owner's logout revocation. Every original
source/financial/media/review/run row and physical schema remains immutable. Copied
baseline/duplicate row negatives exercise the checker. Both clients close before
the source finalizer. Historical producer `native_posts=0` is source-established,
not a claimed live-server counter. Current denied requests leave the entire graph
unchanged and all forbidden factory call counters zero.

## Qualification And Preserved Failures

Durable evidence: `/workspace/inlet-evidence/20261010/social-execution-api10/`.
Every command uses `/workspace/inlet-venv/bin/pytest -o addopts= -q`, explicit unique
`--basetemp=/tmp/inlet-social-execution-<stage>-20261010`, and durable `--junitxml`.
Database runs use the existing disposable localhost integration database with isolated
fixture schemas; no shared target reset.

- `gate`: SQLite2 failed 27.44s because the forbidden runtime sentinel was installed
  before `/options`; strict finalizer also rejected missing logout. Full artifacts
  retained in `failed-gate-artifacts`, no product auth failure inferred.
- `corrected-gate`: SQLite2 failed 31.86s because foreign POST was incorrectly
  expected403; exact actual404 required. Full artifacts retained in
  `failed-corrected-artifacts`; guards were not relaxed.
- `status-gate`: SQLite2 passed 34.51s after those reviewed corrections.
- `historical-wrapper`: only `[social_execution_api]`, wrapper passed83.92s;
  raw child10 passed70.56s. `historical-proof/` retains collection, provenance,
  raw log/XML. No previous historical batch reran.

The partition checks exposed existing drift: BATCHES already had thirteen entries,
while provenance paths and exact count contract still stopped at eight/361. This
package explicitly appends all five reviewed missing entries and this new batch,
closing fourteen/385 without dynamic acceptance or modifying frozen evidence.
Initial partition runs: 9failed/66passed15.95s; 5failed/70passed13.68s;
2failed/73passed12.34s. Raw logs/XML remain. Final counts below supersede these
fixture expectations without erasing the failures.

Final partition matrix: `tests/test_retired_execution_snapshot.py::test_every_retired_invocation_has_explicit_historical_and_current_coverage tests/test_partition_evidence.py` produced74passed/1failed26.30s (remaining fixed identity-index count11→17). Affected-only `test_oversized_same_display_distinct_suffix_maps_compactly` passed0.61s after the count correction. All75 distinct cases now have passing evidence; this is not a claim of one final all-green matrix invocation.

`qualified`: `tests/test_social_execution_current.py tests/test_customer_social_review_api.py tests/test_planning_customer_boundary.py` passed16 in186.10s: current4, existingAPI4, defaultboundary8. This precedes final review tightening; it is preserved, not counted again as extra coverage.

Review followup replaces malformed-only denial inputs with actual saved configuration,
original typed mandate binding, review/plan digests and retained run IDs. Runs/advance
send no body; malformed extra-plan requests remain separate. One-shot logout records
actual request start/end seconds and requires the persisted revocation inside that
interval, with copied out-of-bound and repeated-binding negatives. Both clients close
in nested finally. Only the affected current4 rerun after this test-only tightening;
no historical batch or compatibility suite repeats.

Final followup: `tests/test_social_execution_current.py` passed4 in102.01s on SQLite/PostgreSQL, no skips. Whole `ruff check .`, bare `mypy` (1254 source files), and `git diff --check` pass after final code edits. No JavaScript changed. Raw source IDs/producer logs/SourceLifetime proofs are retained under `followup-proof/`, alongside earlier qualified proof and all failures. `artifact-manifest.json` indexes durable evidence. No Full, live-provider, or original-batch rerun was performed.
