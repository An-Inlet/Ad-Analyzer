# Customer Shopify Connections

Customer routes use revocable customer sessions and active workspace membership:

| Route | Behavior |
| --- | --- |
| GET `/api/customer/v1/workspaces/{workspace_id}/shopify` | List the scoped connection, without credentials |
| POST `.../shopify/authorize` | Owner/admin plus CSRF; body `{"shop":"example.myshopify.com"}` |
| GET `/api/customer/v1/shopify/callback` | Static same-origin callback relay |
| POST `/api/customer/v1/shopify/callback` | Session-bound signed query pairs, owner/admin plus CSRF |
| DELETE `.../shopify` | Owner/admin plus CSRF; disconnect and existing local privacy purge |

Callback POST accepts `{"query":[["state","..."],...]}`. The relay preserves all
query pairs, including duplicates, so existing Shopify HMAC, timestamp, shop and
state validation stays authoritative. No query data is interpolated into HTML,
logged, persisted in browser storage or sent outside the same origin. Query text
is removed from browser history; CSP pins the static script by hash.

## Configuration And Live Gates

`AD_ANALYZER_SHOPIFY_CUSTOMER_ENABLED=false` by default. Enabling requires the
existing Shopify read-only application configuration and an HTTPS
`INLET_CUSTOMER_APP_ORIGIN` with no path, credentials, query or fragment. The
customer redirect is fixed to that origin plus `/api/customer/v1/shopify/callback`.
The existing `SHOPIFY_REDIRECT_URI` and operator dashboard flow are preserved.
Registering the additional callback, granting scopes, credentials and deployment
remain owner-operated live gates; this package does none of them.

The existing real Shopify client performs bounded HTTPS code exchange and shop
identity/scope verification. Tests inject a fake client; no provider call has been
made. Measurement-enabled setup requests the existing measurement scopes, binds
canonical store identity and reuses the existing privacy lifecycle on disconnect.
Disconnect removes local credentials and facts, marks canonical store identity
revoked, and preserves privacy tombstones; merchant uninstall/provider revocation
is distinct from local disconnect.

## Concurrent Callbacks And Revocation

Customer callback locks workspace, user, session, membership, then OAuth
state. This matches login email refresh followed by session rotation. It deletes the nonce and keeps the transaction open across bounded token
exchange and shop verification. Before credential persistence, current customer
access and upstream identity status are checked again. Nonce consumption and
credential persistence commit atomically. A duplicate callback waits, then rejects
without a second token exchange. All service disconnects acquire the same workspace
lock, including pending first-install disconnect, preventing callback resurrection.
Session revocation and membership changes serialize on the locked rows. A change
committed first rejects the callback; one waiting behind a successful callback
applies afterward. Provider failure rolls back local effects and returns a restart
message; the provider's one-use code may already be spent, so restart authorization.

The operator finish flow retains its prior early nonce consumption behavior.
Operator persistence and the Shopify importer use the same workspace-before-connection
lock order; imports skip locked workspaces rather than waiting with a connection lock.

## Validation

`tests/test_customer_shopify.py` checks customer/tenant/role/CSRF isolation, signed
query handling, same-user different-session rejection, replay, provider revocation
after exchange, pending disconnect, static relay/configuration, measurement-store
binding and privacy disconnect. PostgreSQL tests observe actual lock attempts to
verify concurrent callback and disconnect serialization. SQLite covers functional
behavior; PostgreSQL is authoritative for lock semantics.

Official source: [Authenticate A Standalone Or API-Only App](https://shopify.dev/docs/apps/build/authentication-authorization/authenticate-standalone-apps?lang=node).
Docs retrieved through Shopify developer search and primary documentation. The
skill's local telemetry helper scripts were unavailable in this execution environment;
no prompt telemetry was sent. No Admin API GraphQL schema changes are introduced.

Branch started at integration `c86beb3` and subsequently merged integration
`8ae5ab798eadd8835749f9ed03844fcf8280c25f`, including its independent migration-head
merge. The inherited multiple-head blocker is resolved; no Shopify schema change
is required.

Final package checks: `pytest -o addopts='' -q tests/test_customer_shopify.py
 tests/test_shopify_sales.py tests/test_commerce_review.py
 tests/test_inlet_integrated_migrations.py` with disposable PostgreSQL:
**73 passed, 3 SQLite-only concurrency skips**. Ruff, mypy (268 files), and
`git diff --check` pass. Full and hosted CI remain pending; no live verification.

## Cross-Path Privacy Review

PostgreSQL review reproduced the old privacy handler acquiring a native connection
before the callback's workspace/nonce fence. Privacy handling now discovers current,
pending-install and historical-alias owners, locks workspace IDs in sorted order,
then processes native/store rows. A newly discovered owner forces retry without
committing partial work. Uninstall and retention cleanup acquire nonce locks before
store locks; a nonce expiring during a bounded callback cannot deadlock the sweeper.
Concurrent uninstall and expiry-sweep regressions exercise actual PostgreSQL waits.
The importer retains the existing `shopify_ownership_unavailable` response for
suspended workspaces, distinct from a currently locked/busy workspace.

Initial PR87 CI run37403352872 failed on that importer status regression and a
nested existing browser deadline. It is not evidence for the repaired head. The
integration browser deadline repair is inherited separately; new-head CI is required.


## Login Rotation Lock Review

A PostgreSQL regression reproduced `DeadlockDetected` at the earlier ef0aaab head
when login refreshed the user's email and rotated the old session concurrently with
a callback. The guard now acquires User before Session. An in-flight login can finish
rotation; the callback then sees its revoked session, returns 401, and never exchanges
the Shopify code. Logout locks only Session; provisioning locks User before inserting
a fresh workspace (or reads an existing replay without row locks). These paths do not
reverse the corrected shared-row order. Callback/identity/provisioning/native-ownership
regressions qualify the change on disposable PostgreSQL; no live provider calls.
