# Billing Recovery Review Repair

Based on PR77 head `275e0ee179c2b6d84f1b2a14b3048b44b123c5ae`.

A PostgreSQL barrier regression reproduced concurrent replacement checkout sessions:
one caller resolved a completed/canceled checkout, committed, then resumed after a
second caller installed a replacement. The stale caller previously cleared it and
created another purchase attempt (`cs_new2 != cs_new1`). The service now reacquires
the ownership lock, reloads and compares the resolved identity, and converges on the
current attempt. Terminal retirement and replacement-key installation share one
transaction. Bounded retries reject continuing contention rather than losing state.

After an uncertain provider write outlives the 23-hour safe idempotency retry window,
the test-only HTTP adapter now performs read-only recovery. Customer search requires
an exact workspace/request metadata match and a canonical customer read. Checkout
recovery uses bounded customer/time-scoped pagination, exact request metadata,
canonical checkout identity and a single approved-price line item. Empty, ambiguous,
foreign, live-mode, cyclic or mismatched results never authorize a new POST/key.
A timed-out checkout later recovered as completed without a URL reconciles its
subscription and entitlement; the integration regression asserts exactly one POST.

Legacy keys without timestamps/request metadata remain fail-closed and require
manual reconciliation. Search is eventually consistent; an empty search cannot
prove that creation failed. This is actual HTTP code exercised with MockTransport,
not live verification or a complete commercial launch.

## Validation

Baseline race regression failed on PostgreSQL as expected (SQLite explicitly skips
this row-lock interleaving). Final focused command:

```
pytest -o addopts='' -q tests/test_billing_recovery.py tests/test_customer_billing.py tests/test_stripe_transport.py tests/test_inlet_review_regressions.py
```

With explicit disposable PostgreSQL: **95 passed, 1 SQLite-only skip**.
Ruff, mypy (249 files), formatting and diff checks passed. Full and hosted CI are
pending and must be recorded separately. No schema migration or live requests.

## Primary Contract References

- https://docs.stripe.com/api/idempotent_requests
- https://docs.stripe.com/api/customers/search
- https://docs.stripe.com/api/checkout/sessions/list
