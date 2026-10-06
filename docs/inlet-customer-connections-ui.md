# Customer Connections UI

This package extends PR104 with customer-operated Shopify disconnection and Google
Ads authorization/account selection. Both provider factories remain disabled by
default. No migration, advertising action, provider activation or live qualification
is included.

## Customer Flow And Boundaries

An owner/admin can open Shopify's disconnect confirmation, read the data effects,
acknowledge them and disconnect through the existing scoped DELETE API. Imported
Shopify facts, measurements and stored authorization are removed. Saved goal/revision
history remains, but its erased baseline is unavailable and requires reconnection,
import and confirmation. Minimal privacy/audit records remain. This does not uninstall
the Shopify app remotely or change Shopify data or advertising campaigns. Canceling or
leaving the acknowledgment unchecked does not disconnect.

Google setup reports only public configured client/callback values and current role.
The portal permits only the exact Google OAuth endpoint and the expected configured
client, same-origin callback, scope and consent parameters. It rejects duplicate or
unexpected query keys. Consent navigates in the same window. The dedicated GET callback
bridge strips its query before exchanging through the session/CSRF-protected POST API;
its CSP, no-store and no-referrer policies match the Shopify bridge. An error query is
display-only and does not exchange a code. No nonce or grant is stored in browser storage.

The selection page displays verified advertiser account identity, currency and time
zone. Manager accounts cannot be selected directly. Selection binds to the workspace
returned by the server, and returns to that workspace only after a successful scoped
selection. A restored selection page requires restart. Google authorization permits
report imports through Inlet; it does not grant Inlet advertising spending authority.

The existing transactional Shopify guard is now shared without changing its lock
order: workspace, current user, session, membership. Google calls it before starting,
before and after exchange, and before account selection. Expired/revoked sessions or
role loss cannot persist a returned grant or select an account. Retry discards only
pending attempts for the current session/workspace; other sessions/workspaces and
selected receipts remain. Selection locks workspace before the authorization row,
matching retry's lock order. Existing account quotas and generation/lifecycle remain.

## Verification

- Focused pytest: **56 passed, 6 skipped**, PostgreSQL plus SQLite. Skips are existing
  SQLite variants of PostgreSQL-only concurrency tests, not browser skips.
- Real Chromium/HTTPS/API/database journeys on both backends exercise Shopify
  disconnect acknowledgment/cancel/data removal/retained unavailable goal baseline;
  Google canceled consent, Back/retry, stale callback rejection, manager filtering,
  current role loss, changed customer session, successful account selection and
  callback history cleanup. Browser consent HTTP is fulfilled locally before network;
  Google transport is a deterministic grant fixture, with no report/ad calls.
- Additional API tests revoke a session or remove its role during exchange and verify
  no encrypted grant or connection persists. Retry isolation is tested across sessions
  and workspaces, including preservation of selected receipts.
- Node portal helpers: **8 passed**, including configured Google URL validation.
- Ruff, mypy (**290 files**) and `git diff --check` pass.

Primary focused command:

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_review_ci AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true pytest tests/test_google_connections_browser.py tests/test_customer_browser_api_journey.py tests/test_shopify_consent_browser.py tests/test_customer_shopify.py tests/test_google_customer_connections.py tests/test_customer_portal.py -o addopts='' -q
```

Full and remote CI remain pending. Real Google consent, approved project access,
production app setup and live import freshness are not verified. Google disconnect
controls and other providers' self-service connection controls remain customer UI
engineering work; provider grant-wide revocation still requires scope-aware orchestration.
