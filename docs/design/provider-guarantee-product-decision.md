# Provider Guarantees And Product Decision

Proposal for owner/root review, 2026-10-06. Based on frozen `a4fcd3a`, Google composition
PR210 and social-semantics assessment `dbf2263`. No contract, runtime, provider or product
claim is changed. No live account calls. This separates evidence classes rather than
calling every missing guarantee a credential blocker.

## Evidence Matrix

**Code:** implementable offline. **Access:** provider approval and intended-environment
verification. **Contradicted:** the proposed guarantee conflicts with documented behavior.
**Unverified:** no reviewed authoritative proof; includes inaccessible documentation.

| Provider | Native financial bounds and preventive writers | Action timing / correction assurance | Code versus access |
|---|---|---|---|
| Google Ads | **Documented:** daily budgets are averages; supported total budgets exist, including Search/manual CPC with explicit start/end. **Contradicted:** a daily setting is a hard daily served-cost cap; served cost can exceed billing limits. A billed limit is not an arbitrary unchanged Inlet portfolio mandate. **Unverified:** complete U/F/P and a native boundary preventing external cap raises, new owners or resets over the obligation window. [Budgets](https://developers.google.com/google-ads/api/docs/campaigns/budgets/overview), [served versus billed](https://support.google.com/google-ads/answer/1704443?hl=en). | Exact retained successful synchronous single-update configuration responses have the approved narrow original-request terminal reader. **Unverified:** terminality after timeout/lost response, cost finality, delivery-stop latency and an atomic cross-writer compare-and-swap. Completion is not financial settlement. [Synchronous mutates](https://developers.google.com/google-ads/api/docs/mutating/service-mutates). | **Code:** current DAILY transport, diagnostics and owned terminal/composition plumbing exist. Total-budget profile/compiler, versioned billing-basis mapping and any provider-backed transition/portfolio producer remain code. **Access:** approved Google project/OAuth/account capabilities and exact-profile read/write qualification. Access cannot prove missing financial guarantees. |
| Meta Ads | **Documented schema:** account/campaign/ad-set budgets and cap fields. **Unverified:** cap/reset/billing semantics sufficient for U/F/P, complete residual liabilities and preventive control of external writers. The SDK's field existence is not a hard-cap theorem. Relevant semantic references returned 429; do not label their contents disproved. [Account SDK](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adaccount.py). | Direct budget-update transport acknowledges `success=true`. **Unverified:** endpoint-qualified completed-mutation timing and unknown-request closure. Generic SDK success also covers unrelated response shapes, so it is insufficient. No verified pause-to-zero-cost bound. [SDK response logic](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/api.py#L83). | **Code:** transport and scoped diagnostic inventory exist; exact original-response capture/reader is missing pending endpoint semantics. Financial/billing adapters remain missing. **Access:** app permissions/account eligibility and live validation after code/semantics qualification; not a substitute for either. |
| TikTok Ads | **Documented:** Budget Manager pauses an account at its configured cap, but supports edits, resets and unlimited mode. **Contradicted:** that mutable setting alone prevents authorized external writers raising the limit. **Unverified:** effective API cap/reset epoch, complete cost basis/residuals, prevention of future competing changes. [Budget Manager](https://ads.tiktok.com/resources/help/article/how-to-use-budget-manager?lang=en). | Generic code/request ID is acknowledgment/correlation, not reviewed terminality. **Unverified:** exact regular campaign/ad-group update completion semantics; relevant manual pages returned empty bodies. No verified unknown-request closure or pause-cost cutoff. [Response SDK](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/InlineResponse200.md). | **Code:** regular update transports and bounded regular inventory exist, excluding unproved family completeness. Budget Manager parser, financial producer and typed original completion reader remain missing pending schemas/semantics. **Access:** app/account scope and exact-profile live verification. Do not guess Smart+/GMV Max equivalence. |
| Shopify | This is merchandise-sales measurement, not advertising-spend enforcement. **Documented:** orders are mutable; historical access beyond 60 days needs additional approval. **Unverified:** immutable full-history snapshot, deterministic correction cutoff and maturity from elapsed days. [Order reference](https://shopify.dev/docs/api/admin-graphql/latest/objects/Order). | **Documented limit:** webhook deliveries may duplicate; failed deliveries are retried a bounded number of times and reconciliation is recommended. No exactly-once or never-missed correction promise follows. `updatedAt` is last modification time, not a universal settled-sales watermark. [Webhook delivery](https://shopify.dev/docs/apps/build/webhooks/verify-deliveries). | **Code:** incremental reconciliation, agreement/refund normalization, independent full traversal and owned versioned publication exist. `ScanCompletion.correction_state` remains unresolved. Operational refresh/alert/reconciliation and tested correction handling can be improved without claiming finality. **Access:** approved history/protected-data scopes and development-store refund/edit/replay verification. Live examples do not establish universal correction finality. |

`U/F/P` means unreported cost, unchanged-owner future exposure and proposed-transition
exposure. None can be silently zeroed. Source eligibility is distinct from eventual
billing reconciliation. The [source matrix](production-spending-source-readiness.md)
and [social assessment](meta-tiktok-native-exposure-assessment.md) contain deeper limits.
Implementation references: `app/publication/google_request_terminal.py`,
`app/executors/{google,meta,tiktok}_optimization.py`, `app/collectors/native_diagnostics.py`,
`app/commerce/{sync,ledger,independent,independent_owned}.py` and
`app/commerce/independent_contracts.py`. PR210 adds composition, not missing native bounds.

## Is The Strict Product Promise Currently Implementable?

Not for arbitrary customer accounts with uncontrolled external writers on the evidence
available. This is not a proof that no restricted provider configuration can ever work.
However, no credential grant, successful test campaign or additional disabled interface
makes an immutable total-spend guarantee true. The current strict runtime must stay
blocked until an enforceable mechanism and compatible complete financial source exist.

An Inlet-local mutex cannot serialize independent provider administrators. A fresh read
followed by a write without native CAS cannot guarantee that no intervening external
change is overwritten. An exact payload can prove what Inlet requested; it cannot promise
what the whole account will spend or when the platform completes/delivers it.

## Concrete Decision — Recommendation

**Recommend a recommendation-only initial release, with connections, goal planning,
illustrative budget scenarios and revisioned observed progress.** Customer approval can
record intent or prepare an export for manual application, but must not call a write API.
This is a deliberate partial product release, not completion of autonomous optimization.
Commercial viability/pricing still needs owner judgment; this document does not authorize
charging for a different promise.

A possible later product is **customer-approved configuration control**, with the narrower
promise: “Inlet sends only the exact account settings you approved, within the approved
setting limits; provider charges and changes made elsewhere remain outside that control.”
It requires a separate versioned authorization policy, explicit setting units and scope,
provider access/verification and error reconciliation. Approval alone is not a financial
cap and cannot enable the existing strict runtime. Recommend requiring each change's
approval first; do not infer standing autonomous authority from existing aggressiveness.

### Exact Acceptance Changes Requiring Approval

| Acceptance dimension | Recommendation-only release | Later configuration-control option |
|---|---|---|
| Existing-campaign actions | **Zero provider mutation calls**, including pause; proposals only | Each exact supported change approved; native budget setting limit replaces a *claimed total-spend guarantee* only under a new explicit policy |
| Customer spending limit | Planning target/scenario, clearly labeled; strict execution remains blocked | Separate setting-unit limits and observed-spend alerts; no guarantee of total served/billed spend or control of outside writers |
| New campaigns/creative | Reviewed draft/export only; **zero publication calls** | Existing exact review requirement retained; each supported publication journey must separately qualify |
| Timing / outcomes | No execution-time promise; display source observation age | Show requested/acknowledged/verified/unknown separately; no exact delivery/effective-time promise; unknown attempts are not blindly replayed |
| Shopify progress | Revisioned observed merchandise-sales figures, correction-unresolved disclosed; no settled, causal or guaranteed milestone claims | Same; corrections invalidate affected evidence/reviews as required; no promotion to mature evidence solely by waiting |
| B15/B16/B17/B20 acceptance | Publication, autonomous action, maturity-gated automated feedback and live autonomous pilot remain **incomplete**, not renamed passed | Re-specify action/pilot scope explicitly; financial strict-cap acceptance still remains incomplete unless independently proved |

Unchanged in both options: ownership/session isolation, privacy/deletion/retention,
entitlements, exact review invalidation, bounded retries, auditability, no blind unknown
replay, no automatic new creative/campaign publication and no authority from draft
5%/10%/20% aggressiveness to increase any approved limit.

Owner decision requested later by the parent: choose **retain strict gate and defer
write-enabled launch**, **recommendation-only initial launch (recommended)**, or commission
a separately specified configuration-control product. No unilateral relaxation is made.
A monetary-basis choice (served, net billed media, all-in cash) is still necessary for any
future spending guarantee, but cannot resolve external-writer prevention by itself.

Validation: bounded official-document review and code inspection; no tests necessary for
this prose-only proposal. No live account calls, implementation or runtime changes.
