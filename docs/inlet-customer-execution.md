# Customer Execution Journey

This package exposes the durable provider creation/activation services to an
owner through strict intent-only customer APIs and `/app/execution`. It remains
an offline engineering increment: the default customer runtime factory returns
None, no credential factory is installed, and no real advertising account was
called. Default availability is explicitly blocked. Google configuration has a
real bounded named HTTP discovery producer; Meta and TikTok remain visible with
an explicit missing producer blocker pending their separate implementation.

## Customer Flow

Select an approved campaign draft, review proposed execution limits, save the
proposed policy, and separately consent to its exact persisted revision. Existing
simulation approval is not execution authority. The proposed limits may be edited;
consent pins the accounting account set for its fixed period. Account removal or
addition cannot reset spent amounts or evade held exposure. Aggressiveness cannot
raise the overall spending cap. The owner can revoke local consent independently
of provider runtime availability; uncertainty and external effects remain intact.

Choose a named verified purchase-measurement option, daily budget and maximum CPC.
Only the opaque catalog choice identifier crosses the customer API. Server reads
resolve owned account/generation, manager identity, source revision, target and
conversion references, source reservation amount and supported wire configuration.
A fresh provider qualifier independently verifies the selected resources. Missing,
expired, changed or unsupported catalog evidence blocks review.

Review the exact campaign copy, landing page, audience, keywords, budget/bid,
period and configuration; approve the persisted review and plan digests. The
browser sends those digests only as exact-version acknowledgements. It cannot
supply an executable plan, qualification, exposure evidence, provider receipt,
environment or runtime. Create an idempotent run, then advance at most one reviewed
step per request. Completed creation remains paused. Activation requires a separate
server readback of the complete original graph and its own review/approval/run.

Saved execution status and owned receipts can be recovered at
`/app/execution/{workspace_id}/{run_id}` without relying on an active selector.
Unknown/conflict states cannot cause an original mutation to be replayed. Read-only
reconciliation uses the persisted original attempt. Cancellation stops future
local steps; it does not recall in-flight requests or assert external cancellation.
`verified_target_state` activation is displayed as observed status, with effective
time unavailable and no causal lift claim. Held reservations remain visible.

## Interfaces And Authorization

Routes are under `/api/customer/v1/workspaces/{wid}/execution`; implemented resources
include capabilities, mandates (create/edit/list/consent/revoke), draft context,
configuration options, creation/activation reviews, exact approval, run creation,
run listing/read/advance/cancel/reconcile and latest owned attempt receipt.
`draft-context` returns an explicitly unauthoritative editable proposal derived
from the approved source's existing plan. It does not create execution consent.

Mutation routes require same-origin CSRF and owner role. The server binds original
session digest/user identity into the shared `ExecutionAuthorizer` callback,
reloading after blocking locks and IO. The callback checks fresh provider/session
status under workspace→user→session→membership order, then coordinator ledger and
source locks follow. Optional authorizer support was added to the Google provider
review service at both initial and post-qualification boundaries.

The last authorization check before emission is inside the durable admitting
transaction. Logout after admission cannot recall an in-flight request; its receipt
still must be persisted. The customer response is then reauthorized and denied if
the original session was revoked. Logout during catalog or qualifier IO prevents
review persistence. Provider HTTP never runs while these DB locks are held.

All responses are no-store; browser strings use textContent and no tokens/provider
secrets enter browser state. Receipt responses use the existing normalized owned
reader, not raw provider responses. Local policy/runs are capped at100 listed rows;
large-history pagination remains a followup. The static shell is public and inert;
all data and operations use authenticated APIs.

## Evidence And Remaining Work

Actual loopback HTTPS browser and API tests use SQLite and disposable PostgreSQL,
server-only injected contract-test runtime, actual HTTP adapters and mocked HTTP
responses. The full customer sequence covers separate consent, named discovery,
independent qualification, exact approval, durable creation, separate activation,
receipt recovery and logout. Security regressions cover forged authority fields,
foreign owners, CSRF, wrong digest, revoked sessions during reads/admitted dispatch,
unknown no-replay and held reservations. The UI labels every test path as contract
execution with no provider-account changes.

Production factories, operator live enablement, provider permissions, Google cap
qualification, real customer-data/live environment testing, completed social
configuration journeys and settled spending remain separate gates. No migration
or new spending policy is introduced. Root owns integration and Full qualification.
