# Selected Event Customer Confirmation Interface V1

This defines the next offline customer service boundary. It is not implemented or
activated. Dependencies are the reviewed selected contracts, internal 0091 storage,
and injected Google reporting catalog. Publication catalogs and approvals cannot
supply reporting-event authority. No advertising writes are permitted.

## Original Session And Owned Discovery

Use the existing customer mutation principal, CSRF and workspace → user → session
→ membership authorization fences. Capture the original identity and session; never
adopt a replacement session during an operation. Load account/source scope on the
server. Close transactions before Vault/OAuth/provider I/O and reauthorize in fresh
independent sessions afterward. Recheck clocks after authorization waits.

Discovery accepts only an account ID. It returns opaque options bound to the exact
actor/session, source scope, observed label, event resource and explicit metric
family/profile. IDs support comparison, not authorization. Do not expose native
resource paths, session digests, grants or client-authored scope. Responses are
`Cache-Control: no-store`; discovery uses POST and existing paid-read/sync controls.

Google uses the separate v24 reporting catalog, with both `conversions` and
`all_conversions` as deliberate choices. No family is preselected. Duplicate display
names remain distinct; manager-owned actions are unsupported. Configured profile or
developer-token incompatibility returns unavailable. Fixtures do not prove provider
compatibility. TikTok has no selected-event confirmation until mapping is qualified.

## Confirmation And Explicit Invalidation

Confirmation accepts account ID, opaque option ID and the paired expected current
selection ID/digest (both null for first confirmation). Fresh complete discovery
must reproduce that option under the same original session and current owned scope.
At commit, repeat authorization and scope/head checks under the existing lock order,
then create the server UUID/time and call the 0091 storage port. Stale role, session,
scope, event, profile or expected head writes nothing. A still-current identical
choice can return the unchanged stored selection after fresh discovery; never
silently create duplicate history or readopt an old selection.

Changing an active selection requires a distinct, explicit customer invalidation
request with the exact expected head. Under authorization and the workspace fence,
invalidate once and commit. This erases obsolete selected/derived evidence and
advances the existing privacy counter. Return Refresh Required; do not attempt a
new confirmation in the same transaction or automatically choose the replacement.
Retries against the same invalidated head are idempotent. A genuinely refreshed
aggregate and new discovery/confirmation are required before replacing that head.
Old immutable selection bytes remain historical, never restamped as current.
At replacement commit, verify the actual current aggregate completion and recomputed
manifest carry the post-invalidation privacy revision. Checking only current source
scope and the invalidated head is insufficient: the internal selection storage port
does not itself require an aggregate refresh.

The receipt confirms a choice only: selection ID/digest, account, confirmation time,
fresh display label, explicit family/API version, and `spending_authorized=false`.
No new label persistence table is required. A later GET reads stored current state
without provider I/O and may omit a label that is no longer freshly known.

## Selected Reads And Finalization

Construct the aggregate dependency, stored selection and complete campaign map from
owned server data. An injected context resolver decrypts the exact workspace/source
grant and refreshes outside a transaction. Repeat original-session, grant, source,
privacy, current selection and full aggregate-manifest checks after refresh and at
every selected-reader revalidation. Token expiry starts before refresh, not after;
never extend the operation or session deadline. No cross-request token cache.

Finalization repeats the same checks under locks before storing the complete capture
and committing. A DTO, valid access token or completed HTTP read is not finalization
authority. This does not authorize background continuation after session expiry or
invent missing date-range provenance. Those need separate explicit interfaces.

## Required Evidence

Use actual original-session, encrypted test-grant and SQLite/PostgreSQL fixtures with
injected HTTP. Cover CSRF/foreign access, role/session rotation around I/O and commit,
source/privacy/aggregate changes, rename/removal, clock expiry after locks, exact
retry, CAS races, invalidation retry, rollback and response secret exclusion. Public
routes and plan consumers remain unavailable until these dependencies are reviewed.
No Q01/Q02 completion, live verification or purchasable-release claim follows from
this interface.
