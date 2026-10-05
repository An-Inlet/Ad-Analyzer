# B08 Customer Google Connection Preparation

This package prepares the customer lifecycle using an injected fixture-only transport.
The default transport rejects authorization/imports with unavailable status. It is not
an operational Google connector, an app approval, or live-verified account access.
The existing operator Google collector remains intact and separately scoped.

## Shared Interface

`GoogleReadTransport.exchange(code, redirect_uri)` returns a validated encrypted-grant
input and accessible leaf accounts. `page(refresh_token, account_id, start, end, cursor)`
returns bounded campaign metadata and daily campaign metrics plus continuation.
Requests never infer a workspace, connection or account. No mutation method exists.

The authorization URL follows Google's web-server consent flow. Pending state binds
one current customer session and workspace, expires after ten minutes and is consumed
before exchange. Only owner/admin may connect, select or disconnect. Selection is
limited to returned leaf accounts. Grant ciphertext binds workspace and grant/connection
context. Reconnect keeps owned account identity, rotates the generation and discards
old partial pages; stale queued generations are rejected. Disconnect clears stored grant
and partial pages and revokes the associated integration. It does not revoke the user's
provider grant or pause advertising. The callback relay preserves Strict session cookies,
uses the existing same-origin CSRF-protected POST and clears the callback URL.

Imports publish a complete bounded window atomically, deduplicate page rows, reject
conflicting/repeated cursors and mismatched accounts, and create explicitly scoped jobs.
The first window is the most recent seven complete account-local days; older windows
extend to 90 days, then hourly eligibility checks allow subsequent days. Partial pages
are not authoritative metrics. Imports use campaign metrics only; child detail is a
later package. Provider-attributed conversions are never canonical Shopify revenue.
A durable completion record retries analysis independently of successful ingestion.
The existing post-sync analyzer's unique source-job key prevents duplicate analysis.
Dispatcher eligibility filters run before the batch limit; failed tenants do not stop
other selected tenants. Grants expire and are purged on authorization/dispatcher runs.

## Live Release Requirements

The wire adapter has fixed token-exchange request construction, bounded manager-account
traversal with selected manager context, campaign paging and daily metric parsing tested
through injected offline IO. It is deliberately absent from runtime selection. Qualify
the provider SDK factory, refresh/rotation, transport timeouts and revocation classification
before advertising B08 as complete. Live OAuth needs approved project,
client callback and developer token setup, secure key configuration/rotation and real
unrelated-account reconciliation. A broad Google Ads OAuth scope is not read-only
permission enforcement; this package has no write interface and does not authorize one.
Fixture-only implementation must never be enabled as a production connection.

Official design references reviewed 2026-10-05:
- [Google Ads OAuth overview](https://developers.google.com/google-ads/api/docs/oauth/overview)
- [Web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Accessible accounts](https://developers.google.com/google-ads/api/docs/account-management/listing-accounts)

## Checks And Follow-up

SQLite/PostgreSQL fixtures cover two unrelated customers, ciphertext context binding,
state/session/expiry/replay, CSRF/current roles, partial retry, reconnect generations,
disconnect, wrong-account rejection, 90-day backfill and analysis outbox retry. Required
Full/CI results belong to the exact package commit and are recorded in its draft PR.
B18 must finish the customer account-selection UI; B19 must wire disabled-by-default
worker scheduling and release configuration. No deployment or live provider call occurs.
