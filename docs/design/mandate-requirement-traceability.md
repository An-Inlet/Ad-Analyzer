# Approved Mandate Requirements And Financial Evidence

Read-only traceability review, 2026-10-07, source `2a520d0d561ba18b8882e2884e50a200988de3d5`
(parent implementation baseline `ac26a67`). This changes no policy, runtime, authority,
qualification or acceptance criteria.

## Requirement Sources

The owner's implementation request explicitly says:

> Inlet may optimize existing campaigns within an approved spending mandate. New
> campaigns and creative require customer review before publication.

It also says draft 5%/10%/20% aggressiveness inputs do not grant permission to increase
customers' overall spending limits. These are direct requirements. They do not expressly
promise prevention of every future independent administrator's account changes.

The repository already records this distinction in
[candidate acceptance](../inlet-candidate-acceptance.md) lines 45–50,
[current acceptance](../inlet-current-acceptance.md) lines 88–92 and
[restricted Google profiles](google-restricted-mandate-profiles.md) lines 9–30 and 140–144.
The latter separates local action authority, provider-conditional financial limits and
universal outside-writer guarantees. Read the older
[native exposure assessment](google-native-exposure-qualification.md) in that context:
its outside-writer counterexample defeats the stronger guarantee; it does not establish
that the owner required that guarantee or that all restricted optimization is impossible.

The complete attached audit was not available as a readable local artifact in this
executor during this review. The progress ledger records its earlier Library read and
failed materialization. This review does not invent audit quotations or assert that its
unavailable text settles the monetary accounting basis. The direct owner request and
later recorded clarification above are the available requirement evidence.

## Traceability

| Requirement or choice | Current implementation/evidence | Interpretation |
| --- | --- | --- |
| Existing campaigns only within approved authority | `ProviderMandatePolicy`, exact account/target scope, original-session gates, current consent and operation checks | Required. Autonomous existing-campaign authority must not become new-campaign or creative authority. |
| Overall customer limit cannot rise through aggressiveness | Policy total/per-plan/positive-change caps; cumulative positive-change history in `optimization.py`; fixed ledger account set and currency | Required. Revisions, canceled/settled history, refreshes and new sessions cannot reset these obligations. |
| New campaigns and creative reviewed before publication | Exact immutable creation review/approval; separate activation review | Required. A supported budget profile does not waive approval. |
| Uncertain attempts cannot silently free money or replay | Durable fences, original attempts, retained reservations and settlement/replacement proofs | Necessary implementation protection for the approved allocation. Current settings, lower reported cost, age or a pause are not settlement. |
| `R + H + U + F + P` whole-portfolio upper bound | `execution_contracts.py:133–173`, `exposure_qualification.py:117–190` | An implementation-selected financial proof domain, not a verbatim owner formula. Preserve it until a reviewed alternative is implemented; never invent zero components or subtract incompatible spend. |
| Prevent all independent writers from ever changing caps, billing or scope | No demonstrated native universal mechanism; not a field expressly required by `ProviderMandatePolicy` | Stronger than the recorded original requirement. Some proposed source qualifications assumed it. Do not label it original scope or use its absence to silently reduce the product. |
| Emergency pause despite unknown/over-cap exposure, or after mandate expiry | [Containment proposal](../inlet-containment-policy-decision.md) remains pending | Separate authority decision. A structurally non-increasing request is not permission to override current gates or proof of zero residual cost. |

The account-set binding, currency isolation, monotone reported-spend high-water,
all-period held obligations and cumulative change limits remain relevant even if a
supported profile uses a conditional provider limit. They prevent real Inlet allocation
escapes and must not be removed as supposed outside-writer requirements.

## Recommended Next Financial Producer

Pursue a **finite Google Search total-envelope profile**, with the full original approved
envelope retained, rather than claiming arbitrary DAILY budgets are total limits.
This is a bounded profile proposal, not qualification or permission to dispatch.

Already implemented and reusable:

- `GoogleSearchTotalPublicationFields` and `GoogleCreateTotalBudget`, the Google compiler,
  serializer, exact review/customer UI, paused creation and separate activation.
- Owned native campaign/budget/account-budget inventory observations and current topology.
- Exact owned mandate/account/goal/ledger lineage and retained reservations.
- Original synchronous Google creation/activation completion capture. It proves supported
  original configuration-request completion, not financial settlement or delivery time.

Thus the “total-budget compiler missing” entries at lines 110 and 122–134 of the older
restricted-profile proposal are historical, not current blockers.

The useful next producer would bind those existing inputs into an exact **original
allocation plus current native envelope** observation: owned account/currency, native
campaign/budget identity, finite approved interval, unshared complete owner topology,
original reviewed total amount, original successful request commitment, current native
configuration and all retained ledger obligations. It must distinguish an Inlet-originated
new resource from an imported resource with unknown earlier liabilities. Lower current
settings never replace the original allocation. This supplies real facts to an eventual
financial profile; the observation alone is not a qualified upper bound.

Before that profile can produce financial authority, its source specification still needs:

1. An explicit financial domain: for example the provider's campaign-charge quantity,
   rather than an unstated mixture of gross served cost, net billed media, taxes and cash.
2. Exact applicability of the native total-budget ceiling, including earlier larger caps,
   adjustments and costs outside the covered interval. A fresh snapshot cannot prove the
   absence of an earlier raise-then-lower change.
3. Complete coverage of the approved allocation and retained liabilities. Every obligation
   not demonstrably contained remains counted; joint containment must not double-count or
   erase holds. Daily-budget conversions and uncovered campaigns do not qualify by analogy.
4. A reviewed conditional scope and drift policy: what Inlet authors within its fixed
   envelope, which provider assumptions apply, and how observed outside changes stop
   further authority. A local read/write sequence is not provider CAS.
5. Actual supported transition semantics before automatic budget changes. Existing total
   creation support does not imply an existing-campaign total-budget update adapter is
   qualified, nor that pausing/lowering permits reallocating savings.

A full-envelope calculation can avoid pretending delayed reports are final, but it cannot
smuggle a joint ceiling into `U` with `F=P=0`. The existing
[joint-envelope proposal](google-joint-envelope-proposal.md) needs a reviewed conditional
profile and actual consumer before implementation. Monthly-invoicing account budgets are
an alternative for eligible accounts, not a general Shopify-customer assumption.

## Actual Decisions Still Open

The narrow unresolved product decisions are the monetary basis and covered allocation,
and the exact customer-facing assumptions for a supported conditional native profile.
They are not a demand that the owner accept a newly invented universal guarantee.
Optional emergency/post-period containment remains a separate explicit consent question.

The [PR214 product-decision proposal](provider-guarantee-product-decision.md), lines 43–80,
proposes recommendation-only or separately specified configuration control and labels
both as scope changes requiring approval. Neither is an accepted replacement for the
original MVP. Do not revive those reductions merely because universal outside-writer
protection is unproved. Routine implementation of the approved product remains authorized;
changes to its financial promise require a concrete reviewed contract.

Recommended requirement wording: **Inlet may issue only actions covered by the customer's
unchanged approved allocation and exact review rules. A supported provider profile must
state the financial quantity and native conditions it can substantiate. Known drift
blocks further actions; uncertain attempts and financial obligations remain retained.
Inlet does not claim to prevent every independent account change.** This clarifies the
recorded scope; it does not authorize weaker accounting or live execution.

Validation: local source/document inspection and relative-link/diff checks only. No tests,
provider calls, qualification, guard changes or live acceptance are claimed.
