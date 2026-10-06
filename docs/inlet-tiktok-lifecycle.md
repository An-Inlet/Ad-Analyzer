# TikTok Authorization And Failure Lifecycle

Based on PR80 `392d08672a718f1d6450441a6fa141943862abb9`. This package does not
perform real provider calls, credential configuration, grant changes or deployment.

Current-attempt failure classification:
- Authenticated advertiser HTTP 401/403: stop the current connection, persist
  `reconnect_required`, clear unusable encrypted grant and incomplete pages,
  increment generation, unschedule imports and discard pending analysis in the
  exact workspace/integration/account scope. These statuses mean access is denied;
  they do not identify whether the underlying cause is revocation or permission.
- HTTP 429/5xx/network timeout: typed transient failure retains cursor/pages,
  uses existing five-minute backoff, and remains connected.
- Valid Business response with nonzero numeric code: preserve only the bounded
  integer diagnostic in `provider_rejected_<code>`, stop automatic reads in
  `provider_error`, clear incomplete staging, increment generation and discard
  scoped pending analysis. Previously published data stays intact. The encrypted
  existing grant remains for owner review until explicit disconnect/reconnection;
  no extra credential copy or retry queue is created. Unknown numeric codes are
  not guessed to mean expired token, rate limit or any other specific cause.
- Malformed responses/invalid pages remain semantic import failures, so the
  dispatcher resets staging with backoff rather than retaining a poisoned page.

Previously expired local grant bundles take the same terminal reconnect path.
Current workspace/connection locks and generation checks prevent old jobs from
invalidating replacement consent. No automatic provider-wide revocation occurs.
The typed current exception controls retry behavior, not a previous error marker.

## Token Renewal Evidence And Remaining Work

Readable official Business API SDK authentication documentation lists v1.3 code
exchange and authorized-advertiser discovery. It includes creator-token lifetime
prose but no advertiser refresh/rotation/revoke contract. Official Business portal
pages for authentication/error codes returned no readable content through the
browser; a direct public documentation fetch was denied by the environment proxy.
This is insufficient evidence to assert an indefinitely valid marketing grant or
that advertiser refresh endpoints do not exist.

Separately, TikTok's current user-token documentation specifies
`open.tiktokapis.com/v2/oauth/token/` and `/revoke/` for user scopes such as profile
and video access. Those are not substituted for advertiser Business API grants.
No guessed marketing refresh/rotation/revoke endpoint is added. Unexpected refresh
material returned at Business exchange is no longer retained because no qualified
consumer exists. Explicit access-token lifetime, when supplied, is still enforced;
absent lifetime remains unknown. Expired/denied grants require fresh consent.

Before a live release: obtain the current readable Business advertiser-token and
numeric-error specification; qualify renewal/rotation if supported, and implement
any grant-wide revocation only after affected-account ownership and user review are
represented. Unknown provider-code blocks need owner diagnosis/reconnect; no manual
"retry retained grant" action is currently implemented. These are actual remaining
implementation/qualification tasks, not merely credential setup gates.

Official references read October 6, 2026:
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/AuthenticationApi.md
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/business_api_client/api/authentication_api.py
- https://business-api.tiktok.com/portal/docs?id=1737172488964097
- https://business-api.tiktok.com/portal/docs?id=1739965703387137
- https://developers.tiktok.com/docs/en/oauth-user-access-token-management

The official SDK snapshot inspected was
`f809c396520df2d7b201a9ccc5378d822b728ed3`. Absence of a method in that SDK is
not proof the platform lacks it; current advertiser renewal/error-code qualification
is still blocked on the readable primary contract.

Customer source views now label provider_error as Provider Request Rejected with
an instruction to review provider access/configuration before reconnecting.
Reconnect-required has its own reconnection action. These small shared-view changes
were coordinated with the CRM agent and cherry-picked independently of CRM code.

Validation: 104 focused lifecycle/HTTP/source/review tests passed with explicit
SQLite/PostgreSQL coverage; the separate status-label test passed. Ruff, mypy (253
files) and diff checks passed. Final combined 105-test rerun also passed;
Full/hosted CI are not claimed. No live calls or deployment occurred.
