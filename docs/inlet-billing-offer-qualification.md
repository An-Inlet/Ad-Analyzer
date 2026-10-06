# Commercial Offer Qualification

Isolated child of PR186 (`0efe061`). Root approved the concrete frozen
OfferProfileV1/BoundOfferV1/storage/qualified-snapshot proposal before implementation.
Migration0063 follows0061; root owns the later merge revision. No commercial values,
provider settings, credentials, purchases, deployment or Full run are enabled here.

## Supported Contract

`AD_ANALYZER_BILLING_OFFER_PROFILE` defaults unset. A strict frozen server profile
requires explicit scope, product/price, currency, positive minor-unit amount,
interval/count, fixed licensed quantity1, per-unit billing, declared tax behavior,
no automatic tax/rates, no trial, no discounts/promotions/credit, paid latest invoice,
exact portal configuration/period-end cancellation, account limit and opaque release
review reference. No customer body supplies a plan or qualification proof. Every
commercial value is supplied explicitly; the constraints describe supported CODE,
not a recommendation or owner decision about taxes, trials or discounts.

Qualified runtime assembly requires that profile and pinned Stripe API version
`2025-06-30.basil`. Existing unqualified fixture/test paths remain historical tests;
new live consumers cannot use them. The optional old live-account-limit setting is
superseded by the explicit reviewed profile allowance. Live forward billing remains
disabled by default; a populated profile is not permission to enable it.

## Original Requests And Evidence

New workspace-owned protected offer bindings commit exact scope, original checkout
key, reviewed profile, profile digest and binding digest before provider emission.
They are immutable through ORM writes and retained after current-pointer retirement.
Scoped composite foreign keys prevent another workspace/account/environment from
borrowing a binding. Existing rows are unqualified after migration. Downgrade refuses
populated offer lineage; there is no automatic legacy adoption.

A lost response retains its original key and profile. A changed profile permits only
read-only recovery of that original request; it cannot resubmit changed parameters
under the old key or silently install a replacement. An existing unbound request is
unresolved and cannot be retroactively qualified. Canonical expiration without a
subscription, or completion plus terminal subscription proof, remains required before
new checkout creation. Returning an original recovered Stripe session is not proof
of payment or entitlement to the new offer.

The adapter verifies exact price/product/recurrence/quantity/tax configuration and
portal behavior before a new purchase. Original paid subscriptions and checkout
recovery can still be read if the price/product is later inactive; inactivity blocks
new purchases. Non-active subscription snapshots retain cancellation/delinquency
without granting access. Historical terminal-event reads do not need a fresh current
offer and cannot establish a new active subscription.

Active state is insufficient. Qualification reads the owned latest paid invoice,
single recurring line and exact subscription period, invoice payment, succeeded
PaymentIntent and captured non-refunded/non-disputed Charge. It matches exact amounts,
currency, identities and mode and rejects extra adjustments, prorations, credits,
trials, discounts, taxes, schedules and pending changes. Persisted typed qualification
includes original binding/profile commitments, invoice/payment/charge lineage,
status/period/observation and a recomputable minimized projection digest. No raw
provider responses, payment details, client secrets or customer contact data persist.

`live_paid_work` requires current reviewed profile equality and matching fresh typed
qualification/scalar snapshot, plus existing account-count and workspace checks.
A profile change or absent qualification cannot authorize work merely because the
subscription says active. The original financial/closure/settlement evidence paths
remain separate from forward eligibility. Exports explicitly serialize and bind both
new structured domains; arbitrary or altered JSON is unavailable, not silently trusted.

## Reproduced Requalification Defect

After an initially valid paid snapshot, a provider mismatch at +3minutes previously
left the old snapshot inside its5minute freshness window, so forward entitlement
still passed. Both SQLite/PostgreSQL regressions reproduced DID NOT RAISE. The error
lane now marks commercial qualification unavailable under the workspace lock and
retains the old evidence; the original snapshot cannot grant forward work after the
known failure. Baseline log `/tmp/inlet-offer-qualification-failure-before.log`.

## Verification Record

Initial parser/journey tests23 passed. Populated migration plus expanded billing
subset83 passed/1 expected SQLite skip. Initial broad suite178 passed/2 skips/1
fixture failure: SQLite fixture had not enabled foreign keys; explicit FK enforcement
then passed bothDB. The older scope fixture was updated to provide the newly required
full offer/invoice proof rather than bypassing the gate. Latest offer+migration suite
54 passed; static Ruff and configured mypy510 source files passed. Final combined suite:217 passed/2 expected SQLite skips (billing, exports, closure,
provider mandates and settlement). After the final retired-price and pinned-object
checks, offer/scope/migration subset:69 passed. Chromium billing/portal plus scheduler
and migration subset:47 passed. Ruff, configured mypy510 and diff check passed.
Logs: `/tmp/inlet-offer-final2.log`, `/tmp/inlet-offer-final-qualification.log`,
`/tmp/inlet-offer-browser.log`, `/tmp/inlet-offer-mypy-final.log`. No Full claimed.

## First-Party Version Evidence

Pinned invoice, invoice-line, invoice-payment, PaymentIntent and Charge object docs:
[Invoice](https://docs.stripe.com/api/invoices/object?api-version=2025-06-30.basil),
[Line](https://docs.stripe.com/api/invoice-line-item/object?api-version=2025-06-30.basil),
[Payment](https://docs.stripe.com/api/invoice-payment/object?api-version=2025-06-30.basil),
[Intent](https://docs.stripe.com/api/payment_intents/object?api-version=2025-06-30.basil),
[Charge](https://docs.stripe.com/api/charges/object?api-version=2025-06-30.basil).
The docs tool could not open the pinned portal URL. The official immutable
[Stripe Python12.3.0 version declaration](https://github.com/stripe/stripe-python/blob/v12.3.0/stripe/_api_version.py)
identifies this exact API version, and its generated
[portal configuration contract](https://github.com/stripe/stripe-python/blob/v12.3.0/stripe/billing_portal/_configuration.py)
verifies the feature/mode/proration fields used here. All adapter calls in tests use
MockTransport; documentation reads are not live billing API calls.

## Remaining Work And Owner Choices

This supports one deliberately narrow fixed offer. Automatic/manual taxes, trials,
discounts, credits, grace periods, tiered/metered or multiple-item prices, plan
migrations and other portal behaviors need additional engineering if desired. These
are not merely missing keys. Owner choices remain the actual supported price,
currency/period, account allowance, tax applicability, trial/discount applicability
and permitted portal behavior. No numeric values or tax advice are chosen here.

Release work remains: all intended production assembly bindings, configured intended-
environment purchase/cancel/webhook qualification, migrations with old writers
quiescent, and operator reconciliation/monitoring. Offline parser fixtures are not
proof that a deployed product is purchasable.
