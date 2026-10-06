# Customer Closure Quiescing Package

Dependent on PR115 lifecycle receipts/migration0044, with repaired PR112 head
`73725be8c3ce8165d236f998cc850b41cea1f10c` merged before publication changes. This
package implements the approved local quiescing stage. It does not erase data,
settle unknown spend, stop external advertising, cancel billing, or complete closure.
No new migration, live credentials, provider calls or deployment.

## Customer API

- POST `/api/customer/v1/workspaces/{id}/closure-preview`: owner + CSRF + required
  Idempotency-Key, strict empty JSON object. Returns request/revision, exact inventory
  digest and explicit blockers. Replay requires unchanged inventory; a changed
  inventory requires a new preview key.
- POST `/api/customer/v1/workspaces/{id}/closures/{request_id}/confirm`: owner + CSRF,
  exact expected_revision, inventory_digest, and confirm_workspace_id. The latest
  session/user/membership/provider authority is checked at the mutation boundary.
- GET the same closure path: dedicated owner-authorized status, including for a closing
  workspace. Ordinary product routes remain unavailable. Response always explicitly
  reports closed=false, data_erased=false and provider_actions_verified=false.

The API and database flow is implemented; customer navigation/UI is still work.
No export download or portable media archive is claimed by this package.

## Atomic Local Boundary

One transaction holds workspace → user → session → membership before product state.
It changes the workspace to closing, removes pending local authorization grants and
nonces, clears local native/source credential material and legacy secret references,
retires connection generations, disables scoped integrations/automation, pauses
mandates, requests action cancellation and invalidates CRM continuation leases.
Provider secret-manager objects and provider grants themselves are untouched.
Rollback leaves the earlier state intact. Replay cannot repeat generation changes.
Other workspaces, memberships and global customer sessions survive; identity closure
is a separate future operation.

Facts, media bytes, historical checkpoints, published resources and monetary counters
are retained. Existing running/dispatching jobs are not fabricated as canceled. The
request remains blocked for drain/reconciliation, external billing/grant evidence,
unclassified ownership and unset disposition policy. Unknown publication blockers
remain visible. A request accepted for dispatch before closure may still have an
external outcome; local quiescing is not proof that no effect happened.

The shared mandate workspace lock now refreshes an existing SQLAlchemy identity-map
object before checking active status. Google/source authorization exchange resumes
under workspace-first locks and reloads its nonce after provider return, preventing a
late grant response from recreating local credentials removed by closure.

## Late Evidence Lanes

Billing dispatcher diverts already authenticated pending billing notices for a
closing scope into closure_pending without reading the provider, marking processing
complete, changing entitlement, or reactivating the workspace. The canonical billing
customer join and a blocked closure receipt must agree. Future authorized canonical
billing reconciliation still needs an implementation; retained notices alone do not
prove canceled subscriptions.

Publication receipt ingestion permits a closing workspace only through its blocked
closure receipt. Immutable compiler/plan/reservation validation and original
scope/request/fence/freshness checks remain. Valid late receipts append to the
existing receipt ledger only; no step/plan activation, reservation release, or
unknown-outcome settlement occurs. Conflicting definitive receipts for the same
attempt are rejected. Earlier no-effect attempts with different fences remain valid
history and do not falsely conflict with a later attempt. New publication claims
still require an active workspace.

## Verification

Combined lifecycle/quiescing/publication/root-dispatch-regression/billing/Google/
TikTok/migration run: **111 passed, 5 SQLite-specific row-lock skips**; PostgreSQL
counterparts ran. Then the final same-attempt conflict refinement and actual closure
API suite: **14 passed** on SQLite/PostgreSQL. Ruff passed, mypy passed (330 source
files), git diff --check passed. Tests cover atomic rollback/replay, cached-workspace
rejection, preserved global sessions/other workspace access, CSRF and foreign scope,
late exchange return, billing notices without provider calls, and append-only late
publication evidence with unknown reservations protected. Existing publication claim
revalidation tests remain passing.

Full/hosted CI is pending on the assembled candidate. Remaining implementation:
worker-drain acknowledgments and all legacy ownership classification, canonical
external-obligation reconciliation, complete export/download/media archive, and UI.
Purge/media deletion and closed completion additionally require an approved disposition
policy and verified evidence. This is not production closure verification.
