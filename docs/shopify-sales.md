# Shopify sales integration

Each workspace can authorize one Shopify store from **Workspace → Shopify connection and sales**. Owners and administrators connect, refresh, reconnect, disconnect, and handle privacy exports; viewers can read aggregate sales and export the summary. The decision center includes commerce context and answers questions about Shopify sales, products, and refunds. Existing CRM measurement and advertising execution policies still apply.

## Available analysis

- Net collected, captured payments, refunds, paid orders, cancelled orders, and average net collected per paid order.
- Current and preceding 28 completed days in the store's time zone. Period changes are withheld until the import covers both periods.
- First versus returning **orders**, with unknown customer-journey history explicitly counted. This is not unique-customer retention or lifetime value.
- Product demand by ordered units, retained units, and gross original-price ordered value. Product figures are before discounts and refunds, and cannot be used as net product revenue or margin.
- Recognized last-visit source tags; campaign matching requires a numeric `utm_campaign` equal to an imported Google/Meta campaign's external ID in the same workspace. Ambiguous, missing, and unrecognized tags remain unmatched. Use `utm_source=google` or `facebook`/`instagram`/`meta` as appropriate. Existing named campaign tags need a reviewed tagging update before they can match; the integration never changes live ads.
- Store sales/ad spend and tagged sales/ad spend comparisons only with complete campaign-day coverage in the same currency and time zone. Spend uses campaign rows, excluding child metric grains. These are descriptive ratios, not incremental ROAS or proof of advertising causation.
- Sales review suggestions for refund levels, tagging coverage, and product-led creative tests, with a 20-paid-order floor for sales-based suggestions. These fixed heuristics do not promise improved results or execute budget changes.

`netPaymentSet` is captured payments less refunds, including tax and shipping. Reports group by the original order date, even when a refund arrives later. They do not report accounting net sales, refund-date cash flow, profit, or causal attribution. Shopify and CRM totals are not added together. Test orders are excluded. Cancelled orders retain any financial activity actually reported by Shopify.

## Enablement and release gate

This change provisions no service, changes no billing, and deploys nothing. Shopify is disabled by default. An operator must complete the existing human release gate and verify the incremental Pub/Sub, database, and worker costs before enabling it. Do not request or share credentials in chat or commit them to the repository.

1. Create/configure the organization's standalone Shopify app with `read_orders,read_products` only, `embedded = false`, and the authenticated Ad Analyzer dashboard as its application URL. Follow Shopify's distribution rules for the intended stores. Obtain the required protected order-data access for these fields. No customer names, email addresses, postal addresses, customer IDs, notes, or custom order properties are selected.
2. Register the exact HTTPS callback URL ending `/dashboard/shopify/callback`. Keep IAP and workspace authentication in place. The same signed-in workspace owner/admin must start and finish authorization. A local handoff page links to Shopify without a cross-origin form redirect, preserving the dashboard’s `form-action` policy. Shopify HMAC verification, a ten-minute actor/workspace/store-bound state, and single-use consumption protect the callback.
3. Configure a **dedicated** Google Pub/Sub topic/subscription for this app's Shopify events. Grant Shopify's documented delivery service account `delivery@shopify-pubsub-webhooks.iam.gserviceaccount.com` publisher access to that topic only. The existing scheduler identity needs subscriber access to the dedicated subscription. Do not share the CRM subscription or grant public publisher/subscriber access. Native cloud event deliveries rely on this IAM boundary; the app adds no public webhook route and does not weaken IAP.
4. Configure app-specific subscriptions to that topic for `orders/delete`, `app/uninstalled`, `customers/data_request`, `customers/redact`, and `shop/redact`. Configure compliance topics with `compliance_topics` in the Shopify app configuration. Pin webhook version `2026-07`. Configure bounded retry, a restricted dead-letter topic, and an alert on unacknowledged/dead-letter messages. Verify delivery using a development store before enabling real imports. The worker accepts Shopify's native metadata/payload envelope and Pub/Sub message-attribute metadata, case-insensitively. Never log raw events or retain them in general-purpose observability systems.
5. Supply the settings below through the existing managed runtime secret/configuration process to web **and scheduler**. Apply Alembic upgrade `20260906_0018` through the existing migration job before serving the new code. Verify the scheduler is healthy; privacy events need it even when imports are paused.
6. Before OAuth traffic, exclude `/dashboard/shopify/callback` requests from Cloud Run, load balancer, IAP, proxy and tracing logs that record request URLs. Query parameters contain temporary authorization material. The application suppresses Uvicorn access entries for this route, but cannot control infrastructure request logs. Validate this with a non-secret development callback. Do not weaken identity checks to make the callback reachable.
7. Enable the integration, authorize a development store through the workspace page, complete a sync, reconcile sampled order totals against Shopify, verify a refund update, and deliver all five event topics through the dedicated subscription. Verify redaction persists after another import and revocation prompts reconnect. Check actual query cost and backlog at expected store volume. Release to the intended store only after these checks and human approval.

| Setting | Purpose |
| --- | --- |
| `AD_ANALYZER_SHOPIFY_ENABLED` | Defaults to `false`; enables authorization and sales imports. |
| `SHOPIFY_CLIENT_ID` | Shopify app identifier. |
| `SHOPIFY_CLIENT_SECRET` | Runtime secret for OAuth validation/exchange. |
| `SHOPIFY_TOKEN_ENCRYPTION_KEY` | Runtime Fernet key for authenticated encryption of credential envelopes. |
| `SHOPIFY_IDENTIFIER_HASH_KEY` | Separate stable random runtime secret, at least 32 bytes, for pseudonymous deduplication/redaction keys. |
| `SHOPIFY_REDIRECT_URI` | Exact registered HTTPS callback URL. |
| `SHOPIFY_WEBHOOK_SUBSCRIPTION` | Dedicated `projects/PROJECT/subscriptions/SUBSCRIPTION` path. |
| `SHOPIFY_SYNC_PAGES` | 1–10 pages per workspace per scheduler tick; default 10. |
| `SHOPIFY_SYNC_INTERVAL_MINUTES` | Minimum interval between completed syncs, default 60, range 15–1440. Actual cadence is also limited by the existing scheduler tick. |

Authorization scopes are verified both in the token response and installation metadata; write scopes are rejected. Credential envelopes bind workspace and store. Expiring offline tokens rotate under a connection row lock; a failed order page rolls back to a savepoint while preserving a successful credential rotation. No tokens, raw responses or customer identities are included in the dashboard, API or application logs.

## Import bounds and operations

The default Shopify order permission reaches only the most recent 60 days. This importer uses a rolling **59-day** window to avoid the access boundary advancing mid-request and deletes expired local facts on each scheduler tick, including when imports are paused. It does not request `read_all_orders` or claim full-history analysis. Pausing all workers also pauses retention and privacy processing; drain requests and disconnect stores before retiring the worker.

Each page requests ten orders and ten line items per order, keeping nested query cost bounded. Orders with more than ten line items contribute complete order financial totals but no product breakdown, with a visible coverage warning. Full product pagination and bulk historical imports are outside this release. At most ten workspaces and the configured pages are processed per tick. Initial backfills may take many cycles; larger stores must validate throughput and backlog before using this importer. Queries that reach Shopify's pagination limits require a future bulk or partitioned importer. Do not present an unfinished backfill as complete.

The fixed cursor window uses `UPDATED_AT` with a seven-day overlap for late changes, idempotent hashed order keys, and source-update guards against stale overwrites. Refunds on retained orders update existing facts. Pending journey history can remain unknown; there is no customer profiling. Throttling saves a bounded retry time; no busy-loop retries occur. The interface reports missing, stale, failed and partial imports, and withholds unsupported spend comparisons. `All Ad Analyzer data syncs` and workspace `Shopify sales sync` both block scheduled and manual reads.

Privacy processing runs before sales imports and independently of the sync toggles. Events are acknowledged only after successful processing/commit. Orders are erased with tombstones that prevent resurrection by an overlap import. Redaction tombstones expire after 61 days; order facts expire after 59. Store redaction/uninstall removes the connection and its imported facts. Privacy requests retain only hashed requested-order keys and appear to owners/admins for export and confirmed delivery. Requests with no retained facts export an empty record list. Delivered request tracking expires after 30 days; aggregate audits expire after 90 days. Restricted database backups also need a reviewed retention/restoration policy so a restore reapplies deletions before serving data.

Disconnect explicitly removes imported sales and locally encrypted credentials. It does not uninstall the app from Shopify; the merchant can uninstall in Shopify to revoke authorization there. Before rotating either runtime key, disconnect/re-authorize stores and remove old facts, or use a separately reviewed re-encryption procedure. Never change the identifier hash key on an active data set: deletion matching depends on it.

## Validation

Offline tests exercise OAuth HMAC/timestamp/nonce validation and replay, scope restrictions, credential binding, rotation after a failed page, stable cursors, refund upserts, stale update rejection, privacy deletion/replay, authenticated exports, CSRF and workspace roles, campaign/currency/date coverage, query destinations, log suppression and migration constraints. CI additionally runs the repository's disposable PostgreSQL migrations and full read-only/security/privacy suite. Live development-store checks above are still required; schema validation and mocks cannot verify app approval, infrastructure configuration, real Shopify query cost, or store-specific data availability.

Sources: [Shopify standalone OAuth](https://shopify.dev/docs/apps/build/authentication-authorization/authenticate-standalone-apps), [Order fields and access window](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Order), [Customer journey indicators](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/CustomerJourneySummary), [API limits](https://shopify.dev/docs/api/usage/limits), [Pub/Sub delivery setup](https://shopify.dev/docs/apps/build/webhooks/get-started?deliveryMethod=pubSub), [Subscription configuration](https://shopify.dev/docs/apps/build/webhooks/subscribe), [Privacy event requirements](https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance).

Browser compatibility: the local authorization handoff avoids [inconsistent browser handling of form redirects under CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/form-action).
