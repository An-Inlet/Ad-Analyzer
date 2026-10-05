# Shared Offline Action Interface — B07 And Later Adapters

Customer intent and provider authority are separate. B07 supplies only deterministic
simulation; its runtime cannot dispatch a live provider request. Later adapters must
implement current-state evidence, conservative exposure bounds and reconciliation
before any separately authorized live release. Existing mock/live-write blocks remain.

Mandate revisions bind exact confirmed goal, fixed currency/period, explicitly owned
accounts, absolute cumulative spend/change/count caps and cooldown. No renewal, refund
recycling or implicit 5/10/20% permission. One overlapping governing budget per workspace;
replacement revisions carry all observed/reserved/change consumption forward.

Actions bind immutable canonical draft/payload digest and expected resource state.
Campaign/creative drafts require exact customer review. A single transaction locks the
workspace/mandate, validates owned scope and reserves exposure/change/count before
committing a fenced claim. Dispatch rechecks expiry/pause/revocation/goal/source/current
state. Uncertain outcomes retain reservations and cannot be blindly retried. Cancellation
before dispatch may release a proven-unused reservation; after dispatch it requests
reconciliation. Inlet pause/revoke does not claim to stop an external ad or undo spend.

Initial interface has no network adapters: evidence and outcomes are explicitly
synthetic and persisted as such. UI must label simulated mandate/action status. Owner
starts/resumes; owner/admin stops. Goal/mandate/draft revision changes invalidate pending
eligibility. Provider secrets, raw API payloads and customer advertising actions are not
part of this package. Approval of this offline implementation does not authorize live use.

## Implemented Simulation Boundary

Routes live under `/api/customer/v1/workspaces/{workspace_id}/mandates` and require
shared customer sessions, current membership and mutation CSRF/origin checks. Only
an owner can approve/resume, review an exact campaign/creative draft, claim, dispatch
or reconcile simulations. An owner/admin can pause/revoke/cancel; analysts can draft.
All returned state explicitly sets `live_execution_enabled=false`.

Evidence supplied to `simulate/*` is synthetic, including entitlement, resource state,
exposure bound and complete-account cumulative period consumption. It is never a
provider attestation. A future live adapter must collect authoritative observations
itself; these customer-supplied values must never authorize live execution. Aggregate
consumption uses a high-water mark; reservations are added conservatively. Settlement
requires cumulative consumption consistent with prior observations and settled costs,
then releases the reservation without counting the same observed spend twice.

`AD_ANALYZER_MANDATE_SIMULATION_ENABLED=false` blocks new simulated claims/dispatch;
reconciliation and cancellation remain available. Claims expire after five minutes,
require a matching attempt fence and cannot dispatch twice. Unknown outcomes retain
reservations. A violated bound requires manual reconciliation and keeps the reservation;
there is no automatic refund, blind retry, compensation or claim that past spend reversed.
Immutable periods prevent replacement mandates from resetting cumulative limits.

## Remaining Acceptance

This package proves database and API simulation behavior, including PostgreSQL races.
It does not satisfy live adapter/read-back acceptance for B09/B15/B16 or validate the
5/10/20% policy inputs. Provider-specific spending semantics, reporting delays, actual
entitlements and live source-health proofs remain later adapter/release requirements.
