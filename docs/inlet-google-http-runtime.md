# Google Read HTTP Runtime Preparation

Branch: `codex/inlet-google-runtime`, based on Stripe runtime preparation
`694e3388254d0fcffd76e11eb84c8313f718da75`. This is offline implementation, not live
verification. No provider calls, credentials, deployment, or advertising writes occurred.

`GoogleHTTPRead` implements OAuth authorization-code exchange, refresh-token exchange,
accessible-account and manager hierarchy discovery, and account-scoped Google Ads REST
Search pagination. Calls are restricted to fixed Google endpoints. Account IDs and
manager routing are validated, discovery is bounded, response bytes/page sizes are
bounded, redirects and environment proxies are disabled, and timeouts/errors are
sanitized. Access tokens remain transient. Existing service vault, session-bound
OAuth state, owner/account selection, generation fences and imports remain in place.

The factory defaults to unavailable. Enabling requires explicit
`AD_ANALYZER_GOOGLE_CUSTOMER_RUNTIME_MODE=google_read`, an explicitly pinned
`AD_ANALYZER_GOOGLE_CUSTOMER_API_VERSION`, existing customer client ID, and secret
setting `AD_ANALYZER_GOOGLE_CUSTOMER_CLIENT_SECRET`. Legacy
`AD_ANALYZER_GOOGLE_CUSTOMER_DEVELOPER_TOKEN` is optional for compatibility. Setting up these values or enabling
runtime in a deployed environment still requires the separate live approval gate.
Google's adwords OAuth scope is not intrinsically read-only; this adapter exposes only
read searches and token exchange. It contains no advertising mutation endpoint.

Verified against mocked HTTP: disabled/configured factory, code exchange, refresh,
manager context, 10,000-row pagination, metrics defaults/micros, wrong account,
malformed/repeated pages, invalid cursor/token/scope, missing offline consent,
response bounds, timeout and 301/400/401/403/429/500 sanitized failures.

Remaining implementation/acceptance gaps: provider token revocation lifecycle (local
disconnect already invalidates generations), customer portal OAuth/reconnect journeys, deployment
scheduler qualification, and live authorized account reconciliation. API version
availability and provider approval must be verified at release. Token refresh is
per-page without a shared cache; retries remain job-level and bounded by scheduler
policy. This change does not claim complete B08 acceptance.

Official references consulted October 6, 2026:
- https://developers.google.com/google-ads/api/rest/common/search
- https://developers.google.com/google-ads/api/rest/auth
- https://developers.google.com/identity/protocols/oauth2/web-server

Validation: 33 focused tests passed (22 HTTP contracts plus 11 customer
connection cases, including explicit disposable PostgreSQL variants); Ruff passed;
mypy passed across 248 source files; `git diff --check` passed. Full validation and
hosted CI have not been run for this isolated branch.


Late-conversion followup: once caught up through account-local yesterday, refresh
90 days newest-first in seven-day windows. Phase stays `refresh` until the fixed
snapshot window is covered; new days are caught up before starting another cycle.
Refresh pages remain immediately due, and the next completed cycle is delayed an
hour. Atomic window replacement updates positive conversions/revenue and downward
corrections to zero, without touching another customer account. Regression coverage
runs on SQLite and PostgreSQL. The 90-day horizon follows the existing B08 history
floor; longer provider adjustment windows remain a release policy qualification.
`last_sync_at` continues to mean the last completed window, not complete-cycle
freshness; the phase indicates ongoing refresh.

PR73 review-repair head `7b7ab2963b79e23d99f945dc83624da6584cab93` was merged
cleanly. Post-merge validation: 73 Google/review regressions passed with explicit
disposable PostgreSQL enabled; Ruff, mypy (248 files), and diff whitespace checks
passed. Full/hosted checks remain outstanding for this head.
