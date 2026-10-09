# Original Google Completion Source For Current Privacy Regressions

Proposal from `a9a7681`. Exactly fourteen current cases:

- `tests/test_google_completion_evidence.py::test_durable_reader_and_export_never_release_hold`: SQLite/PostgreSQL × None, document, fence, request, digest, scope (12).
- `tests/test_google_completion_evidence.py::test_customer_closure_retains_original_completion_and_financial_hold`: SQLite/PostgreSQL (2).

Do not change the shared `emitted` helper, native completion/restore consumers,
legacy acknowledgment/capture tests already qualified by `05d48c7`, or any product
code. The fourteen functions remain current-policy tests with `planning_boundary`
on these two functions only. No retained-engine fixture or guard override.

## Fixed Child And Storage Boundary

New helper `tests/google_completion_retained_fixture.py` and fixed child
`tests/fixtures/retired_execution/google_completion_seed_driver.py` use only literal
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`, the existing exact three tree hashes and
verified extractor. One source behavior, no caller-selected PIN/provider/action,
arbitrary callback, policy, table selector or child mode.

The child calls the untouched pinned `test_google_completion_evidence.emitted`
against original `configuration` and a freshly prepared, exclusively owned
current schema. To measure the real server, a scoped record-only wrapper around
that pinned module's imported `ready` delegates to the original function with
identical arguments, records its returned tuple, and returns it unchanged. Require
exactly one invocation and the actual original `GoogleServer` instance. No field,
transport, response, runtime or authority behavior changes. The original helper
performs actual preparation, approval, claim and MockHTTP dispatch; require its
existing verified-target-state outcome plus `len(server.writes) == 1`. This is one
historical simulated POST, not current write permission. No live HTTP.

Parent owns DDL. SQLite uses a new evidence-local file with FK enabled and current
metadata; original in-memory fixture is not shared with a subprocess. PostgreSQL
uses only the existing explicit disposable loopback URL, no URL query, exact
engine URL equality and actual schema `inlet_test_<32 lowercase hex>`. Parent and
child check every non-Alembic table empty before original writes, and parent checks
unchanged schema fingerprint afterward. No migration, stamp, reset, bootstrap
exceptions or schema broadening in this package. All transactions are committed
and Sessions closed before parent readback.

One explicit SourceLifetime profile `google_completion` owns the new helper and
child, source leaf `source`, archive `historical-source.tar`. ID JSON, producer log,
media and file SQLite remain outside it. Preserve existing provenance/reap/failure
retention guarantees and all historical harness exclusions; no utility changes.

## Exact Scalar Result And Parent Readback

Frozen `GoogleCompletionIds` fields:

- `workspace_id`: positive strict integer.
- `actor_id`, `attempt_id`, `fence`, `receipt_id`, `reservation_id`: 32 lowercase hex.
- `request_digest`, `completion_digest`, `response_digest`, `receipt_digest`: 64 lowercase hex.
- `receipt_sequence`: positive strict integer from the actual stored receipt.
- `reservation_amount_micros`: positive strict integer from the actual held row.
- `provider_posts`: strict integer exactly one, measured on original server.

Output is exact-key JSON <=4096 bytes; no session material, request body, provider
response, original ORM object, runtime callback or authority object crosses.
Require exactly one original attempt, response, receipt and Google completion,
and the actual associated held reservation. Parent reloads original attempt/run/
step, request, response and receipt using current contracts; verifies common
workspace, original fence/request digest, current completion digest, receipt ID/
sequence/digest, receipt verified-target-state, linked hold identity/value/state,
and actor ownership. It resolves the actual mandate/consent/ledger through the
request and checks original lineage. Do not manufacture counts, completions or
financial rows. Exact field-name/contract availability is verified in a bounded
probe; incompatible original source semantics are a blocker, not a fallback.

## Parent Snapshot Modes And Permitted Deltas

`retained_google_completion(engine, artifacts, *, purpose, tamper=None)` yields
only `(current_engine, GoogleCompletionIds)`. `purpose` is exactly `reader` or
`closure`; `tamper` is exactly None/document/fence/request/digest/scope, with
non-None allowed only for reader. These affect the parent final verifier only;
the child source is identical. No arbitrary expected-delta callback.

Before yielding, snapshot every physical `provider_*` table, `mandate_actions`,
`optimization_mandate_preparations` and `google_original_completions`, all values
and rows ordered by actual primary key. The final verifier opens a fresh current
connection after consumer Sessions close, with default no-write guard intact.
Compare exact original graph, with only the following computed transformations:

| Reader tamper | Exact permitted change to the one original completion |
| --- | --- |
| None | No change anywhere, including recorded_at and normalized response rows |
| document | Only document.capture.operation_digest becomes 64 `f` characters |
| fence | Only row.fence becomes 32 `f` characters |
| request | Only row.request_digest becomes 64 `f` characters |
| digest | Only row.digest becomes 64 `f` characters |
| scope | Only document.capture.account.workspace_id increases by 1000 |

All tamper branches retain the original committed SQL update and subsequent
current `read_owned` rejection. No completion field other than the exact stated
path may change, even if the corrupted payload is no longer internally valid.
The unchanged branch performs the original actual current `evidence_lock` and
`record_response` with the same captured response at NOW+1 second. Current
`optimization.py:907` inserts only a missing normalized-response digest and
`google_completion.py` returns on identical prior capture: the original already
contains that response, so the expected delta is **none**, including timestamp.
A changed response count is investigated, never silently allowed.

Closure keeps the original current user/session setup, `confirmed`, actual
`quiesce`, commit, completion equality, held-state and protected inventory checks.
It legitimately changes customer/workspace/grant/lifecycle records outside this
financial snapshot; those original current assertions must not be moved to the
child. Within the snapshot, compute precisely the current `quiescing.py` behavior:
original owned provider mandates' state becomes `revoked`; owned uncanceled runs'
state becomes `canceled` and canceled_at becomes the existing test NOW; existing
owned mandate_actions' cancel_requested becomes true. Preserve every other column
and row. These are explicit revocation/cancellation changes, not broad table
exemptions. Completion, original attempts/responses/receipts, consent/revision/
ledger, reservation identity/value/state and all other financial graph rows stay
exact. No post-closure normal-owner read is required because the workspace is
closing; current raw protected-row and inventory assertions remain meaningful.

## Qualification Before Integration

Probe one SQLite no-tamper reader plus PostgreSQL closure first. Then all fourteen
exact current cases and the unchanged default planning execution/provider
transport boundaries (86). Preserve original assertion ASTs aside from fixture
setup/binding; record intentional current additional assertions separately. Add
focused tests only if needed for new closed argument/URL parsing. Run whole Ruff,
bare mypy, diff check and SourceLifetime pure tests. Retain original W1 failures,
all probe failures and exact commands/logs/XML. No aggregate run, native restore
rerun, historical batch expansion or live qualification claim.
