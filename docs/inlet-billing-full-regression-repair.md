# Billing Full Regression Repair

Isolated base: root `01eec67`. The frozen candidate and its running Full validation
were not changed. No live calls, schema changes or commercial policy changes.

## Reproduction And Classification

Exact targeted baseline: three failures in 4.28s,
`/tmp/inlet-billing-full-before.log`.

The repurchase test failed on SQLite and PostgreSQL because `reconcile` required
any event naming a different subscription to be historical and terminal *before*
resolving the saved replacement checkout. A legitimate new active subscription
therefore failed with HTTP 502 before reaching the existing owned-session and
old-terminal guards. This is a real service regression, not a fixture exemption.

The default transport test expected a usable Stripe adapter with only a test key
and an old API version. Current assembly deliberately requires an explicit merchant
and reviewed offer. That expectation was stale; the corrected test verifies denial
first, then supplies the explicit supported test profile for construction. It makes
no provider request and does not weaken production enforcement.

## Repair And Boundaries

For a different event subscription, resolve only the locally persisted checkout
first. The existing resolver validates its owner and original offer, requires the
previous subscription to be terminal, and verifies the replacement's paid evidence.
If the event still differs, the separate historical-terminal rule applies. An event
identifier alone never authorizes adoption or supplies a new offer binding.

Qualified mocked-HTTP tests cover successful replacement, an old subscription still
active at the provider, an open checkout, a foreign checkout owner, and unpaid
replacement evidence. Rejected replacements preserve the original subscription
binding. A delayed old-terminal event cannot restore the previous subscription.
Only one checkout POST is made in each fixture scenario; reconciliation does not
create or replay a purchase.

## Validation

Initial repaired focused subset: 13 passed. Broader and final results are recorded
in the delivery PR and appended below. Offline fixture evidence is not a claim of
production payment qualification or a passing successor Full run.

Broader billing/reviewer/Stripe/recovery/scopes/assembly suite: 169 passed, one
SQLite skip for PostgreSQL row-lock interleaving, in 47.86s
(`/tmp/inlet-billing-full-final.log`). Final qualified repurchase suite after the
late-event assertion: 10 passed in 6.26s (`/tmp/inlet-billing-full-last.log`).
`ruff check .`, configured mypy (610 source files), and diff whitespace checks
passed. No new Full was run by this package.
