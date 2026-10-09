# Full Actual Feedback Browser — Current Fixture Interface

Read-only proposal after reviewed91c5eee. No implementation/tests until root review.
Exact original failures:

```text
tests/test_reported_feedback_actual_browser.py::test_actual_acquisition_calibration_feedback_browser[sqlite]
tests/test_reported_feedback_actual_browser.py::test_actual_acquisition_calibration_feedback_browser[postgres]
```

## Existing Contract And Obsolete Setup

The actual browser differs deliberately from the configured browser: its complete
shared JavaScript performs real login, action selection, request POST, invokes the
fixture acquisition endpoint, then reads the actual comparison and applies feedback.
It must NOT reuse the configured browser's slicing away of that first half.

Current test_reported_feedback_actual_browser.py calls obsolete acquisition_fixture,
changes CustomerUser.subject to reported-browser, extends login TTL to60days, and
creates a separate SQLite planning.sqlite. Its acquisition callback rebuilds the
legacy tuple around the API-created job, runs actual acquired(), then obsolete
baseline() (execution consent). Runtime dependencies are explicitly injected in this
original test. Preserve/disclose this injection; do not claim configured factory
coverage here or import its different45.75m feedback policy.

## Proposed Setup And Engine Lifetime

Only this Python harness changes, plus ledger. Keep shared JavaScript byte-identical;
no production/shared helper changes. Import reviewed file-backed customer_engine wrapper
and its base fixture, and planning_origin/PlanningOrigin. Use that supplied engine
for both SQLite/PostgreSQL, eliminating the extra SQLite engine/create_all and its
conditional disposal. The wrapper owns the exact current.sqlite or isolated PG schema;
whole-test relative-original/ExpectedPlanningConfirmation finalizer brackets browser
work and asserts exact financial graph plus the permitted current planning draft.

Use prepare_reported_read(db, origin.ids) followed by unchanged
prepare_reported_acquisition(db, configuration, prepared, monkeypatch). This supplies
an actual bootstrap request and current owned GET source wiring, original scalar
IDs, shared clock and settings. The browser must still create its own distinct job.
Store source_type/source_id and bootstrap job ID as scalar evidence before closing
setup Session; retain the existing runtime_box with a fresh-session factory. Do not
use acquired_current() in the endpoint: that would create another request instead of
processing the browser's actual job.

Remove subject mutation and TTL patch entirely. In served driver only, replace exactly
one literal each of 'reported-browser:actual' and 'reported-browser:rotated' with
JSON-quoted `origin.ids.actor_id + ':actual'` and `... + ':rotated'`. Assert occurrence
counts before replacement. Keep every other statement, assertion, handler and timing
bound unchanged; workspace placeholder substitution remains. The first browser POST
therefore creates an ordinary real same-actor session, not a transferred/fabricated
session. Identity/access/issuance/global clocks and TTL remain unmodified. Relative
original windows are already closed, so no long future-window session is necessary.

The original app dependency overrides remain exactly its DB generator, FakeProvider,
reported runtime_box and initial runtime_box.initial. This is an injected-runtime
actual HTTP/browser test, distinct from reviewed configured-runtime/browser coverage.
Do not introduce any authority or transport boundary override.

## Typed Actual Acquisition Callback

Keep `/__fixture__/acquire` synchronous DB work within the existing async harness.
Query exactly one current nonblocked/nonexpired job for this workspace; assert it
is distinct from bootstrap, original_attempt/account/campaign/source/generation match
origin and actual source, original_actor is origin.actor_id. Reload its actual user
and session; assert session.user_id matches and its digest differs from historical
origin session. Do not edit these rows or IDs.

Reconstruct a fresh `PreparedReportedAcquisition` via its existing named `_replace`:

```text
principal = CustomerPrincipal(actual_user, actual_session)
runtime = runtime_box[0]
job = actual_API_job
request = ReportedAcquisitionRequestV1.model_validate(job.document)
source = db.get(original_source_type, original_source_id)
runner = MetaSyncService(db, original_runner_config, reported_feedback=runtime_box[0])
```

All other fields (workspace, shared clock, recorded current GET requests/control,
scalar original IDs) retain their existing meanings. This is session-local reconstruction,
not mutable source/authority editing or an old runtime crossing subprocesses. Assert
actual request before/after windows equal the bootstrap windows driving MockHTTP.
No arbitrary tuple-position replacement; no invented completed job or source facts.

Invoke unchanged acquired(..., data=current) to run real GET acquisitions, captures,
four-observation readiness and actual commerce refresh. Its existing fixture policy
and clock sequence remain unchanged. Then call reviewed
baseline_current(db, current, updated, observation, origin, tmp_path, monkeypatch),
returning `(updated_runtime, genuine_InitialPreviewV1, NativeWireReads)`.
This creates actual PlanningConsent using canonical configuration/current owned native
catalog and same original ledger, then genuine V1 initial46m with the original feedback
policy47m. Assign runtime_box[0] to that returned runtime. Preserve baseline46m assert;
replace historical `len(data[10].posts)==1` with scalar original_post_count1 plus current
native POST0, retaining strict financial finalizer. Never fake a prior MockHTTP POST.

All expected query/source/cadence/goal/period/expiry guards remain active. If actual
API job/session/profile/window or V1 binding fails, retain trace and review rather
than changing source dates, runtime policy, deadlines or guard behavior.

## Unchanged Browser And Evidence

Preserve full driver: initial login, owned action selection/CPA input, actual pending
request, actual acquisition endpoint, real calibrated baseline, comparison CPA5/2.5,
USD47 from46, no compounding/financial handoff, actual held-response discard on
workspace change, history restoration, actual same-owner rotation and old-response
invalidation, refresh and logout. Keep TLS setup, external DNS blocking,90sec completion
bound, polling bounds and process/thread/listener cleanup. There is no separate
explicit expiry-negative in the original JavaScript; do not claim one was added or
closed. Actual source/preview/session expiry checks remain running normally.

Supplement actual before/after session evidence: first browser login and later rotation
are genuine new rows for original actor, ordinary TTL; rotated session revoked by
actual logout. Preserve historical session independently, no fabricated cookie/row.
Write structured browser result under evidence basetemp. AST proof must preserve all
original Python assertions except documented user-setup and historical counter changes;
shared JS byte equality plus served-script transformation proof excludes only exact
identity/workspace literals. No driver slicing or fabricated JSON response.

First actual SQLite browser gate, then exact2bothDB and bounded current genuine V1
baseline2/configured browser2 compatibility. Preserve raw failures/logs/XML/exact original
IDs; whole Ruff/bare mypy isolated/tmp, Node syntax and diff before freeze. Overlap
is not extra recovery. No aggregate, live calls, new algorithms or broader scope.
