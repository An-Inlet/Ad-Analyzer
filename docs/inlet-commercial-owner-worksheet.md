# Inlet Commercial Owner Worksheet

Prepared against candidate `b9d2dce` on 2026-10-06. This is a decision package for
An Inlet's future paid launch, not a request to activate billing. Engineering,
customer-session automation and release validation are still underway. These
choices do not block independent offline work or prove that Inlet is purchasable.

## Recommended Launch Structure

Start with one fixed monthly subscription per customer workspace, one currency,
one explicitly chosen advertising-account allowance, and a single recurring price.
Recommend enabling payment-method updates and invoice history in the customer
billing portal. This keeps the initial offer within the implemented fixed licensed
profile and reduces plan-change complexity. **No price, allowance, currency or tax
treatment is selected by this recommendation.** One workspace is the billing unit;
it does not imply that an entire multi-workspace customer shares one subscription.

The current implementation supports no trial, discount, promotion code, credit or
grace period, and only period-end cancellation without proration. Those are support
limits to accept or change through further implementation; they are not approved
An Inlet business policies. Do not choose a tax treatment merely to fit the code.

## Four Owner Inputs

| Input | Minimum answer needed | Effect |
|---|---|---|
| Seller and launch markets | Confirm the legal selling entity, its jurisdiction, and the customer markets to serve initially. Have the responsible tax/legal adviser determine applicable collection, registration, invoicing and customer-terms requirements for that scope. Record the determination and responsible owner; no sensitive documents or credentials are needed in this worksheet. | Establishes whether the implemented offer can legally serve those markets or needs tax/terms engineering first. No exemption or zero-tax conclusion is assumed. |
| Offer economics | Choose the recurring amount and currency. Accept monthly billing or specify the desired period. | Supplies the real price; no numeric placeholder becomes a commercial default. |
| Included usage | Choose the maximum number of connected advertising accounts per paid workspace. | Sets the explicitly validated account allowance. This is not an advertising spending limit or permission to raise one. |
| Customer policy | Accept the current no-trial/no-discount/no-credit/no-grace profile and period-end cancellation, or name the changes required. Confirm portal payment-method updates and invoice history. Identify the customer-facing cancellation/refund terms and who handles refund requests. | Separates supported behavior from new engineering. Refund issuance and alternative cancellation/credit policies are not automated by this profile. Published terms must match the behavior actually delivered and applicable requirements. |

A compact reply can provide those four answers. If tax treatment or a policy is
not yet settled, name the responsible owner and leave it unresolved. Do not provide
API keys, webhook secrets, payment details, live account grants or permission to
charge as part of these answers.

## What The Code Currently Qualifies

The server-owned `OfferProfileV1` binds the merchant, environment, pinned provider
API version, exact product/price, amount/currency, interval, quantity one, account
allowance and supported portal policy. Every commercial field must be explicit;
there is no configured default launch offer. Purchase requests retain an immutable
original offer and request key. Paid entitlement requires matching current offer
and owned paid invoice/payment evidence; an `active` subscription label alone is
insufficient. Production cannot substitute test billing or bypass enforcement with
the historical optional rollout flag.

The supported tax setting is technically `disabled_no_rates`; its inclusive or
exclusive price label does **not** establish tax compliance. The parser rejects tax
amounts/rates and unsupported adjustments. If the seller's required treatment needs
collected tax, automated tax, additional invoice fields or other unsupported
behavior, engineering and qualification must precede serving that market. This
worksheet provides no tax or legal conclusion.

Original financial receipts can be read through the separately enabled GET-only
reader even when the current offer is unavailable. That reader cannot create a
customer, checkout or portal session, replay an unknown purchase, change an offer,
or grant access without current qualification. A lost checkout response without a
known checkout ID remains unresolved in that receipt-only lane.

## Engineering And Release Work That Is Not An Owner Price Choice

- Trials, discounts, promotions, credits/grace, tax collection, tiered/metered or
  multiple-item pricing, plan migration and alternative portal/cancellation rules
  need additional implementation if selected. Supplying keys will not add support.
- Complete the remaining customer/session automation and current candidate
  acceptance checks. Offline HTTP/browser fixtures are not deployed payment proof.
- Map the approved offer to actual non-secret Stripe merchant/product/price/portal
  identifiers, validate their exact provider fields, and record the immutable review
  reference. These identifiers are implementation outputs after the offer is chosen,
  not extra business decisions or customer-supplied authorization proof.
- Qualify migration, deployment, monitoring, reconciliation and intended-environment
  checkout/webhook/cancellation behavior under the separate release process. Store
  any later authorized credentials only in the external secret system.
- Keep live enablement off and public claims accurate until the release gates are
  met. Completing this worksheet does not authorize deployment, charges, ad spend,
  publication, or access to customer advertising accounts.

Implementation evidence and limits: [Offer qualification](inlet-billing-offer-qualification.md),
[production assembly](inlet-billing-production-assembly.md),
[receipt reader](inlet-billing-receipt-reader.md), and the current
[candidate acceptance record](inlet-candidate-acceptance.md).

## Document Review Record

Docs-only change against `b9d2dce`; no settings or application files changed.
Existing offer/production-assembly regressions: 69 passed on configured SQLite and
PostgreSQL fixtures (`/tmp/inlet-commercial-decisions-tests.log`). Full-tree Ruff,
configured mypy (582 source files), local document links and diff whitespace checks
passed. No Full or live calls were run for this worksheet. These checks verify the
referenced offline behavior, not legal compliance, market viability or launch approval.
