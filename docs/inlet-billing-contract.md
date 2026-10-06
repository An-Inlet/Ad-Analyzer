# B13 Billing Preparation Contract

Prepare hosted-checkout and subscription lifecycle through an offline transport. No
commercial plan, price, trial, charge, Stripe account or live checkout is authorized.
Runtime checkout must fail closed until owner-approved commercial configuration and
provider setup exist. An empty catalog is not a free plan. One workspace owns one billing
customer; checkout customer identity is derived server-side, never accepted from a browser.

Verified webhook events are durable notifications, not authoritative entitlement snapshots.
Preserve a unique event ID, body digest and minimal resource identifiers, without card or
invoice payloads. Reject bad signatures, old signature timestamps, duplicate conflicting
payloads and live events in this offline implementation. Duplicate/out-of-order delivery
must retrieve current subscription state before applying access; never let an old snapshot
reactivate canceled service. Lock the workspace through retrieval/application and verify
customer, subscription and configured price. Provider failure must remain retryable.

Entitlements derive from an explicit configured policy and a fresh verified snapshot.
Unknown status, unknown price, expiry, suspension or stale verification denies paid work.
Read/report/export/disconnect access must remain available to authenticated members;
payment state cannot grant workspace membership or change an advertising mandate. Pausing
Inlet jobs on payment problems never pauses campaigns or reverses spend at providers.

Proposed commercial default for owner review: one monthly workspace subscription, explicit
account limits, cancel at paid-period end, no automatic paid trial and no new paid work
after verified lapse. Price/currency/account limits and any grace period remain unset.
No amount is invented. Initial fixture policy uses zero grace only as a test input.

Shared interfaces: `BillingTransport` handles customer/checkout creation with durable
idempotency keys and retrieves current subscription state; `require_entitlement` is used
by both customer mutation APIs and background workers. Provider resource IDs never replace
workspace ownership. Billing enforcement rollout and stale-state refresh scheduling are
release requirements, not silently activated for existing operator workspaces.

Official references checked 2026-10-06:
- [Stripe webhooks](https://docs.stripe.com/webhooks): raw-body signature verification,
  duplicate delivery, retries and fetching current resources.
- [Subscription lifecycle](https://docs.stripe.com/billing/subscriptions/overview).

This contract defines offline implementation boundaries. It does not settle pricing,
authorize purchases or claim that Inlet is purchasable.

## Implemented Slice And Open Acceptance

Durable customer/checkout idempotency keys survive uncertain responses. Owner-only
customer checkout routes use existing session/CSRF controls. Status remains accessible
without paid entitlement. Minimal signed fixture webhook receipts are deduplicated in
SQL; processors retrieve current subscription state under the workspace lock. A bounded
dispatcher refreshes stale subscriptions even without a new event and backs off failed
reads before batch selection. Unknown replacement subscription identities are unresolved,
never silently attached. Migration0031 preserves existing schema and blocks downgrade
while billing references or receipts exist.

`AD_ANALYZER_BILLING_REQUIRED=false` preserves current operator fixtures. Enabling it
requires explicit commercial configuration; Google customer imports, TikTok imports,
mandate claims and dispatch use the shared entitlement guard. This is not complete
rollout: legacy Meta/Shopify/operator jobs, account-connection limits, remaining customer
mutations and closure/export policy need a coordinated B19 boundary review. Do not enable
the flag in a production product and assume all workloads are covered.

No live Stripe adapter, billing portal, cancellation command, replacement-subscription
reconciliation or scheduled refresh runtime is delivered by this slice. B13 remains
open until these behaviors, owner commercial policy and live checkout/webhook recovery
are qualified. The independent B14 supplied-media/versioned-review work can proceed.
