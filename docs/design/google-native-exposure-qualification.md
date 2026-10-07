# Google Native Exposure Qualification Assessment

2026-10-06. Read-only engineering assessment; no provider requests, credentials, activation, migrations, or runtime changes. Source contract inspected at `5bcd0aabaabc4e20c77a3b44713330a40a96651f`, `app/publication/exposure_qualification.py`. Actual optimization adapter inspected in the preceding PR157 delivery, head `97fd992cffa68d138d4e4f6e9fe9911791fdf867`.

Related: [joint-envelope contract proposal](google-joint-envelope-proposal.md), [implemented native inventory diagnostics](../inlet-google-native-inventory.md), and [current exposure composer](../inlet-exposure-qualification.md).

## Decision

The existing Search/manual-CPC/independent DAILY budget profile is **not qualified** to prove a strict total spending mandate. There is no defensible finite reporting-delay allowance derived from the published reporting SLO. Reading a native cap immediately before mutation also cannot bind future exposure if other authorized writers can raise that cap or add uncapped campaigns afterward. This is a capability and accounting-semantics gap, not just missing credentials.

There are two concrete native-cap candidates worth implementing as read-only evidence collectors: whole-account monthly-invoicing budgets, and finite campaign total budgets. Neither should be registered as a live `qualified_native_cap` profile merely because its fields are available. Both require a proved accounting basis and a configuration-control boundary for the full mandate period. No such boundary is currently represented/proved by the reader. **No currently reviewed Google preventive writer mechanism qualifies. Adding typed proof fields cannot close the strict-cap acceptance gap.**

## Native facts and limits

| Mechanism | Actual evidence | Consequence for Inlet |
|---|---|---|
| Average daily campaign budget | Google documents daily and monthly billed-cost limits for most campaigns; served cost can exceed them with later adjustments. | `amount_micros` is not an overall spend ceiling and cannot cap gross served cost. [Spending limits](https://support.google.com/google-ads/answer/10486637). |
| Daily budget changes | The day's limit uses the highest daily budget that day; changing a budget also changes the remaining month's calculation. | A current lower amount does not bound earlier unreported cost. Current snapshots cannot reconstruct the requisite maximum/history. [Budget changes](https://support.google.com/google-ads/answer/10487143). |
| Campaign total budget | Current API docs support Search with Manual CPC, using `total_amount_micros` and explicit campaign start/end times. | A finite independent total-budget Search profile is technically distinct from PR157's DAILY-only profile. It needs explicit types, validation, publication/review support, and tests. [API budget overview](https://developers.google.com/google-ads/api/docs/campaigns/budgets/overview). |
| Campaign total-budget constraints | The help page promises charges no greater than the total budget, no daily limit; Search duration is 3–90 days. Existing daily-budget campaigns cannot switch budget type. | This offers a candidate billed-media envelope for new reviewed campaigns, not an automatic migration of existing campaigns. Other portfolio campaigns still need coverage. [Total budgets](https://support.google.com/google-ads/answer/10486938?hl=en). |
| Account budget | Monthly-invoicing advertisers can set account amount/end limits; ads stop when exhausted or ended. Unlimited account budgets do not supply an amount cap. | This is the strongest candidate for containing newly created campaigns inside one account, but not available to every initial Shopify customer. Payment thresholds must not be substituted. [Account budgets](https://support.google.com/google-ads/answer/2393037?hl=en). |
| Account-budget approval and changes | Proposed, approved and adjusted limits differ. Credits can change adjusted limits. Pending proposals exist; budgets can be updated or replaced/chained. | Collect effective finite limits, approved intervals, billing setup, adjustments and every pending/future overlapping budget. A proposed amount alone is not enforced proof. Reject ambiguous or unlimited coverage. [Account budget API](https://developers.google.com/google-ads/api/docs/billing/account-budgets). |
| Reporting | Click/impression/cost hourly freshness is an SLO with temporary delays; later adjustments can occur. | Neither `fetch_finished_at` nor `now − 1 hour` proves that earlier cost is complete. Do not synthesize a completeness watermark or finite delayed-cost reserve from this SLO. [Data freshness](https://support.google.com/google-ads/answer/2544985?hl=en). |
| External-change detection | Change events have a 30-day query window, a 10,000-row limit and possible three-minute delay; they do not include every change visible in web history. | Useful diagnostics, not an atomic snapshot, CAS, spending fence or proof that no writer will change a cap. [Change Event](https://developers.google.com/google-ads/api/docs/change-event). |

## Why the current proof cannot be completed

Counterexample: Inlet reads a $100 remaining native cap, authorizes a within-mandate action, and an independent authorized writer subsequently raises that cap to $1,000. Google can then serve under the new configuration before Inlet observes the change. Short evidence expiry, post-read checks, change-event polling and pause-on-drift reduce detection time but cannot establish the requested invariant. The same problem exists when a new campaign appears after a complete campaign inventory. An unchanged account-level cap could contain that campaign, but an externally mutable account cap cannot.

Likewise, reported spend of $70 and a nominal one-hour lag do not prove at most $30 of omitted spend. The provider gives no deterministic maximum delay here. A genuine enforced whole-period cap can bound combined past/unreported/future cost without a reporting-delay assumption, but only in that cap's accounting basis and while its enforcement/configuration assumptions remain true.

Net billed media cost, gross served cost, and total cash charges including taxes/fees are different quantities. Do not relabel `metrics.cost_micros` or lower the existing ledger high-water mark to fit a billed-cap argument. Any conversion between bases needs explicit, source-supported accounting and versioned policy; late credits must not automatically release held reservations.

## Mapping to the current reader

The reader composes `R + H + U + F + P`: reported spend, held reservations, unreported upper bound, unchanged future upper bound, and proposed owner's upper bound. It correctly requires exact mandate-account coverage, native ownership generations, currency/period/plan lineage, freshness, non-null bounds, and reported spend at least the ledger high-water mark. It deliberately does not establish native semantics.

An account-level envelope is a **joint** bound across these components. If `R + U + F + P <= C` is proved, it does not follow that `U=0` or `F=0`. The existing component API cannot simply place the remaining account cap into one field while leaving the other nonzero exposures at zero. Independent conservative component bounds can overcount the cap, safely but often prohibit execution. Efficient joint-envelope composition would need a separately reviewed typed proof and reconciliation rules; it is not a source-reader shortcut.

For example, for a genuinely fixed per-campaign billed lifetime cap `Cj`, each of its unreported and remaining future portions is individually no greater than `Cj`. Using each full cap as a component bound is conservative and avoids pretending reports are final, but doubles some exposure. Subtracting reported cost requires a proved compatible, non-reversing accounting basis; do not assume it from ordinary metrics. Keep the proposed owner excluded from `F`, never from its historical unreported exposure. Hold existing reservations exactly as the current reader requires.

The source signature currently takes `CreationPlan`; optimization requires its own reviewed plan binding or an explicit common interface. Do not coerce an optimization request into a fake creation plan. The cached source must not release the coordinator transaction or perform provider mutations.

## Concrete Engineering Package

The following package was subsequently implemented as [PR167](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/167), head `16fd3b907177b0446ffda63a694ff6fb753baa2e`; see [native inventory diagnostics](../inlet-google-native-inventory.md). These are diagnostic inputs, not qualified proof:

1. Read every exact mandate account with current connection generation, customer currency/timezone and identity. Page all campaigns and budgets, including paused/scheduled owners and historical owners relevant to the mandate period; do not filter to the optimized Search target. Preserve native budget ownership topology and reject truncation, duplicate pagination, unrecognized enums, missing accounts and unbounded inventory.
2. Collect account-budget/billing-setup identities, statuses, finite approved/adjusted limits and effective intervals, pending proposals and all overlapping future budgets. Missing billing permission or monthly-invoicing support is an explicit capability result, not an empty portfolio.
3. Collect reported cost by native account/campaign/date with the query interval and observation timestamps. Keep provider-reported completeness distinct from local fetch time; if no authoritative completeness value exists, record that absence. Preserve immutable evidence plus changed-budget diagnostics without claiming snapshot atomicity.
4. Emit named reasons such as `daily_budget_not_total_cap`, `reporting_completeness_unproven`, `external_writer_boundary_unproven`, `billing_basis_unqualified`, `portfolio_incomplete`, `pending_cap_change`, and `unsupported_total_budget_profile`. Keep `U`, `F`, or `P` null as appropriate; no live qualification registration.
5. Mock regressions: hidden owner on later page; account generation change; missing account; currency/timezone mismatch; cap lowered after earlier high budget; pending increase; future replacement budget; unlimited cap; late cost outside assumed one-hour window; external creation/cap increase between reads; gross-versus-billed adjustment; retained reservation from an earlier period. A complete read must not itself turn any of these into qualified authority.

This yields useful customer readiness diagnostics and the real provider-backed evidence path without inventing a guarantee. It also identifies eligible account configurations before spending time on total-budget publication support.

## Narrow owner choices and recommendation

Recommended: retain strict total-mandate behavior and fail closed for unqualified accounts; proceed with the collector above. Determine whether the customer's spending mandate is **net billed media cost** or a stricter gross/all-in amount. No choice has been applied by this assessment.

Only after a real enforceable mechanism is demonstrated should the owner decide whether its required restricted customer account configurations are an acceptable launch profile. No restriction or monetary basis is approved here.

If choosing billed media cost, the first candidate to qualify is a finite whole-account native budget with complete period coverage and an enforceable restriction on budget-changing writers. A dedicated account may simplify ownership but is not, by itself, proof: another administrator able to change caps remains an external writer. Establishing that restriction is still engineering/provider-evidence work; a checkbox promise is insufficient for a hard ceiling.

Alternatively, explicitly choose a monitored, best-effort guarantee for customer-controlled external changes. That would change the product's mandate semantics and requires an owner decision, new customer disclosures and policy design; it is not authorized by the present assignment and should not be implemented implicitly.

Campaign total budgets are a subsequent bounded implementation option for new reviewed Search campaigns. They do not remove the need to bound every other account/campaign or prevent cap increases. Keep current existing-campaign optimization and new-campaign review authority separate.

Assessment validation performed: read the cited source contract and official documentation only. The later collector package has its own separately recorded test evidence. No runtime tests or live verification are claimed. No operational configuration changed.
