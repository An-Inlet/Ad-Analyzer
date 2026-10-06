# Meta Customer Connections — Interface Proposal

Proposal only, after PR120 Google disconnect. No implementation or migration yet.

## Existing Reusable Behavior

`app/meta/service.py` already owns encrypted Meta grants, read-only scope checks,
authorized account pagination, account ownership, conversion-event selection,
integration quota checks, verified reconnect generation and local disconnect.
`MetaClient` uses fixed Graph endpoints with bounded responses/timeouts. Preserve its
signatures and operator flows. Existing limitations: one Meta account per workspace,
and an external Meta account cannot belong to another workspace. Display these limits.

`configuration_ready` currently accepts only the operator `/dashboard/meta/callback`.
Customer setup must use its own exact same-origin `/api/customer/v1/meta/callback`,
with a separate disabled-default customer flag. Customer never supplies an operator
API token or credentials. Runtime factory derives a Settings copy with this exact
callback, leaving operator configuration unchanged.

## Proposed Customer API

All workspace paths under `/api/customer/v1/workspaces/{workspace_id}/meta`:

- GET `/setup`: public client ID, fixed callback, fixed consent endpoint/scope,
  enabled, can_manage, supported conversion-event choices and one-account limit.
- POST `/authorize`: current session/CSRF/owner-or-admin guard; begin exact session-
  bound nonce. Replaces only this workspace/session's pending flow.
- GET `/api/customer/v1/meta/callback`: dedicated external-script bridge; strips
  query immediately; CSP/no-store/no-referrer. Error query is display-only.
- POST same callback: `{state, code}`, current session/CSRF, workspace derived only
  from server nonce; returns workspace, authorized accounts and whether another page
  exists. No provider cursor/token exposed.
- POST `/accounts`: `{state}` loads next authorized account page under current actor
  and nonce, preserves bounded page size, returns safe account metadata.
- POST `/select`: `{state, external_account_id, conversion_action_type}`; require
  exact current nonce/grant and current role/session; existing service selects only
  returned account. Reconnect increments existing explicit generation.
- GET connection and DELETE connection: scoped membership/current mutation guard;
  truthful data-effects confirmation. Existing disconnect removes local connection,
  clears staging via cascade and revokes integration; retained account/report history
  is not claimed erased. No remote grant revocation or campaign/spend modification.

Browser destination validator requires fixed Facebook HTTPS endpoint/version, exact
configured client/callback/ads_read/response_type/auth_type and one bounded state;
unknown or duplicate query keys rejected. State remains in memory, not browser
storage. Return workspace comes from verified response. Show currency/time zone and
explicit conversion selection; never silently treat unknown conversions as zero.

## Required Shared Service Repair Before UI

Current `finish` deletes MetaOAuthState before external exchange, then replaces the
workspace/actor pending grant without a nonce check. Current pending-grant model only
stores actor/workspace. A retry while exchange waits can therefore be overwritten by
an older callback. A route wrapper alone cannot close this race.

Recommended small additive migration (number assigned by parent):

- MetaOAuthState.phase: pending | exchanging, default pending.
- MetaPendingGrant.oauth_state_digest: nullable bounded digest, populated for new
  flows; old operator grants can remain nullable until consumed/expired.

`finish` atomically transitions pending to exchanging and commits before external IO.
After exchange/permissions/discovery, optional `before_persist()` reacquires canonical
workspace→user→session→membership locks, verifies provider identity active, then locks
and rechecks exact nonce/session/workspace/phase/expiry. Retry deletes/replaces the
nonce; stale exchange cannot persist. New pending grant stores the exact nonce digest.
Delete consumed state only after persistence. Customer select/pagination require the
provided nonce digest match this grant; operator compatibility remains explicit.

Service callbacks/optional arguments are additive: `finish(..., before_persist=None)`;
`more_accounts(..., expected_state=None, before_persist=None)`;
`select_account(..., expected_state=None)` with customer routes always providing it.
Never hold a stale principal as authority across network waits. Pagination should
snapshot grant ID/nonce/cursor, release transaction during HTTP, then recheck current
actor and same grant/cursor before applying the page. Workspace lock precedes grant
and connection locks throughout begin/finish/select/disconnect.

Avoid empty encrypted-grant placeholders as a phase mechanism: they blur valid-grant
semantics and rely on decryption failure for safety. An explicit phase/digest is easier
to audit and test. Parent review required before schema implementation.

## Acceptance / Verification Plan

Actual HTTPS Chromium + real API/database on SQLite and PostgreSQL, with consent HTTP
intercepted before network and real MetaClient parsing mocked HTTP: denial, Back/retry,
callback query cleanup, duplicate callback, retry during exchange, role/session loss
during exchange/pagination and selection, exact nonce matching, unauthorized account,
conversion choice, one-account limits, reconnect generation and scoped disconnect.
Assert no advertising calls and no old grant surviving superseding flow. Keep existing
operator tests passing. Full owned by parent; no live provider calls or activation.
