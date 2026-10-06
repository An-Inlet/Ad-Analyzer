# Shopify Portal Consent Flow

The customer portal now exposes an owner/admin store-domain form when customer Shopify
setup is configured. Other members receive a read-only explanation. Existing API
configuration defaults remain disabled. The form accepts the canonical store
`myshopify.com` domain, calls the CSRF-protected authorization endpoint, and validates
that navigation stays at that exact shop's HTTPS `/admin/oauth/authorize` endpoint.
It does not accept a caller-supplied redirect destination or authorize advertising spend.

Shopify returns to the existing public GET callback bridge. Its external module removes
query material from history before handling it. No-referrer, no-store, frame denial and
restricted CSP headers remain. A signed success query is submitted to the real customer
POST callback with the current session/CSRF token; successful return selects only the
workspace ID obtained from that verified server response. The portal checks it against
current membership and removes the selection query from history.

An untrusted provider error query is display-only and never triggers code exchange.
Explicit cancellation calls a new CSRF-protected endpoint which deletes only the current
session actor's stored, unexpired nonce after current workspace/role/session checks.
A stale nonce, other session or missing CSRF cannot cancel another attempt. The return
workspace for cancellation also comes from that server-owned state. Missing callbacks,
replay, expiry, session changes and failed exchanges show a restart/return action rather
than automatically resubmitting. A fresh authorization attempt replaces the prior nonce
for the same actor/workspace. Back-forward restoration refreshes the customer session.

Official standalone-app OAuth guidance checked on 2026-10-06:
https://shopify.dev/docs/apps/build/authentication-authorization/authenticate-standalone-apps
The existing server continues to verify HMAC, shop, timestamp, one-time nonce and current
session/ownership before persisting credentials. This package does not broaden scopes.

## Validation

The new Chromium regression navigates the actual portal form through a mocked Shopify
consent HTTP document and the real GET bridge, POST API and database. Chrome DevTools
intercepts the exact fixture Shopify authorization endpoint before network access;
external DNS is blocked. Token and metadata HTTP use a mocked transport under the real
Shopify client. No provider or merchant is contacted.

Both SQLite and PostgreSQL cover denial remaining display-only until explicit cancel,
nonce deletion, Back/retry replacing the old attempt, rejection of an old signed return,
a second-tab customer session change while consent is pending, and successful return to
the selected workspace. Token/metadata exchange occurs only for the final valid attempt.
Browser history contains no authorization code or HMAC after the bridge. Existing PR95
direct callback, tampering, CSRF, replay, import and disconnect regressions are retained.

Combined consent-navigation/customer-Shopify/portal/browser-API suite: 37 passed,
6 skipped (PostgreSQL-only cases' SQLite variants). Ruff, mypy (289 files), and diff
checks passed. The browser harness explicitly declares its WebSocket dev dependency.
Full and hosted CI remain pending. No live provider qualification, deployment or spending.

Remaining connection UI work includes disconnect/deletion confirmation and wider
provider onboarding. Provider configuration/approval and a real merchant consent journey
remain live release gates; the code and local navigation flow are implemented and tested.
