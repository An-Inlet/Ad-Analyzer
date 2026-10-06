# Original Billing Receipt Reader

Parent approved `/workspace/inlet-design/BILLING-RECEIPT-ONLY-ASSEMBLY.md` before
implementation. This isolated successor starts from PR196 `ac2a601`; no schema,
commercial profile, customer purchase authorization or retention policy changes.

## Implemented Contract

`BillingReceiptReader` exposes only immutable scoped current-subscription and
known-checkout reads against an original validated `BoundOfferV1`. The private
HTTP adapter rejects non-GET methods, request bodies and idempotency keys before
HTTP. Every original read uses the binding's pinned Stripe API version and offer
terms, and verifies the authenticated merchant and response mode. The factory
never consults the current offer or current purchase API version.

`AD_ANALYZER_BILLING_RECEIPT_READ_ENABLED` defaults false. The separate
`AD_ANALYZER_BILLING_RECEIPT_ENVIRONMENT` defaults empty and must explicitly be
`test` or `live`; production accepts only live. The server merchant and key family
must match that scope. The existing customer billing scheduler flag is also
required. When both flags are enabled the scheduler uses the receipt dispatcher
instead of constructing a purchase transport or current commercial policy.
This code does not set either flag or supply credentials.

The dispatcher selects at most 10 owned rows by default (hard maximum 100),
validates original immutable bindings under the workspace lock, releases that
transaction for GET-only provider IO, and reacquires the workspace lock before
checking the complete original identity, observation state and a fresh clock.
A changed/closing workspace or replaced/newer billing state prevents persistence.
Qualified paid evidence is validated against the original binding. Failure marks
qualification unavailable with bounded retry delay while preserving original
identity and earlier evidence. Current offer qualification remains mandatory for
forward entitlement; removed/invalid/replaced offers cannot grant paid work.

Known checkout completion can recover its exact owned subscription. Expired/open
checkout observation preserves the original request key; it does not start a new
purchase. No-ID lost checkout responses remain unresolved without provider IO.
This package intentionally adds no search/discovery, POST replay, portal session,
customer creation, replacement key or offer substitution. A future bounded GET
search can be separately qualified without weakening these guards.

Only pending notices for the same scope/customer/subscription and received no
later than the provider observation are acknowledged. Newer or mismatched notices
remain pending. Closing workspaces retain the existing local `closure_pending`
notice lane, without provider calls or any claim of completed external closure.

## Verification and Remaining Readiness

Deterministic HTTP fixtures exercise the real strict Stripe parsers and scheduler
assembly on SQLite and PostgreSQL. Tests cover removed/invalid current offer,
terminal subscriptions, known and unknown checkout, exact pinned version despite
changed current config, GET-only method capture, foreign scope/pre-HTTP mutation
rejection, closure/identity/newer snapshot changes during IO, post-read expiry,
backoff, evidence retention, scoped notice acknowledgement and disabled factories.

Initial receipt tests: 21 passed. Broader billing/assembly/offers/scopes/closure/
scheduler suite: 155 passed in 57.65s before the final notice-time assertion.
Logs: `/tmp/inlet-billing-receipt-first.log`, `/tmp/inlet-billing-receipt-final.log`.
Final receipt suite and static checks are reported in the delivery PR.
No Full, live provider requests, charge, deployment or manual CI dispatch occurred.

For a separately authorized deployment, configure the explicit receipt environment
and matching merchant/key secret reference, alongside the independent scheduler and
receipt flags. Keep purchase enablement off if the current commercial offer is
not qualified. Historical alternate merchants need an explicit supported server
credential mapping; no fallback exists. Customer portal management uses POST and
remains outside this reader. Tax/trial/discount and other unsupported offer policies
remain separate engineering work, not settings the reader can infer or choose.

Final receipt suite after the notice observation-time fence: 27 passed in 11.81s
(`/tmp/inlet-billing-receipt-last.log`). Full-tree `ruff check .`, configured
`mypy` (514 source files), and `git diff --check` passed.
