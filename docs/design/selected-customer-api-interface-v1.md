# Selected Reporting Customer API — Exact Service Proposal

Base c47e5ce; branch codex/inlet-selected-customer reuses clean
/workspace/inlet-selected-storage. No storage/schema changes planned.

## Ownership

Own new `app/google_connections/selected_customer.py` (service and strict public
DTOs), `app/api/customer_reporting.py`, additive main router registration, dedicated
API tests and package ledger. google_runtime owns selected_owned_context.py and its
OAuth/Vault tests. No progress.md or raw/summary/HTTP/catalog changes.

## HTTP Contract

Prefix `/api/customer/v1/workspaces/{workspace_id}/reporting/google`.
All responses Cache-Control:no-store. Every POST uses MutationPrincipal/CSRF;
GET uses Principal, original-session owner authorization, no provider reporting IO.

- POST `/event-options`: `{account_id: positive strict int}`. Returns account_id,
  observed_at, expires_at, options[{option_id:64hex,label,metric_family:
  conversions|all_conversions,api_version:v24}], spending_authorized:false.
  Full bounded catalog maximum2000; no default family, raw event/resource/native
  account/connection/session/token/query-profile fields. Option digest is an opaque
  selector only, never authorization. Catalog labels distinguish explicit families.
- POST `/event-selection`: account_id, option_id, expected_selection_id:32hex|null,
  expected_selection_digest:64hex|null. Pair must both be null or both present.
  Returns state `selected`, account_id, selection_id, selection_digest, confirmed_at,
  label (fresh), metric_family, api_version, spending_authorized:false.
- GET `/event-selection?account_id=...`: same safe receipt with state
  `none|selected|refresh_required|unavailable`; nullable selection fields follow
  state, label is null because not freshly known. No raw historical document.
  Invalidated heads expose their exact ID/digest pair for safe explicit retries,
  but not stale choice details as current. Stale active scope returns unavailable.
- POST `/event-selection/invalidate`: account_id and nonnull exact expected pair.
  Returns refresh_required and head pair. Same invalidated-head retry is idempotent.
  No replacement selection or provider IO in this transaction.

Selection digest is an intentionally exposed immutable choice receipt/CAS commitment
required by the canonical interface; it is not scope/proof/token authority. All other
internal digests remain private.

## Trusted Composition And Service Signatures

`SelectedCustomerRuntime(sessions:Callable[[],Session], oauth:GoogleHTTPRead,
 vault:Vault, transport:Callable[[],httpx.BaseTransport], clock:Callable[[],datetime])`.
No default credentials/provider/client; default FastAPI runtime dependency returns
None (503 fixed unavailable after owner authorization). Explicit transport required; tests use MockTransport and no live default is installed.
Create a fresh OwnedGoogleReportingContext for every options/confirmation operation.

`options(runtime, principal, provider, workspace_id, intent)->OptionsView`
`confirm(runtime, principal, provider, workspace_id, intent)->SelectionView`
`state(db, principal, provider, workspace_id, account_id)->SelectionView`
`invalidate(db, principal, provider, workspace_id, intent)->SelectionView`

Options/confirm own short-lived sessions and close every transaction before OAuth/
HTTP. API releases its initial dependency transaction after capturing original
principal identity and before service IO. No caller transaction is implicitly committed.
Runtime service creates immutable original-session authorizer before release.
State/invalidate use caller DB, API commits invalidation once after final checks.
No token/session representation retained in DTOs/logs.

## Confirmation Algorithm

1. Capture original identity/session authenticated_at+expiry; initial owner, paid
   read/sync, account/platform scope and exact head CAS check, before any provider IO.
2. Resolver derives owned request; fresh complete catalog uses actual injected v24
   HTTP and resolver pre/post callbacks. Find option by exact identifier bound to
   this original session/scope and fresh metadata. Rename/removal changes identifier.
3. In fresh final transaction, lock original owner/session workspace first, then
   source/account, repeat exact head/current scope and clocks after waits. Require
   the exact observed catalog request scope and unexpired observation. No resolver
   callback using a second session while holding these locks.
4. Before first/replacement selection, construct aggregate dependency from actual
   CurrentPerformance and invoke existing `_aggregate` complete-manifest validator.
   Require current completion privacy equals new scope. This blocks invalidation→
   immediate reconfirmation until genuine aggregate refresh; never restamp metadata.
5. Same active choice with exact CAS returns unchanged stored selection only after
   fresh catalog/source proof. Different active choice requires explicit invalidate.
   Invalidated replacement always server UUID/new time; immutable history not adopted.
6. Build CustomerEventSelectionV1 from server option/source/original actor only,
   store_selection exact CAS, final original authorization/paid/sync/deadline checks,
   flush/commit once. Rollback on any failed check. Final receipt uses fresh label.

## Checks / Limits

Actual FastAPI HTTPS TestClient plus real customer login, source row/encrypted grant,
GoogleHTTPRead OAuth MockTransport and catalog transport; SQLite + isolated PostgreSQL.
Cover zero-write options, first confirm/retry, explicit invalidation/idempotency,
real aggregate refresh/reconfirmation, current GET, strict inputs/CSRF/foreign/viewer,
role/session/source/privacy changes during IO and final waits, stale CAS/renamed event,
missing configured runtime and no response secrets/native IDs. No runtime getter
substitution for authority; only explicit infrastructure dependencies and provider mock.
No selected import orchestration, background continuation or provider capability claim.

## Final Freeze Refinements

State and explicit invalidation remain usable under original owner authorization
when billing or sync is paused: they cause no provider read and must not require
a purchase to revoke derived evidence. Paid/sync checks apply to options/confirm.
API constructs SelectedCustomerService(principal, provider, workspace_id, runtime)
BEFORE dependency rollback; constructor captures detached original identity/session
scalars. Then options(intent)/confirm(intent) own their sessions. State and invalidate
methods accept the caller DB, and API commits invalidate after its final local guard.
The resolver receives that detached original principal, never refreshed ORM identity.
