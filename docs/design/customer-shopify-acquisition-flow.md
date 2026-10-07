# Customer Shopify Window Acquisition

Base: 19ff2fa. The existing API can enqueue, read a known job ID and cancel. It
has no customer interface and cannot recover a forgotten job ID. The ordinary
Measurement History page currently renders only v1 publications; independent v2
publication completion must not be passed through that renderer as if compatible.

## Implemented Additive Interface

AcquisitionIntent and AcquisitionStatus bytes remain unchanged. A bounded GET
on the existing acquisitions collection requires goal_id. The server checks
original session, current owner membership, active workspace and owned goal/store;
it selects only that actor AND exact session's jobs for that goal. Return at most
20 newest jobs plus a truthful truncated boolean (21-row probe). Each entry has
status: AcquisitionStatus, goal_id, goal_revision, start and end from the bound
persisted request. Dates use the existing exclusive-end local-day semantics.
No provider IDs, private handles, session digest or technical profile are returned.

List uses workspace-first private transactions and existing source/identity
checks. It does not require acquisition enabled merely to recover/cancel an
existing job. It does not reveal another session's active job: a conflicting job
from another session remains a named conflict with no cancel authority. Pending
jobs whose source is no longer current cannot be presented as runnable. Reads and
cancel retain the existing status guards; disabled creation stays unavailable.

## Customer Flow

An owner selects existing workspace/store and a confirmed goal on Measurement
History. Show the goal's existing dates and store time zone; suggest known dates
without silently clamping a future horizon. The owner explicitly chooses a closed
local-day start/end and requests a Shopify read. No raw IDs, scope claims, financial
policy knobs, maturity flags or credentials are entered.

Show named progress phase, deadline, state and a manual refresh/cancel action.
Recovery loads server-owned recent rows, so reload does not depend on localStorage.
Exact duplicate enqueue retains existing idempotency; conflicting work gives a
specific message and refresh action. A terminal failure offers a new explicit
request, never silent retry/extended deadline. Completion displays the publication
reference and the fixed limitations: corrections unresolved, maturity unqualified,
no spending authority. Do not call this settled, full-history or qualified learning.

Clear selected job and all results on workspace/store/goal/session changes. Fence
late requests with a selection epoch, original-session cookie check and current
session recheck. Use existing owner connection/goal choices; no automatic paid
connection, hidden worker invocation or enabled-by-default runtime.

## Acceptance

Actual TLS page → existing configured API → real persisted enqueue → bounded worker
with injected HTTP transport → v2 publication, on SQLite and PostgreSQL. No seeded
jobs/publications or runtime getter override. Exercise reload recovery, exact
repeat, competing active request, cancellation, session revocation, disabled
runtime and stale UI responses. Verify no mutation or financial authority is
created. Existing v1 measurement and descriptive comparison behavior stays intact.
No new schema expected. This proposal precedes the minimal recovery API change.


## Frozen Implementation And Evidence

The response contracts were frozen at 70780aa before service/UI implementation.
`acquisition_service.recover(engine, principal, identity, settings, wid, goal_id,
clock=...)` returns `AcquisitionRecovery`. Its private transaction takes the
workspace/principal fence, binds current goal/store, selects 21 rows scoped to the
original actor/session, strictly binds each saved request, and repeats original
identity authorization before returning. It is operational history, not proof
that an old pending source is still usable. Existing per-job GET/cancel and worker
checks remain authoritative. Recovery itself performs no provider request.

The UI is the existing Measurement History page plus `commerce-acquisition.mjs`.
The settings page links to it by purpose. All mutations use existing origin/CSRF
protection. Component selection epochs and original cookie binding are checked
before and after session/HTTP reads, including before sending a mutation. Recovery
preserves a selected exact job or prefers active work rather than selecting an
older completed job with a tied timestamp. No IDs are typed or kept in storage.

The worker's existing cleanup marks expired pending/running jobs and removes their
private staging; it runs even when acquisition is disabled. Enqueue does not
silently expire another job, so the conflict message correctly says to await the
fixed deadline **and worker cleanup**. Another original session's details are not
listed, adopted or cancellable. Recovery remains available while new reads are
disabled. Terminal/new requests require an explicit customer action.

Validation: 42 tests passed in 57.72 seconds across actual SQLite/PostgreSQL API,
new TLS browser flow, legacy measurement TLS and existing acquisition worker
regressions. After the final frontend original-cookie/pre-IO epoch guard, the four
impacted new/legacy TLS tests passed in 13.31 seconds. Whole Ruff, mypy (882 files),
Node syntax and diff checks passed. All test cohorts retained durations20.

The TLS fixture starts with an owned connected Shopify source and a confirmed goal
using existing baseline setup. The browser creates every new acquisition through
the ordinary configured API; the real dedicated runner performs injected HTTP
requests and publishes the new independent v2 document. No new job or independent
publication is inserted by the browser fixture; no runtime getter is overridden.
The browser explicitly requests, recovers, cancels and sees fixed unqualified limits.
No live provider access, deployment, scheduler enablement, financial qualification,
or Full validation was performed.
