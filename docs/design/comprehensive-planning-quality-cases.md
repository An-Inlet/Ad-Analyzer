# Comprehensive Planning Quality Cases — Frozen Inputs V1

Frozen before new comprehensive-plan composition on 2026-10-08. This document
defines synthetic acceptance inputs and required outcomes, not a passing evaluation
or evidence of expert or live-customer review. Changes to cases require a new
revision with reasons; implementations must not weaken cases to match their output.
Exact API and persistence assertions follow the reviewed aggregate contract.

## Common Basis

All names, identifiers and amounts below are synthetic. A current owner session,
paid read entitlement and owned Shopify store are available unless a case overrides
them. Use USD and America/New_York, a closed September 2026 reporting month, a
closed August comparison month and a November 2026 planning period. Reporting
dates are distinct from the future budget dates. The confirmed goal is $12,000
Shopify merchandise net sales against an $8,000 complete baseline. The November
customer budget ceiling is $1,000 (1,000,000,000 micros); the configured
aggressiveness is balanced. Product facts supplied by the customer: a reusable
travel mug, $25 list price, no approved health claims or testimonials, and one owned
product image. These facts are customer-supplied, not independently verified.

Account references use valid synthetic provider IDs and observed names, never
names as join keys. Use distinct owned advertisers and an unrelated foreign
workspace in authorization cases. Catalog observations preserve actual fixture
read intervals, expiries, source generations, native units and coverage. No
fixture implies a provider-specific budget unit, attribution window, event
definition, shared-budget owner or native status that it does not supply.

No case permits an advertising write. Every plan/export records planning-only
authority. Forecasts are unavailable unless a case supplies an explicit qualified
model; none of these cases does. Customer assertions and matching native fields
are independent facts; neither proves causal effect or who made a change.

## Cases

| ID | Input variation | Required result |
|---|---|---|
| Q01 Google positive conversions | One Google campaign and one observed ad group; 100 clicks, 10 selected conversions, $100 historical spend; exact selected event and reporting basis supplied. | No spend-without-conversions finding or equivalent rationale. Campaign and ad group are locatable by correct name/account/ID. Advice states its evidence and limitations; no forced budget change merely because data exists. |
| Q02 True zero and unavailable | Same as Q01, first with a present selected conversion count of 0, then with missing conversion evidence. | True zero may justify a specific tracking/landing-page investigation tied to that campaign. Missing is unavailable, never numerically zero. Neither case promises that pausing or reallocating will increase sales. |
| Q03 Meta-only brand | One connected Meta account, two campaigns with observed ad sets and known-status partial coverage; one customer product image; native amounts present but budget ownership/unit qualification unavailable. | Useful campaign-specific nonbudget actions and a feasible image brief, with placement/asset gaps and exact manual prerequisites. Planned allocation alternatives may be hypothetical, labeled as such. Proposed native budget amount/delta stays null with explicit missing facts. Google, TikTok and CRM connections are not required. |
| Q04 TikTok-only brand | One TikTok account, one regular-family campaign/ad group; observed names and references; no owned video; unqualified native amount semantics. | Useful scoped plan and a concrete video/storyboard brief with production steps and an asset gap. Regular-family limitation remains visible. No invented uploaded video, Spark authorization, campaign URL or native budget edit. Other platforms and CRM are optional. |
| Q05 Three-platform alternatives | All three owned platforms, one coherent goal/input revision. Customer supplies alternative A allocations Google $400, Meta $300, TikTok $200, reserve $100; alternative B $300/$400/$200/$100. | Each alternative independently totals $1,000, is never added to the other, and preserves customer-supplied provenance. Historical spend, planned allocations and native settings have distinct labels/units. No sum of platform conversions is described as unique customers or attributed Shopify sales. |
| Q06 Google shared budget | Two Google campaigns reference one observed budget owner; a third campaign has its own owner; all affected campaigns are supplied by qualified coverage. | Shared budget setting occurs once with both affected campaigns. Child planning allocations cannot be added again as independent native spend. Conflicting edits to the same owner fail. If affected-set coverage becomes incomplete, exact native edit is unavailable with a recovery step. |
| Q07 Ceiling and arithmetic | Reuse Q05, then submit $400/$400/$200/$100; another variant uses a negative allocation; another mixes currencies; another changes aggressiveness to assertive. | Over-ceiling, negative and mixed-currency scenarios are rejected. Changing aggressiveness alone cannot raise the ceiling. Exact integer arithmetic reconciles all allocations and reserve; no floating-point rounding loss. A higher ceiling requires a newly confirmed goal and corresponding input revision. |
| Q08 Zero budget and sparse brand | Confirmed ceiling $0, empty advertising history, customer product facts and image only. | No paid allocation or native amount increase. Provide useful prerequisite, measurement, creative preparation and learning tasks within stated unknowns; do not claim an evidence-backed performance forecast. Empty history is not a failing campaign. |
| Q09 Incomparable metrics | Google uses purchases, Meta uses leads, TikTok uses a different purchase attribution window; one reporting window is incomplete. | Preserve event/window/coverage distinctions. No cross-platform CPA ranking or automatic transfer justified by incomparable numbers. Specify what must be aligned or verified. A coherent qualitative plan is allowed; missing comparison cannot be hidden in a footnote while numeric rankings remain. |
| Q10 Constraints and facts | Customer excludes campaign A, fixes a $200 planning allocation for B, prohibits discount claims, has one image and no video, and limits production to one asset. | Exclusion/fixed allocation respected and counted once. Alternatives stay within the same ceiling. Creative work respects production capacity and distinguishes an asset request from an existing asset. No invented discounts, testimonials, health claims or revenue guarantees. |
| Q11 Correction and reconnect | Generate V1, then correct selected conversions/refunds, or reconnect one source with a new generation. Customer previously accepted one V1 action. | Referenced current advice becomes stale/unavailable as applicable. Refresh creates V2 with a field-level change explanation and exact source lineage. V1/its decision remain historical; no automatic decision carryover. Native names never cross-wire targets and stable identity is distinct from snapshot selection. |
| Q12 Concurrent version and decision | Two edits name the same expected current version; repeat one exact request; reuse its idempotency key with changed input; accept an obsolete or changed action digest. | One CAS successor wins; loser conflicts without a partial head. Exact replay returns original outcome; changed key reuse conflicts. A stale/changed action cannot gain a current decision. No execution mandate, consent or financial obligation is created. |
| Q13 Reported versus observed | Customer reports applying one exact action, later corrects/retracts it. Separate reads exactly match proposed fields, partially match, conflict, or cannot qualify units/ownership. | Append-only report/correction history retained with actor and claimed time. Read results are independently exact/partial/conflict/unavailable and show evidence/time. Customer report never sets provider-verified status. Matching fields never assert cause, change time or business lift. |
| Q14 Missing and ambiguous targets | Referenced target disappears; child has an unknown parent; two campaigns share a name; new campaign is manually created with the suggested name only. | No name-only rebinding or arbitrary fallback. Missing/ambiguous targets and topology changes require owned re-selection/fresh evidence. Unsupported manual verification remains unavailable. |
| Q15 Scope, revocation and malicious text | Foreign account/settings selection, membership/session revoked during I/O, expired read, and names/notes containing HTML or spreadsheet-like formulas. | Reject foreign/mismatched references and post-I/O authorization/expiry failures before save/export. Browser and readable export display text safely. CSV, if ever added, neutralizes formulas. No raw secrets or foreign evidence appears in errors or exports. |
| Q16 Privacy, history and progress | Erase scoped customer data after V1; request export/history. Separately import later Shopify closed-day progress and corrections. | New aggregate/evidence/history records follow lifecycle erasure rules and cannot resurrect removed data through export or refresh. Progress distinguishes customer task completion from observed net sales and late corrections; it never calls association causal lift. |

## Evaluation Gates

Deterministic tests must verify ownership, exact sums, source lineage, no fabricated
facts, lifecycle conflict behavior and zero writes. Reader fixtures must exercise
the actual service/API boundary, not construct a passing plan directly in place of
generation. At least Q01–Q05, Q11–Q13 and Q15 need customer API coverage; the
assembled HTTPS/browser journey must cover goal confirmation, plan read, successor
edit, decision, application report, export and progress with escaped native names.

For each provider-alone case and Q05, record a separate expert assessment for:

1. Correct scope, source facts and metric semantics.
2. Campaign-specific usefulness: a customer can locate the target and act or
   knowingly defer using concrete prerequisites and manual steps.
3. Coherent budget and alternatives without invented native settings or forecasts.
4. Traceable rationale, assumptions, uncertainty and a defensible maintain option.
5. Feasible creative brief respecting supported facts and customer capacity.
6. Honest decision, application, observation and outcome labels.

Each criterion is pass/fail with evidence and a reason. A numeric average cannot
hide a wrong target, fabricated claim, spending violation or unusable action.
Automated and agent review results are recorded separately from human expert
review. Human expert and authorized live-pilot gates remain outstanding until
actually completed. A valid schema, populated catalog or green test suite alone
does not qualify comprehensive planning quality.
