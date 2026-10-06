# Meta Customer Connections

Implementation on an isolated child of PR118 `216fda2` plus PR120 `a4a66d5`. No
operator API token is required in the customer UI. Runtime remains disabled by default
through `AD_ANALYZER_META_CUSTOMER_ENABLED=false`, in addition to existing Meta app
configuration. No provider activation, live traffic, advertising mutations or deployment.

## Delivered Behavior

Owners/admins can navigate to configured Meta consent, return through a same-origin GET
callback bridge, page authorized accounts, explicitly choose a conversion event and
connect one Meta advertising account. The portal renders actual scoped connection state
and offers acknowledged local disconnect with concrete data effects. Disconnect stops
imports/removes local authorization and unfinished staging; historical data remains.
Running campaigns and spending remain unchanged. Existing single-account workspace and
cross-workspace external-account ownership constraints remain.

The OAuth destination is restricted to the fixed Facebook endpoint/version, exact
configured client ID, same-origin callback, ads_read scope and expected single query
parameters. Callback queries are stripped before session/CSRF-protected POST; CSP,
no-referrer and no-store protect the bridge. Errors require a fresh customer retry;
there is no blind authorization-code replay. No state/grant is placed in browser storage.

## Flow Identity And Compatibility

Migration **0045 down0042** adds explicit pending/exchanging/failed phases and a nullable
pending-grant nonce digest. Existing operator signatures, callback and legacy nullable
grants remain compatible. New customer selection/pagination reject unbound legacy grants.

The customer flow consumes pending into exchanging before external IO. After each
provider request it reacquires workspace-first current user/session/membership locks,
checks active identity, exact nonce/phase/expiry and connection generation. A retry
removes the old receipt, so an old exchange cannot overwrite a newer completed grant.
Unsuccessful exchanges become failed receipts and cannot exchange the code again.

Pagination releases locks during IO and rechecks exact grant ID/nonce/cursor and current
actor before storing another page. Customer account selection reuses the existing service
with an additive post-IO guard; it verifies the grant and connection generation again
before persistence. No invalid encrypted-grant placeholder represents a pending flow.

## Verification

- Focused SQLite/PostgreSQL/API/real HTTPS Chromium suite: **57 passed, 2 skipped**.
  The two skips are existing SQLite variants of PostgreSQL-only concurrency tests.
  This includes existing Meta operator tests, connection races/review locks, Google
  connection/disconnect and the billing browser journey.
- Final expanded customer Meta API suite: **22 passed** on both database backends.
  Cases cover retry interleaving at each exchange/discovery stage, preservation of a
  newer completed grant, failed receipt non-replay, revoked sessions, changed roles,
  selection/pagination post-IO fencing, incorrect state/account, nullable operator
  compatibility, reconnect generation, disabled configuration and local disconnect.
- Browser journey uses the real MetaClient with HTTP responses mocked before network,
  and intercepted consent navigation. It covers consent denial, Back/retry, stale
  callback, role loss at selection, explicit purchase conversion, successful return,
  acknowledged disconnect and callback history cleanup on SQLite and PostgreSQL.
- Node portal helpers: **10 passed**. Ruff, mypy (**325 files**) and diff check pass.
- Dedicated disposable PostgreSQL `inlet_meta_ui_0045`: upgrade to0045, downgrade to0042,
  upgrade back to0045 passed. Optional whole-schema `alembic check` still reports
  unrelated CRM target-metadata omissions and analysis_runs enum/VARCHAR differences.
  No0045 discrepancy was reported; parent is integrating the separate model registry fix.
- An initial focused command named a nonexistent billing test and collected no tests;
  the corrected command below produced the 57-pass result. An early browser harness
  run raced initial session loading on PostgreSQL; it now waits for enabled controls
  before login, and the corrected browser runs passed on both backends.

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_review_ci AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true pytest tests/test_customer_meta.py tests/test_meta_customer_browser.py tests/test_meta_connection.py tests/test_meta_first_connection_race.py tests/test_meta_review_locks.py tests/test_customer_portal.py tests/test_google_connections_browser.py tests/test_billing_browser_journey.py -o addopts='' -q
```

Full/hosted CI remain pending. Live Meta consent, app approval and production provider
qualification remain unverified. TikTok/CRM customer connection controls remain separate
engineering packages; account-wide remote grant revocation is not performed here.
