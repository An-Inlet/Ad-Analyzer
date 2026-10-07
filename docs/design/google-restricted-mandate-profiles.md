# Restricted Google Profiles Within An Approved Mandate

Proposal for review, based on `c6d72b6`, 2026-10-06. No runtime, authority, acceptance or
public claim changes. Recommendation-only launch remains an unanswered owner option,
not the assumed product direction. This investigates an attainable restricted path for
the original optimization scope rather than declaring all optimization impossible.

## Mandate Interpretation

The owner's scope permits optimizing existing campaigns within approved spending authority;
new campaigns and creative require review, and aggressiveness never increases the overall
limit. That requires controlling **Inlet's actions**. It does not expressly promise that
Inlet can prevent every independent administrator from changing an account forever.

Three different claims must remain distinct:

1. **Locally enforceable:** Inlet emits only owned, authorized, policy-conforming requests;
   never increases its approved allocation; detects known drift and stops new actions;
   retains unknown attempts and previous financial obligations.
2. **Provider-conditional:** an eligible native budget limits the provider's specified
   financial quantity while its applicable configuration remains within the approved
   envelope. This requires exact scope, period and accounting-basis qualification.
3. **Universal:** total served/billed/cash expenditure cannot exceed the mandate despite
   outside cap increases, new uncovered campaigns, billing changes or provider exceptions.
   No reviewed mechanism establishes this stronger claim.

Current strict execution contracts require more than (1), including qualified financial
bounds and writer evidence. They remain intact. A reviewed mandate interpretation/profile
must specify whether (1)+(2), with explicit outside-change handling, satisfies the intended
product contract; this document does not silently substitute it for (3).

## Candidate A — Fixed Campaign Total Envelopes

**Best concrete next engineering profile:** one owned Google advertiser, supported Search/
manual-CPC campaigns, each with an independent finite total budget and explicit schedule.
Current Google documentation supports this combination. Total budgets use `CUSTOM_PERIOD`,
`total_amount_micros`, and `explicitly_shared=false`; campaign start/end use datetime fields.
[API overview](https://developers.google.com/google-ads/api/docs/campaigns/budgets/overview),
[exact creation fields](https://developers.google.com/google-ads/api/docs/campaigns/budgets/create-budgets).

Google describes a campaign-charge ceiling equal to its total budget and no daily limit.
Search campaigns use a 3–90 day duration. An existing daily-budget campaign cannot switch
budget type: this profile applies to already eligible total-budget campaigns or a newly
reviewed campaign, never an automatic replacement of the customer's existing campaign.
[Total-budget behavior and constraints](https://support.google.com/google-ads/answer/10486938).

Proposed enforceable Inlet constraints:

- Customer approves fixed per-campaign envelopes `E1..En` and exact account, currency,
  native resources and period. Their sum, plus separately retained obligations, fits
  the unchanged overall mandate. Cross-platform allocations must also remain covered.
- Inlet never requests a campaign total above its envelope, changes budget type, shares
  a budget, extends the approved schedule, resumes a paused campaign, adds owners, or
  raises billing/account limits. No API operation outside the reviewed allowlist.
- Keep each **full original envelope reserved**. A lower observed cost, paused status,
  a lowered budget or delayed reporting does not free funds for another campaign.
  New/unknown prior liabilities or an unverifiable prior larger cap prevent eligibility.
- Fresh exact ownership/topology/configuration checks before requests and semantic
  readback afterward. Any known external budget/schedule/owner change suspends further
  optimization and invalidates the review. This detects drift; it is not native CAS.
- Initially restrict automated writes to PAUSED, or budget decreases within a separately
  qualified total-budget transition. Pause does not assert zero residual cost. Restore/
  increases, even within an envelope, need an additional reviewed transition profile.

Example: a $1,000 mandate funds A=$600 and B=$400. Pausing A or lowering its setting to
$300 leaves A's entire $600 allocated; Inlet cannot increase B to $700 from an apparent
$300 saving. This avoids pretending reporting is final and preserves the original total.
It is deliberately conservative, with limited reallocation, but still allows useful
automatic harm-reduction actions and a concrete path to bounded campaign optimization.

**Conditional bound, not proof yet:** if every campaign's applicable lifetime billed
charge is bounded by its approved envelope and the portfolio/retained liabilities are
complete, summed envelopes can bound that financial domain without guessing reporting
lag. Native cap decreases after previous spend, history, adjustments and the precise billed
basis still need a reviewed source specification. Do not fill existing U/F/P with zero or
double-count/erase reservations to force it into the component API. The existing
[joint-envelope design](google-joint-envelope-proposal.md) remains proposal-only.

## Candidate B — Existing Daily Campaigns Under A Finite Account Budget

Monthly-invoicing account budgets add a finite amount/end boundary across an account;
Google says ads stop when the amount is used or the period ends. This can contain existing
DAILY campaigns and new siblings while the effective account cap remains unchanged.
Unlimited budgets do not qualify. [Account budget behavior](https://support.google.com/google-ads/answer/2393037?hl=en).

Require an already approved finite budget, matching account currency/timezone and mandate
period, no ambiguous overlapping/pending/future replacement budget, and verified approved/
adjusted values. An account-budget proposal is not the effective budget: Google reviews
proposals before application. Inlet would read the cap only and never create/update/end
billing budgets as part of campaign optimization. [Account budget API](https://developers.google.com/google-ads/api/docs/billing/account-budgets).

This profile is a strong candidate for retaining existing-campaign scope, but excludes
customers without monthly invoicing and does not itself solve external changes. Billing
access is not cleanly separated by simply using a standard Ads role: standard/admin/
billing users at the paying manager or above can edit budgets and transfer billing.
[Paying manager permissions](https://support.google.com/google-ads/answer/9703430?hl=en).
Google-managed payments links restrict some setup actions, but their existence is not an
immutable account-budget promise. [Payments link types](https://support.google.com/google-ads/answer/15758513?hl=en).

A dedicated manager arrangement is an operational restriction to investigate, not a
proved native fence. Do not provision accounts or remove customer control from this
proposal. Google multi-party approvals document sensitive user/role actions, not a budget
cap lock; do not use MPA as that proof. [MPA](https://developers.google.com/google-ads/api/docs/oauth/multi-party-approvals).

## Attainable Now, Unknowns And Access

| Area | Attainable code/behavior | Still unresolved |
|---|---|---|
| Exact Inlet authority | Existing owned request/fence/session/mandate checks; retain every full allocation; allowlisted pause or qualified total-budget fields | Approval of the restricted operational mandate interpretation, not a new assumption in code |
| Google protocol | Actual DAILY adapter and exact synchronous original-success terminal source exist | Concrete total-budget compiler/readback/transition implementation; successful mutation is not cost settlement |
| Financial evidence | Native campaign/account budget diagnostics exist; no report-delay subtraction needed for a genuine full-envelope theorem | Exact billing basis/history/adjustment and complete same-period portfolio proof; conservative envelope composition not implemented |
| Outside writers | Inspect known current configuration; invalidate on observed drift; keep owned requests bounded | No native compare-and-swap or universal prevention established; customer promise alone cannot certify one |
| Qualification | Offline parser/compiler/ownership/race/retry tests can be completed | Approved access and controlled intended-environment validation; this assignment authorizes neither account setup nor live requests |

A pause-only request is structurally non-enlarging in what Inlet asks Google to configure,
but this is not proof that already incurred/future residual cost becomes zero. Qualifying
that narrow action without fabricating exposure requires a reviewed non-enlargement rule;
it must not bypass the current strict financial gate merely because it is called “safe.”

## Concrete Next Code Slice For Review

Implement **actual total-budget Search support in offline review/compiler/HTTP readback**,
not another empty proof interface:

1. Add a distinct typed budget variant to Google reviewed plans: positive lifetime micros,
   exact native-timezone start/end datetimes, unshared ownership and fixed approved envelope.
   Do not reinterpret DAILY amounts or change existing serialized social requests.
2. Compile the documented `CUSTOM_PERIOD`/`total_amount_micros` budget plus exact campaign
   datetimes, initially create PAUSED only; verify the exact resource response/readback.
   Existing campaign enrollment accepts only already-total-budget resources with complete
   history requirements; it never converts a daily campaign or auto-creates a replacement.
3. Add real MockHTTP journey tests for exact fields, incompatible daily/total payloads,
   missing/invalid dates, shared/multiple owners, currency/timezone mismatch, partial failures,
   changed schedules/caps, retry/no-duplicate behavior and review invalidation.
4. Preserve all current live financial/profile gates. Separately review the fixed-envelope
   accounting theorem and mandate interpretation before implementing/enabling automatic
   actions. This slice completes concrete provider support useful to both strict and
   restricted profiles; it does not claim that access alone finishes qualification.

Recommended review decision: advance Candidate A's concrete provider support, investigate
Candidate B for eligible existing accounts, and explicitly settle the operational boundary
of “within approved mandate” before any live source is qualified. Do not claim all
optimization impossible, adopt recommendation-only by default, or promise universal
outside-writer protection. No owner limit or acceptance is changed here.

Validation: code/audit-scope inspection and official-source review; docs-only diff and
relative-link checks. No tests or live verification claimed.
