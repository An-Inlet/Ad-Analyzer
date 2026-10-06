# Google Disconnect UI

Child of frozen PR111 (`960de15cee97de54b88e3cb2bc33e59217c60915`). No migration,
provider request, remote grant revocation, advertising mutation or deployment.

Owners/admins select a Google account, review concrete data effects and explicitly
acknowledge them before disconnecting. Changing the selected account resets the review.
Disconnect remains available if provider configuration is unavailable: removing local
access does not require an external service. The canonical current user/session/role
guard now executes before the existing scoped disconnect locks and mutation.

The confirmation states what the backend actually does: removes this connection's
stored grant, stops imports, discards unfinished pages and pending analysis deliveries,
and retains historical campaigns/metrics/reports/goals/audit records without new
updates. Running Google campaigns and spending are unchanged. It does not delete Google
data or revoke grants used by other connections. Backend generation fencing and pending
analysis removal are unchanged.

## Verification

- Focused pytest: **55 passed**, including real Chromium/HTTPS/API/database journeys
  on SQLite and PostgreSQL, Google API/service tests and lifecycle regressions.
- The browser seeds real imported campaign/metric rows and a sibling connection;
  unchecked confirmation and cancel do nothing, role loss blocks DELETE, successful
  selected-account disconnect retains historical rows, clears grant/staging/scheduling,
  increments generation and leaves the sibling connected. No provider calls occur
  during disconnect. Consent and import transport remain deterministic fixtures.
- API coverage also verifies viewer and revoked-session DELETE requests leave the
  connection intact. Static checks and final focused results are recorded in the ledger.
- Full and remote CI pending; no live qualification claimed.

Focused command:

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_review_ci AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true pytest tests/test_google_connections_browser.py tests/test_google_customer_connections.py tests/test_google_lifecycle.py tests/test_customer_portal.py -o addopts='' -q
```

## Next Connection Package

In this branch, `customer_sources.py` already exposes authorize/callback/select/list/
disconnect for TikTok, Klaviyo, HubSpot and Omnisend. The portal only lists their status;
it lacks configured consent controls, usable selection and disconnect UI. The shared
callback uses the older generic relay. Meta is listed as unavailable and needs a separate
customer-owned flow around its existing operator API; it cannot be solved by a button.

Recommended next package: TikTok customer consent, typed setup metadata, dedicated
query-stripping callback/account selection and local disconnect UI, using mocked
consent HTTP and actual API/database browser tests. First define the shared source
lifecycle additions: optional post-exchange current-actor recheck, consistent workspace
before authorization locks, and retry invalidation restricted to provider/session/
workspace. Preserve existing provider exchange signatures and PKCE requirements.
After review of those interfaces, reuse the same customer flow for independently
configured CRM providers, with provider-specific URL validation and truthful data
retention effects. Coordinate with the CRM runtime owner before editing shared source
contracts/service; do not assume optional CRM providers are enabled by TikTok setup.

These are engineering gaps, distinct from subsequent production provider configuration,
consent approval and live qualification. Grant-wide remote revocation remains a separate
scope-aware design, not a side effect of per-account disconnect.
