# Durable CRM Renewal

Offline, disabled-default provider-runtime preparation on top of PR93. No customer
profile scheduler, live grant or provider revocation is added. Existing acknowledged
Klaviyo pacing now supports the same explicit boundary for HubSpot and Omnisend.

## Shared Interfaces

`CRMHTTP.issue_refresh(refresh_token) -> RefreshCandidate` performs the documented
token exchange and validates response structure. The frozen candidate is **unverified**.
`prove_refresh(candidate, expected_account) -> SourceGrant` proves the original account
and read scopes; HubSpot also proves active status, client and access-token use through
its authoritative introspection endpoint. Klaviyo/Omnisend validate token-response
scope before staging; omitted Omnisend renewal scope retains the original grant under
OAuth rules. No pending candidate can authorize a profile read or replace the source
grant before proof succeeds. Existing combined `refresh()` methods remain compatible;
durable orchestration uses the split interface instead.

`read_page(db, workspace_id, connection_id, generation, reader, now)` runs at most one
phase and returns an acknowledged page, a deferred timestamp, or completed `None`.
`acknowledge_page(..., provider="klaviyo")` retains its legacy default; HubSpot/Omnisend
callers supply their provider. Concrete adapter provider must match the scoped source.
No user-supplied token, provider URL or account ID becomes authority proof.

## Durable State And Fencing

State transitions use existing CRMCheckpoint/CRMQuota tables; no migration is required.

1. A known near-expiry token, or one failed read authorization, requests renewal.
   Unknown expiry never creates a fabricated deadline or automatic renewal.
2. Commit `refreshing`, a unique dispatch fence and a 120-second lease before the token
   request. This marker means a rotating refresh token may have been consumed.
3. On success, reacquire scoped source locks and verify generation, existing grant digest,
   checkpoint fence and lease. Encrypt the candidate in checkpoint progress and commit
   `proof_ready`. The old validated grant remains separate.
4. A later reserved quota slot performs only account/scope/client proof. On success,
   install the new encrypted source grant and checkpoint grant digest atomically. Retain
   generation, acknowledged cursor, seen-cursor hashes and page count.
5. A third later slot may read profiles, including its usual fresh authority proof.

The quota key includes provider, configured client and external account. Token issuance,
renewal proof and page proof each reserve a slot; there is no proof burst hidden inside
refresh plus page. The conservative 4.1-second spacing also protects Klaviyo's 15/minute
account endpoint. This is not a claim that all provider limits are live-qualified.
Initial authorization and callers bypassing this explicit boundary remain outside it.

Reconnect/disconnect deletes the scoped checkpoint, including pending credentials.
A late worker cannot overwrite a new generation or grant. Access-token renewal alone
does not increment source generation or reset a valid cursor. Live pending leases defer
other replicas; an expired `refreshing` marker requires attention, never reissuance.

## Failure Rules

- Explicit OAuth `invalid_grant`, failed authoritative account/scope/client proof,
  missing required refresh token, or read authorization failure after a successful
  forced renewal: `reconnect_required`, remove source credentials and scoped checkpoint.
- Token POST timeout, 429, 5xx, arbitrary 4xx or crash before candidate commit:
  `provider_error` with `renewal_uncertain`, remove unusable local credentials/candidate,
  require reconnect guidance. No request is blindly replayed: no provider-specific
  no-issuance guarantee was verified. This is **not** a claim of provider revocation.
- Read-only pending proof 429/5xx/network failure: retain the encrypted candidate and
  cursor, record durable cooldown, then safely retry proof without another token POST.
- Ordinary profile/account transient failure: preserve connected state and durable
  backoff. 429 uses bounded Retry-After; other failures use 60 seconds. Authorization
  failure schedules at most one refresh before terminal attention.

No error payload, token, raw profile or customer address is logged or persisted in a
plaintext field. Only encrypted progress, opaque fences/digests and sanitized statuses
are retained. Pending credentials are not represented as installed or verified grants.

## Verification

`pytest -o addopts='' -q tests/test_crm_renewal.py tests/test_crm_pacing.py
 tests/test_crm_http_runtime.py tests/test_omnisend_http_runtime.py
 tests/test_customer_context.py tests/test_tiktok_sources.py`
with explicit disposable PostgreSQL: **148 passed, 3 skipped**, two existing Alembic
configuration warnings. The three skips are SQLite-only concurrency tests; their real
PostgreSQL counterparts ran. Log: `/tmp/inlet-renewal-final.log`.

Fixtures exercise actual HTTP construction and DB replicas: all three providers,
rotating credentials, separate proof retry, acknowledged cursor continuity, concurrent
worker deferral, reconnect during issuance and proof, crash after token success before
candidate commit, unknown/malformed expiry, foreign workspace/provider/brand denial,
disconnect cleanup and one-refresh authorization recovery. Ruff, mypy (275 source files)
and whitespace checks passed. Full and hosted CI are pending integration coordination.

Remaining: real grants and provider qualification, approved canonical customer matching
and retention, scheduler enrollment, and provider revoke orchestration. This package
implements durable renewal/read lifecycle only; it does not imply B12 or SaaS launch
acceptance.

## Review Repairs: Shared Cooldown And Client Binding

A synchronized PostgreSQL fixture reproduced a 429 with Retry-After 3600 lost
when a customer reconnected before the response returned: another workspace using
the same provider account could read after the 120-second lease. Completion now
commits a quota-only transaction before reacquiring source locks. Every observed
429 extends the original account quota conservatively, even after the old lease
fence is superseded; only the matching fence can release a lease. Stale responses
still cannot install credentials, candidates, or cursors. This separate transaction
avoids reversing the source-then-quota lock order used when dispatching requests.

Pending renewal candidates now include their issuing OAuth client ID and original
account quota HMAC inside encrypted checkpoint progress. Proof and proof retries
require both identities to match the configured reader. A changed client or missing
binding requests reconnect before HTTP; there is no invented Klaviyo/Omnisend token
introspection. HubSpot's authoritative introspection checks remain. Same-client
rotation retains cursor/generation continuity. No schema migration is required.

Omnisend's [official contact contract](https://api-docs.omnisend.com/reference/contacts)
maps email identifiers to email and phone identifiers to SMS. A typed identifier
with absent, null, or empty channels now contributes unknown status to that channel,
so a second subscribed identifier cannot erase that uncertainty. Existing explicit
conflicts remain unknown; address and phone values are not retained.

The [Omnisend rate-limit contract](https://api-docs.omnisend.com/reference/rate-limit-timeouts-errors)
and [pinned official SDK parser](https://github.com/omnisend/wp-omnisend/blob/fdfc72021e90d3fb333e7c1b2d77017dc69f850d/omnisend/includes/Internal/class-apiresponse.php#L151-L153)
also document a JSON `retryAfter` delay. On actual HTTP 429, the adapter accepts a
nonnegative integer from at most 16 KiB of response bytes, caps it at 86400 seconds,
and uses the maximum of that value and the bounded header/default. Invalid values,
malformed/oversized bodies and stream errors preserve the header/default. Token
issuance 429 remains uncertain and is never blindly retried.

Omnisend quotas now use a brand-only HMAC namespace (`crm-quota-brand-v2`), matching
the documented limit shared across OAuth clients and integrations. Other providers
retain their existing client/account key. Candidate client binding remains separate.
No production runtime has been enabled by this work. **Deployment requires quiescing
old workers and honoring any outstanding cooldown before enabling the new binary**:
legacy app-partitioned keys cannot provide safe mixed-version rolling operation.
This is a live rollout gate, not an assertion that old quotas have been migrated.
