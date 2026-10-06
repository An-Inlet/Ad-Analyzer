# Restricted Meta And TikTok Operating Profiles

2026-10-06; documentation proposal from `c6d72b6`. No runtime registration,
qualification, gate relaxation, live calls or claim change. Recommendation-only
versus automatic operation remains an owner decision; this document adopts neither.

## Obligation And Evidence Boundary

The retained audit requires Meta/TikTok actions and reviewed publication, with each
declared campaign type completing its journey and B07 mandate safety as a dependency
([retained criteria](../inlet-b15-b20-acceptance.md),
[timeline](../inlet-audit-timeline.md)). Original attachment bytes are unavailable in
this executor; these are the retained criteria, not a claimed rereading of the file.
The owner's explicit scope permits optimizing existing campaigns inside an approved
spending mandate, requires review of new campaigns/creative, and does not allow the
draft 5/10/20% aggressiveness inputs to enlarge the overall limit.

Separate three claims when evaluating a restricted profile:

1. **Inlet request obligation:** every Inlet-authored request has exact current scope,
   permitted fields, approved amount/period and durable action lineage; local workers
   cannot independently spend the same allowance. This is enforceable by Inlet.
2. **Conditional native envelope:** the provider documents a limit for a particular
   eligible configuration while that configuration and its accounting basis remain
   applicable. This needs provider evidence and observed eligibility.
3. **Unconditional account ceiling:** all served/billed costs stay below a limit even
   through outside edits, cap resets and unrelated writers. Neither an Inlet lock nor
   the reviewed public documentation establishes this claim.

The audit/owner scope does not itself require proving universal exclusive control of
all account writers. Conversely, removing that universal claim does not magically
qualify the current accounting proof. Existing exposure/reservation/settlement gates
remain unchanged. A future engineering review must specify which conditional native
contract is sufficient for a launch profile, and how known drift invalidates it.
Do not mark every external-writer scenario intrinsically impossible, or silently
translate a conditional contract into unconditional financial protection.

## Provider Evidence And Candidate Profiles

| Profile | Evidence and useful restriction | Remaining qualification |
| --- | --- | --- |
| Meta manual Sales/Auction, independent ad-set budget | Current adapter scopes the account, campaign and exact ad set, currency/timezone, manual objective, sharing/rebalancing/schedule flags and owner topology. The official SDK exposes budget/status fields and corresponding update inputs. Restricting writes to the existing budget field or `PAUSED` is implementable. | SDK field availability does not establish overdelivery, cap accounting, effective-time or atomic precondition guarantees. No current Meta help-page cap claim was retrieved successfully. |
| Meta campaign budget owner | Restrict to a fully enumerated approved owner pool; campaign-level status or budget affects that pool. Never call a child-only action independent if its budget is shared. | Complete topology and unsupported sibling features must be checked. Parent/child limit precedence, scheduled changes and a qualified native envelope remain required. This is not the preferred first bounded profile. |
| TikTok regular Web Conversions/Website, independent ad-group lifetime budget | TikTok describes lifetime budgets as a run-wide maximum, pauses delivery at exhaustion, and permits adding budget. Published daily/lifetime budget type cannot be switched. Require existing `BUDGET_MODE_TOTAL`, a finite unchanged run window, exact account currency/timezone, no Smart+ or campaign pool, and complete owner binding. | Need authoritative API field/value fixtures, effective budget/history, exact gross/net cost basis, delayed liability and provider behavior under concurrent updates. These docs do not establish immutable billing finality. |
| TikTok Budget Manager account cap | Official help describes daily/monthly/one-time caps and pausing account ads at the configured cost limit. It also documents edits, additions/deductions, resets and unlimited mode. A finite one-time cap with a known counting origin is worth qualifying. | No qualified readable Business API snapshot mapping all cap/reset/history semantics exists in Inlet. UI configuration is not machine-verifiable proof. Inlet must not silently create/edit account caps under campaign authority. |
| Both providers, pause/disable only | Existing action unions allow Meta `PAUSED` and TikTok `DISABLE`, not resume. Exact status-only serialization cannot itself request activation or a budget increase. | Observed status is not delivery cessation, zero residual spend, irreversible disablement or settlement. Existing gates still apply; a distinct restrictive-action admission policy would require review before any bypass. |

Primary sources:

- [Meta pinned AdSet SDK](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adset.py),
  [Campaign SDK](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/campaign.py),
  [AdAccount SDK](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adaccount.py).
  Schemas only; source commit checked locally. The bounded live-document lookup of
  [Meta pricing](https://www.facebook.com/business/ads/pricing) and
  [daily budgets](https://www.facebook.com/business/help/190490051321426) redirected
  to a blocked login page. No third-party overdelivery percentage is adopted.
- [TikTok lifetime budgets](https://ads.tiktok.com/resources/help/article/about-lifetime-budgets?lang=en)
  (July 2026), [Budget Manager](https://ads.tiktok.com/resources/help/article/how-to-use-budget-manager?lang=en)
  (July 2026). The cap credit example is not a general taxes/fees or API accounting mapping.
- [TikTok dynamic daily budget](https://ads.tiktok.com/resources/help/article/about-dynamic-daily-budget?lang=en)
  describes up to 25% daily variation with Sunday–Saturday averaging. Exclude this
  profile initially; multiplying a current daily amount by remaining mandate days
  is not the same contract, especially after edits.
- [TikTok automated rules](https://ads.tiktok.com/resources/help/article/automated-rules?lang=en)
  explicitly include turning campaigns on and increasing budgets. An empty rule list
  at one instant, or a dedicated-account promise, is not a permanent writer fence.
- [TikTok pinned ad-group update SDK](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/business_api_client/models/adgroup_update_body.py)
  supports request-shape investigation, not invented response/enforcement semantics.

## What Inlet Can Enforce Now

Keep exact session/membership/connection-generation and approved target-set checks;
existing server-owned policy, account currency/timezone and mandate period; and the
single shared ledger, cumulative positive-change/action limits and durable dispatch
fence. New campaigns, new creative, resume, account-cap edits, target expansion,
period extension and mode switches remain outside this proposed action subset.

The existing transports perform bounded current-state reads, restrict request fields,
emit once, and reconcile the original attempt without mutation retry. A response
lost after emission remains unknown, with its original reservation and fence. Pause
or a smaller observed budget cannot release old holds. An observed outside change
invalidates pending work; polling is detection, not prevention. Restricting Inlet's
own credential and serialized fields limits its own requests, not unrelated accounts
or another administrator's permissions.

A particularly important race: Inlet reads budget100 and proposes90. Another writer
sets80 before Inlet sends90. The absolute write is now an increase relative to the
provider's intervening state. A preflight read and database lock cannot make that a
monotonic decrease without provider compare-and-swap/exclusive enforcement. Label it
an exact authorized absolute set, not a guaranteed non-increasing operation. Even a
status-only pause can later be reversed by another writer. Neither case grants
permission to exceed the customer's unchanged overall mandate.

## Concrete Offline Slice To Implement After Interface Review

Add a pure typed profile classifier alongside existing optimization contracts;
no migration, provider factory registration or admission change is needed initially.
Inputs are a validated existing current-state object, exact intent, current mandate
binding and a server-selected profile version. Output contains:

- exact account/connection-generation/owner/target-set/current-state commitments;
- `action_class`: status-only restriction, absolute budget set, or unsupported;
- fixed eligibility blockers for unknown sharing/schedules, dynamic/smart profiles,
  lifetime-window mismatch, currency/timezone mismatch or incomplete topology;
- `guarantee_scope`: Inlet request only; optional separately typed native-envelope
  reference, always absent until a qualified reader supplies it;
- explicit `concurrent_precondition`: unavailable for current transports, plus
  immutable requested-field/value commitment; no guessed external-writer assurance.

Do not combine profile eligibility and finite financial exposure in one boolean.
The classifier can be consumed by existing account diagnostics and offline review
explanations while production exposure remains unavailable. Any later conditional
native-envelope implementation must be additive and reviewed with the shared
[envelope proposal](google-joint-envelope-proposal.md), rather than setting unknown
residual or pending costs to zero.

Acceptance tests should invoke existing actual adapters with injected HTTP:
(1) exact status-only body, (2) forbidden extra fields/activation rejected,
(3) current-state drift invalidates prepared work, (4)100→80→90 race is classified
honestly rather than as an atomic decrease, (5) unsupported child sharing, missing
flags, mode/timezone/window changes block, (6) a timeout retains original attempt
and hold with no duplicate mutation, (7) same-epoch recalibration cannot mint another
allowance, and (8) absent native proof never yields a finite exposure bound. All
fixtures must identify their synthetic enforcement assumptions.

Recommended first engineering step: this classifier plus diagnostics and mocked
race evidence for independent owners. Investigate TikTok lifetime and one-time
account-cap qualification next; retain Meta's semantic-document retrieval blocker.
This advances an enforceable component without adopting recommendation-only launch
or claiming safe live autonomous optimization prematurely.

## Verification And Remaining Decisions

Documentation-only package: existing adapter/schema and retained acceptance sources
inspected; bounded primary-web reads and pinned SDK commits checked. No tests, Full,
provider API/storage calls, credentials, mutations, merges or deployments. Local link
validation and `git diff --check` are recorded with the commit handoff. The owner
launch-mode decision, exact conditional native accounting contract and real profile
qualification remain open. B16/B17 completion is not claimed.
