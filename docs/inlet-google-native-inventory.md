# Google Native Inventory Diagnostics

This is a concrete read-only provider collector, not an exposure qualification profile. `GoogleNativeInventoryHTTP` performs fixed Google Ads v25 GAQL queries through the existing bounded wire transport. It has no runtime factory, database persistence, portfolio composer registration or mutation path. Tests inject HTTP; no live requests occurred.

The server-only request binds the exact workspace/account/connection generation, mandate binding, currency, timezone and period (maximum 366 days). Its credential context binds the request digest. The caller must authorize the current session/role and mandate/account ownership before IO and recheck those bindings afterward before persisting or using diagnostics. The collector does not commit or release transaction locks. Missing/changed identity, currency, timezone, pagination or malformed response data fails closed.

Actual selected provider data:

- All paginated campaign rows, including enabled, paused and removed states, other campaign types, schedules and native budget resources. No campaign names, audiences, ads or search-term text are requested.
- Native budget amount/total amount, sharing, reference count, period/type/status. The inventory includes other owners, not just the campaign being optimized. Missing budget references and active owner-count mismatches report a changing/incomplete advertising inventory.
- Observed account `metrics.cost_micros` for the full native calendar dates intersecting the mandate period. These may include extra hours around partial-day boundaries. A missing amount stays null; this is an observed metric, not final billing or a completeness watermark.
- Billing setup identities/statuses and every returned account budget: proposed, approved and adjusted amount/type, proposed/approved start/end fields, pending proposal resource, and amount served. No filtering to the current budget hides an already-created future replacement. Missing billing access/transient read failure is explicitly incomplete, not a successful empty inventory.

Responses are projected into typed snapshots; raw payloads and credentials are not stored or logged. Existing fixed wire bounds are 2 MB per response, 12-second IO/5-second connect timeout, identity encoding, no redirects/environment proxies, and private HTTP logging. This collector adds 200 rows and 10 pages per inventory, duplicate/cycle rejection, and a 60-second operation deadline checked before/after each bounded request. A request already in progress can consume its bounded IO time before a deadline check. Credential expiry is rechecked after each page. No automatic retries occur.

`advertising_inventory_read_complete` and `billing_inventory_read_complete` mean the selected bounded reads completed and references matched. They do not claim an atomic provider snapshot or complete future portfolio. `reporting_watermark`, `unreported_upper_micros`, `unchanged_future_upper_micros`, and `proposed_owner_upper_micros` are typed as null only. `cap_semantics` can only be `unqualified`. A finite budget, zero observed spend, a lower current budget or a successful read cannot change those types. The result is not `PortfolioFacts` and cannot be registered as qualified evidence.

Related design records: [native exposure assessment](design/google-native-exposure-qualification.md) and [joint-envelope contract proposal](design/google-joint-envelope-proposal.md). Neither registers a qualified profile or changes policy.

## Qualification And Repeat-Optimization Boundary

A later qualified source needs an explicit accounting basis, enforced cap coverage for every account/owner and the whole mandate period, a demonstrated configuration-writer boundary, and a valid joint accounting model for reported, delayed, future and reserved exposure. Current snapshots alone do not prove those facts. The source must bind its result to the exact plan/target/native budget identity, account generation, mandate revision/currency/period, observation interval and evidence version. It must preserve unresolved earlier attempts and reservations.

For repeat optimization of one native owner, do not infer that lowering its current budget releases the previous reservation, or subtract a prior reservation merely because a new action refers to the same campaign. A timeout can leave an unresolved prior effect, reporting can arrive later, and the native cap may have changed externally. A replacement protocol must explicitly bind old and new owner states and the exact reservation being superseded under durable ledger serialization. This collector supplies observations, not authoritative absent-effect, settled-cost or reusable-residual-cap proof. No `U=0`/`F=0` default or invented reporting-delay allowance exists.

Concrete release decisions still required:

1. Does the approved spending amount mean net billed media, gross served media, or all-in cash including taxes/fees? Current provider metrics cannot be silently relabeled, nor may ledger high-water marks be reduced to fit billed caps.
2. What enforceable restriction prevents another writer from raising/replacing native caps or adding exposure outside them? A dedicated account or customer promise alone does not establish that restriction. Until it is demonstrated, strict ceiling behavior remains fail-closed. Best-effort monitoring is a different product guarantee and is not authorized.

A monthly-invoicing finite whole-account budget is the strongest candidate for future qualification; all effective/adjusted/pending/future coverage still matters. Newly reviewed Search/manual-CPC total-budget campaigns are another candidate engineering profile, but do not cap other campaigns and cannot convert existing daily-budget campaigns in place. Neither candidate is enabled by this package.

Primary evidence checked 2026-10-06:

- [Account budgets API](https://developers.google.com/google-ads/api/docs/billing/account-budgets): proposed/approved/adjusted values, pending proposals, updates and replacement budgets.
- [Account budgets help](https://support.google.com/google-ads/answer/2393037?hl=en): monthly-invoicing availability and amount/end-date behavior.
- [Spending limits](https://support.google.com/google-ads/answer/10486637): billed versus served cost and overdelivery adjustments.
- [Data freshness](https://support.google.com/google-ads/answer/2544985?hl=en): hourly reporting is an SLO with delays and later adjustments, not a bounded completeness guarantee.
- [Campaign budgets](https://developers.google.com/google-ads/api/docs/campaigns/budgets/overview) and [total-budget constraints](https://support.google.com/google-ads/answer/10486938?hl=en): Search/manual-CPC support and new-campaign-only budget-type selection.

Remaining work: reviewed server persistence/runtime composition and a genuinely qualified exposure source. No credential-only blocker is claimed for these engineering and policy requirements.
