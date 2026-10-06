# Billing Environment Foundation

Base: `1c82e03`. Parent approved `BillingScopeV1` and reserved migration
`20261006_0061` after the concrete environment-separation proposal. This is offline
implementation, not an enabled purchase service or live qualification.

## Frozen Interface And Migration

`BillingScopeV1` is a frozen strict schema: provider `stripe`, environment `test|live`,
merchant account `acct_...`. It is server-selected, never customer input or inferred
from a redirect. Billing rows are keyed by workspace plus that identity; event rows
by event ID plus that identity. Resource and durable retry-key uniqueness is scoped.
ORM updates cannot change identity. Shared repository helpers require scope.

0061 follows0060. Old rows become `stripe/test/legacy_unqualified`. No automatic
adoption, test-to-live promotion or entitlement transfer occurs. The real runtime
factory requires a qualified account. Legacy direct fixture/test transports remain
explicitly unqualified for historical offline tests; they cannot create live scope.
Downgrade refuses qualified data or an identity collapse; populated legacy records
survive a roundtrip. Stop all old billing writers before upgrading: an old binary's
workspace-only UPDATE is unsafe against multiple scoped rows. This is a quiescent
upgrade requirement, not a rolling compatibility claim.

## Runtime And Evidence Lanes

`AD_ANALYZER_BILLING_PROVIDER_MODE` supports disabled, stripe_test and stripe_live.
`AD_ANALYZER_BILLING_MERCHANT_ACCOUNT_ID` is required for a real adapter.
`AD_ANALYZER_BILLING_LIVE_ENABLED` defaults false. Price, API version, key, merchant,
portal configuration and live account limit remain unset. The new optional
`AD_ANALYZER_BILLING_LIVE_MAX_ACCOUNTS` has no default commercial allowance.
No settings, keys, provider accounts or charges were enabled by this package.

The adapter checks the key family and authenticates `GET /v1/account` before each
qualified resource read or mutation. The returned current account must exactly
match; each resource's livemode must match. No construction/import IO occurs.
Durable checkout retry/recovery and unknown-outcome rules are retained.

Signed `/api/billing/stripe/test/events` and `/live/events` bind their environment
before persistence; live has a dedicated signing secret. Legacy `/stripe/events`
is permanently test-only. Receipt routes require configured merchant/signing secret
but remain evidence-only when forward live billing is disabled: no provider call or
entitlement grant. Dispatcher, backoff, closure late-receipt lane, operations and
archive ownership join on customer AND all scope fields. Closing workspaces retain
receipts without reconciliation mutations or new purchasing.

`live_paid_work` requires qualified live scope, explicit commercial policy and a
fresh matching live subscription. It ignores the optional `billing_required` flag.
Live `ProviderMandatePolicy` validation calls it during review/claim/final authority,
so changing configuration to test cannot authorize forward live execution. Original
receipt/settlement readers are unchanged. Generic `paid_work` uses this gate whenever
live billing is configured; otherwise its historical test rollout remains optional.
Customer analysis/import and older publication callers have no intrinsic production
environment parameter. Their future production assembly must explicitly require the
live gate; they are not claimed universally production-bound by this package.

Portal actions distinguish test and live modes and preserve exact Stripe-host/path
redirect validation. `live_verified` remains false: no deployed billing was tested.

## Verification And Remaining Work

Focused pre-final checks: 167 passed, 2 expected SQLite concurrency skips across
scope/migration, billing/recovery, closure, route inventory, bounded exports,
operations and provider execution mandate/lifecycle tests. After adding the explicit
unset live limit and receipt-only disabled-forward path: billing/scopes/migration
60 passed, 1 expected SQLite skip. Node portal tests:14 passed. Ruff and configured
mypy:505 source files passed. Actual Chromium portal/billing plus scheduled-runtime/customer API journey subset:47 passed.
No Full or manual hosted dispatch.

Migration evidence: PostgreSQL ran full ancestry and populated upgrade/downgrade;
SQLite ran exact0031 billing schema then0061 because historical0002 has unsupported
SQLite ALTER. The initial SQLite full-history attempt failed before0061. Initial
new scope test setup had a fixture signature mistake, not a product failure. Logs:
`/tmp/inlet-billing-scope-final.log`, `/tmp/inlet-billing-scope-last.log`,
`/tmp/inlet-billing-scope-js.log`, `/tmp/inlet-billing-scope-mypy-final.log`,
`/tmp/inlet-billing-scope-browser.log`.

Tests include identical IDs in different environments/accounts, immutable identity,
owned export predicate, signed cross-mode denial, disabled-forward receipt replay,
closing-workspace late receipt isolation, wrong authenticated account before POST,
wrong livemode, mock HTTP checkout→signed inbox→dispatcher→entitlement→management→
cancellation, and unchanged lost-response recovery. No real Stripe calls.

Next package: explicit commercial offer qualification (product/currency/interval,
tax/trial/discount configuration), owner-approved pricing and portal cancellation
rules, all production assembly bindings, and intended-environment release evidence.
These are not supplied by scope migration alone. Existing fixture billing and a
successful checkout redirect remain insufficient evidence of a purchasable product.

## First-Party Contract References

Reviewed Stripe's [mode/key isolation](https://docs.stripe.com/keys),
[account API](https://docs.stripe.com/api/accounts/retrieve), and the official
[Python current-account implementation](https://github.com/stripe/stripe-python/blob/master/stripe/_account_service.py)
(`retrieve_current` uses `/v1/account`). Documentation reads were the only external
reads; tests use injected MockTransport.
