# TikTok Customer Journey — Shared Interfaces

Implemented offline on `codex/inlet-tiktok-customer-ui` from `f77553b`. No migration
or live provider calls. Existing workspace-first authorization locking and fresh ORM
reads are preserved. This records the reviewed contract and its original gaps.

## Existing State And Gaps

The launch TikTok runtime already builds the fixed Business API consent URL, exchanges
an auth_code, verifies advertiser metadata, imports scoped reports and classifies
provider failures. It is disabled by default. `SourceAuthorization` already has an
exact nonce, provider, customer session, workspace, expiry, phase and selected receipt;
no new schema is needed for the customer journey.

Missing work: a configured portal connect control, usable GET callback/account selection,
local disconnect controls, exact destination validation, pending-attempt replacement,
and canonical current-role/session rechecks after exchange. The existing generic callback
is incorrectly Google-branded, writes the nonce into sessionStorage and tells customers
to select an account without providing a selection UI. CRM providers share these APIs
but remain later UI packages and must not be enabled through TikTok configuration.

## Customer API / UI Contract

- Add GET `/api/customer/v1/workspaces/{wid}/sources/tiktok_ads/setup`: membership-scoped,
  no-store, `enabled`, `can_manage`, public `app_id`, exact same-origin `redirect_uri`,
  fixed `authorization_endpoint`; never credentials. Availability uses only the
  TikTok factory/configuration and source encryption readiness, with no network calls.
- Existing POST `/sources/tiktok_ads/authorize` returns `authorization_url` after the
  canonical mutation guard. Portal navigates in the same window only if URL is HTTPS
  `business-api.tiktok.com/portal/auth`, has no credentials/nondefault port/fragment,
  and contains exactly one configured app_id, exact same-origin callback, and nonce.
  Reject all unknown/duplicate query parameters; no user-supplied destination.
- GET `/api/customer/v1/sources/tiktok_ads/callback` serves a dedicated external-script
  bridge with query stripping, no-store/no-referrer/frame denial/CSP. Accept exactly
  one state and one auth_code; reject the code alias and all duplicates. Error query is display-only and performs no exchange.
- Bridge POSTs existing `{state, code}` with current cookies/CSRF. Server resolves
  workspace only from the exact session-bound nonce. Response stays `{workspace_id,
  accounts, mode, live_verified:false}`; no grant/cursor is exposed or browser-stored.
- Display authorized advertiser name/ID/currency/time zone and POST the chosen ID to
  existing workspace/provider `/select`. Return to server-verified workspace only
  after success. Account selection performs no new provider IO. Preserves account
  quota, customer ownership, integration scope, generation and replay checks.
- Render per-account disconnect confirmation with truthful consequences: remove local
  stored authorization, stop imports, clear unfinished pages/pending analysis, retain
  historical campaigns/metrics/goals/audit records. Running TikTok campaigns/spending
  are unchanged; no remote or grant-wide revocation. Existing scoped DELETE plus
  canonical current actor guard remains available while runtime setup is disabled.
- Add `external_id` to safe SourceConnection view for account identification; render
  existing reconnect_required/provider_error labels and next_action rather than generic
  unavailable. Show conversions/revenue as unqualified/unavailable, never Shopify sales.

## Shared Service Changes To Freeze First

Keep `SourceTransport.authorize_url`, `exchange`, `read`, PKCE signatures and the
AdvertisingPage schema unchanged. Reuse current successor workspace-first locking.

1. `begin`: after canonical actor guard, replace only unselected attempts for the same
   provider/workspace/session. Keep selected receipts and other customers/browser flows.
   Preserve PKCE context; use fetch synchronization for timestamp-based cleanup.
2. Add optional `before_persist: Callable[[], None]` and fresh-time callback to `finish`.
   Pending -> exchanging is committed once before external IO. After exchange, canonical
   workspace/user/session/membership plus active-identity checks run, then exact nonce,
   phase, provider and expiry are reacquired and validated before storing credentials.
   Retry deletes the old nonce, so an old callback cannot overwrite a newer grant.
   Failure marks the same still-current attempt failed; customer starts fresh rather
   than blindly replaying an authorization code. No grant placeholders.
3. For TikTok's two-request exchange (token then advertiser metadata), add an optional
   structural `GuardedSourceExchange` capability: `exchange_guarded(code, redirect_uri,
   checkpoint: Callable[[], None]) -> SourceGrant`. TikTokHTTPRead implements it using
   per-call callbacks, never mutable adapter-level actor state. Checkpoint runs after
   each successful provider request, checks current actor/exact exchanging receipt,
   then releases locks before the next request. Existing exchange delegates without
   a guard for operator/fixture compatibility. CRM PKCE flow remains unchanged until
   its own reviewed guarded capability is implemented.
4. Customer APIs perform canonical guard before authorize, callback, selection and
   disconnect. For callback, look up the session/provider-bound reference without
   locking it first, then canonical workspace-first guard and fresh authorization.
   Use an additive `authorization(..., lock=False)` reference option if necessary;
   default existing locked behavior remains unchanged.
5. Declare TikTok runtime provider identity and enforce provider_read transport identity
   in `ready`, matching the existing CRM mismatch safeguard. Fixture compatibility is
   explicit. Enabling TikTok must never authorize optional CRM adapters.

## Required Verification

Actual HTTPS Chromium + API/database on SQLite and PostgreSQL; browser consent HTTP
intercepted before network; real TikTokHTTPRead with mocked provider HTTP. Cover consent
cancel, Back/retry, stale callback, exact callback parameter validation, session/role loss
between token and advertiser discovery and before selection, current flow replacement,
unauthorized advertiser, replay, disconnected setup availability, sibling preservation,
retained metrics and truthful status. Deterministic synchronization for initial session
loading and ready Chromium targets must use the already-reviewed harness repairs.

Shared API/service tests must preserve CRM PKCE behavior and provider isolation. No
schema work proposed. Full and provider live qualification remain parent-owned gates.

## Verification And Remaining Gates

The shared source/CRM/TikTok regression batch passed 178 tests with 14 existing
SQLite concurrency skips. The browser/customer API/source/status/portal batch
passed 34 tests against SQLite and PostgreSQL. Both TikTok browser cases use real
HTTPS, application APIs and persisted database rows, with consent intercepted and
provider HTTP mocked. They verify cancellation, Back/retry, alias rejection, stale
callbacks, role/session changes, account selection, retained reporting rows and
sibling isolation after local disconnect. JavaScript helper tests: 11 passed.

Callback response headers and the installed Uvicorn access-log filter explicitly
cover auth_code; the filter suppresses all customer callback requests regardless
of query parameter name. Browser assertions check stripped history and absence
of authorization code in console/error messages, storage and referrer.

TikTok remains disabled by default. Real Business API grants, app approval,
account-specific conversion/revenue qualification and production consent validation
remain unverified. This package adds no campaign mutation, remote revocation,
refresh endpoint or spend authority. CRM-specific callback/selection UI remains
engineering work; its existing PKCE exchange signatures are preserved. Full/hosted
CI and integration review remain pending.

Final customer API/access-filter plus adjacent Google/Meta browser regression:
**19 passed, zero skips**. Whole-tree Ruff, mypy app tests (362 files) and diff check passed.
