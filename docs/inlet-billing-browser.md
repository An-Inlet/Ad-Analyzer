# Customer Test Checkout And Management Journey

The portal offers checkout only when the server reports a valid configured test
billing policy and the current customer owns the workspace. Existing nonterminal
subscriptions use management instead of another checkout. Management also requires
a configured provider portal and an existing customer. Other members retain safe
read-only billing status; their controls cannot grant authority.

`GET /billing` adds boolean action availability, pending checkout, current verification
and attention flags. No provider/customer IDs, checkout URLs, tokens or raw errors
are exposed by this status response. Current verification describes freshness of the
server snapshot, not a purchase assertion or a separate entitlement decision.

Both POST endpoints preserve their existing service, durable idempotency/recovery
and ownership contracts. The server generates `/app/settings?workspace=<id>&billing_return=1`
from the configured application origin. The portal selects that workspace only after
loading the signed-in customer's memberships, then clears query parameters. The
marker has no payment meaning. Both successful and canceled provider flows return
to the same current-state screen. Session expiry/revocation and the owner role are
rechecked after provider/lock waits before a navigation URL can be returned.

Only HTTPS checkout.stripe.com `/c/` and billing.stripe.com `/p/session/` URLs in
explicit stripe_test mode navigate. Other modes, unknown actions, credentials,
ports, hosts and paths fail closed. A canceled or interrupted checkout can be
explicitly resumed through the same server-held attempt; the browser neither
creates idempotency keys nor marks a subscription paid. Existing uncertain/expired
attempt recovery remains authoritative. Check Billing Status reads persisted state;
webhook/dispatcher processing remains asynchronous and is not triggered by GET.

The screen distinguishes pending checkout, stale verification, scheduled end-of-period
cancellation and attention. It makes no live purchase offer and invents no price.
An interrupted request displays a safe next step. Role/session rejection removes
billing controls; logout/session failure clears customer content. Existing response
epoch checks reject a previous workspace's delayed result. A reproduced overlap
between a pending management request and a workspace change left controls disabled;
the common portal guard now keeps one original disabled-state map until all pending
guarded tasks settle, avoiding restoration of another task's temporary state.

## Offline Acceptance

`tests/test_billing_browser_journey.py` drives actual visible portal controls in
Chromium against local HTTPS FastAPI, real cookies and SQLite/PostgreSQL. The actual
StripeBilling HTTP adapter uses MockTransport. Only provider-host navigation is
intercepted before network and rendered as a synthetic return/cancel page; browser
API fetch is not replaced. This is not an exercise of Stripe's real hosted form.

The journey covers a lost checkout response, same-key retry, provider cancellation
and resume, return while still pending, signed webhook receipt plus dispatcher
reconciliation, management navigation, delayed cancellation status, stale workspace
responses, usable controls after overlapping requests, read-only viewer status,
role downgrade during provider wait and session revocation before URL release.
Separate API regressions check owner-to-admin downgrade and revocation during both
checkout and management. Node tests reject unsafe navigation paths/actions. Existing
Shopify consent and customer browser/API journeys are rerun because they share the
portal guard.

Final focused command (explicit disposable PostgreSQL enabled):

```sh
pytest tests/test_billing_browser_journey.py tests/test_customer_billing.py \
  tests/test_billing_recovery.py tests/test_stripe_transport.py \
  tests/test_customer_portal.py tests/test_customer_browser_api_journey.py \
  tests/test_shopify_consent_browser.py
```

Result: **78 passed, 1 skipped**, 32.64s. The skipped SQLite lock case has its
PostgreSQL counterpart executed. Log: `/tmp/inlet-billing-browser-final.log`.
Whole-tree Ruff and `git diff --check` pass. Targeted strict mypy across application
and changed Python tests passes (220 source files). Whole-tree mypy reports only the
inherited unused-ignore at `tests/test_gcs_media_storage.py:12` (314 files checked);
the integrating agent already removed that ignore separately in PR113 `7ae1d0d`.
This candidate intentionally does not edit that unrelated file. No Full run is claimed.

## Remaining Qualification

Default billing remains disabled; live mode is rejected. Pricing, provider setup,
real checkout/webhook/portal behavior, browser/device qualification and production
operations require separate approval and evidence. A same-tenant server-side provider
operation already in flight cannot be undone by local revocation; this change fences
URL delivery, not remote effects. Remote identity checks remain point-in-time. New
commercial products, live charges, credentials, grants, deployment and merge are not
authorized or performed. Full final integration validation remains a parent-owned gate.
