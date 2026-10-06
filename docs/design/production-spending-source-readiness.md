# Production Spending Source And Adapter Readiness

Reviewed `1c82e03` on 2026-10-06; frozen validation is untouched. This is a code and
primary-source assessment, not live qualification. Related: [Google native evidence](google-native-exposure-qualification.md),
[social native evidence](meta-tiktok-native-exposure-assessment.md), and [joint-envelope proposal](google-joint-envelope-proposal.md).

## Result

**Strict-ceiling execution is not merely waiting for customer credentials.** Actual
HTTP adapters, typed proof ports and durable accounting exist, but no production
source produces authoritative complete spending, preventive writer-control or
original-request finality evidence. There is no reviewed native prevention mechanism
that currently qualifies any of the three providers. Supplying account access cannot
fill missing adapter code, change the accounting basis, or manufacture that guarantee.
No daily-budget multiplication, balance, recent fetch, pause readback or reporting SLO
can be substituted for the missing evidence. Preserve fail-closed behavior.

Here R is compatible reported spending, H is every retained hold, U is omitted/pending
spending, F is unchanged future exposure and P is the proposed owner's transition
exposure. Unknown U/F/P stay null. These are independent from original-request finality.

## Code Readiness Matrix

| Path | Implemented at reviewed head | Missing engineering, not an access-only gate |
|---|---|---|
| Google selected-owner operations | [GoogleOptimizationTransport](../../app/executors/google_optimization.py): actual v25 Search/manual-CPC independent DAILY budget and pause HTTP, owner topology, validation and readback. [publication](../../app/executors/google_publication.py) and [activation](../../app/executors/google_activation.py) HTTP also exist. | Total-budget Search is not implemented in the reviewed mutation/review/compiler profile. Complete native cost proof, writer prevention and finality adapters absent. |
| Google portfolio diagnostics | [GoogleNativeInventoryHTTP](../../app/collectors/google_native_inventory.py): owned account/campaign/budget/billing inventory, proposed/approved/adjusted limits, pending proposals and observed cost. The result fixes watermark/U/F/P to null and semantics to unqualified. | No source converts this into valid PortfolioFacts. No durable authorized evidence cache, complete edit/reset history or prevention proof; no claim that paginated reads are an atomic snapshot. |
| Meta selected-owner operations | [MetaOptimizationTransport](../../app/executors/meta_optimization.py): actual v26 target and bounded siblings, independent child or owned campaign-pool budget/pause; [publication](../../app/executors/meta_publication.py)/[activation](../../app/executors/meta_activation.py) adapters. | Whole-account campaign/ad-set cap inventory and observations missing at this head. Selected siblings are not every portfolio obligation. Cap counters/reset/pending-history interpretation, qualified U/F/P and terminality producer absent. |
| TikTok selected-owner operations | [TikTokOptimizationTransport](../../app/executors/tiktok_optimization.py): actual v1.3 target/sibling reads and budget/disable; [publication](../../app/executors/tiktok_publication.py)/[activation](../../app/executors/tiktok_activation.py). | Whole-account inventory producer absent. Budget Manager effective/reset/history response mapping is not established by readable authoritative schema; do not invent it from advertiser balance. Qualified exposure and terminality producer absent. |
| Analytics imports | [Google read HTTP](../../app/google_connections/http.py), [MetaClient](../../app/meta/client.py), [TikTok read wire](../../app/tiktok/wire.py) consume provider reporting for customer diagnostics. | Ordinary reported metrics are not settled billed cost, a deterministic completeness watermark or proof of all historical liability. Existing import checkpoints cannot supply those semantics. |
| Component arithmetic | [PortfolioExposureReader](../../app/publication/exposure_qualification.py): exact account coverage, generation/consent, high-water, held-history and nullable bound validation. | No app constructs a provider-backed reader/profile. FactsReader accepts CreationPlan; optimization has a separate [OptimizationExposureReader](../../app/publication/optimization_execution_contracts.py) and no provider implementation. A common immutable plan/intent binding and cached, authorized source integration are still code work. |
| Repeat and settlement | [replacement](../../app/publication/replacement.py), [replacement contracts](../../app/publication/replacement_contracts.py), [settlement](../../app/publication/settlement.py): exact predecessor snapshots, original fences, atomic transfer, retained unknowns, qualified closure/settlement interfaces. | No native ReplacementReader or SettlementReader. Contract tests and the synthetic restore reader do not qualify a production source. Settlement additionally needs reporting completeness through last possible effect and zero remaining exposure. |
| Runtime and customer inventory assembly | [CustomerExecutionRuntime](../../app/publication/customer_runtime.py), [CreationRuntime](../../app/publication/coordinator_contracts.py), optimization, activation and settlement optional factories remain None. [ConfiguredOptimizationCatalog](../../app/publication/customer_optimization_catalog.py) performs real selected-target reads from explicit named inventory. | Credential/current-generation/context assembly, bounded automatic target discovery, profile registration, evidence refresh/cache and lifecycle invalidation are missing implementation. Do not label these only deployment configuration. A disabled diagnostic assembly can be built independently; live mutation assembly must not bypass absent proofs. |

## Provider Proof Eligibility

| Required source fact | Google | Meta | TikTok |
|---|---|---|---|
| R and accounting basis | Observed cost plus billing-budget counters readable; versioned served/billed/credits/tax mapping absent. | Analytics spend and SDK amount_spent exist; counter epoch and basis mapping unqualified. | Analytics spend exists; net-cost placeholder zero and credits make silent basis substitution unsafe. |
| U, omitted/pending cost | No deterministic complete-cost watermark or sound finite residual source. SLO is not an upper bound. | No authoritative residual/completeness producer. | No authoritative residual/completeness producer; delayed net-cost documentation is not a general immutable cutoff. |
| F, every unchanged owner | Native inventory diagnostic exists; mutable caps and unknown future writers prevent qualification. | Whole-account diagnostic still to build; cap/reset/enforcement and full ownership semantics unqualified. | Whole-account diagnostic still to build; account cap/reset API semantics unresolved. |
| P, proposed transition | DAILY operation transport exists, but no strict transition envelope. New total-budget profile could be implemented offline, without qualifying it. | Budget/pause transport exists; no provider proof covering old/current/proposed/delayed or never-applied effects. | Same: transport exists, native transition-bound producer absent. |
| Original-request closure | No implemented authoritative terminal/no-later-effect lookup. State readback alone insufficient. | No reviewed endpoint-specific terminality producer. | request_id is diagnostic correlation, not idempotency or terminality proof. |
| Preventive writer boundary | No qualified mechanism preventing later cap raises/replacement/new uncovered owners for full obligation window. | Same; an account spend_cap field does not constrain all administrators or automation. | Budget Manager permits changes/reset/unlimited; roles explain access, not an immutable cap fence. |

This matrix distinguishes absence of reviewed proof from proof that a provider could
never support it. Provider-owned documentation or a demonstrable enforced mechanism
is needed before specifying a qualified producer; account credentials alone are not it.

## Authoritative Evidence And Supported Offline Work

Google currently documents Search/manual-CPC total budgets with explicit campaign
start/end times. This supports an additive **unqualified** total-budget review/compiler/
HTTP profile if separately scheduled. Current [Google compiler](../../app/publication/google_compiler.py)
creates a DAILY budget; [provider contracts](../../app/publication/provider_contracts.py)
require a conservative daily reservation and still gate qualification. Implementing
total budgets would not migrate existing daily campaigns or prove a portfolio ceiling.
[Official budget API overview](https://developers.google.com/google-ads/api/docs/campaigns/budgets/overview)
was re-read for this assessment.

Meta's pinned official SDK supplies account spend_cap/amount_spent and campaign/ad-set
budget fields and edges. That supports bounded **diagnostic** whole-account reads now,
without claiming the counter's accounting epoch or cap immutability. The next package
is frozen below. [Official account SDK](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adaccount.py).

TikTok's Budget Manager help describes account caps and pausing at exhaustion, but also
editing/resetting and unlimited mode. It does not specify every effective API field.
Proceed with only independently documented campaign/ad-group inventory fields; do not
guess a Budget Manager parser, reset epoch or finality endpoint.
[Official Budget Manager documentation](https://ads.tiktok.com/resources/help/article/how-to-use-budget-manager?lang=en)
was re-read; earlier [social assessment](meta-tiktok-native-exposure-assessment.md)
records exact SDK sources and inaccessible API pages.

No provider source above proves a preventive writer mechanism. Full-account cap
candidates may require joint-envelope composition; that [proposal](google-joint-envelope-proposal.md)
remains docs-only. Do not encode an account cap as U=0/F=0 or subtract ordinary reported
cost to create a remaining cap. Basis-qualified nonreversing subtraction is not implemented.

## Frozen Next Interface: Meta Native Inventory Diagnostics

This is an additive collector, not an exposure reader. Existing Google interfaces stay unchanged.

```text
MetaNativeInventoryRequest {
  account: ExecutionAccount [meta_ads, exact account/integration/generation]
  mandate: ProviderMandateBinding
  currency, time_zone, period_start, period_end [positive, <=366 days]
}
MetaNativeInventoryContext extends OptimizationContext { request_digest }
MetaNativeInventoryHTTP(request, now) -> MetaNativeInventory {
  exact request; observation_started_at; observed_at; expires_at
  account observations: status; optional amount_spent_minor; spend_cap_minor
  campaigns <=200: id, account_id, status, optional daily/lifetime/spend caps,
                   optional start/stop and declared sharing/schedule flags
  adsets <=200: id, account_id, campaign_id, status, optional daily/lifetime/spend caps,
               optional start/end and schedule flags
  advertising_inventory_read_complete [only successful complete bounded reads]
  accounting_basis: unqualified
  cap_counter_epoch: null; pending_cap_changes_complete: false
  reporting_watermark: null; U: null; F: null; P: null
  cap_semantics: unqualified; bounded fixed reason codes
}
```

Read only fixed v26 account/campaign/ad-set endpoints using injected bounded HTTP.
Never follow provider next URLs: take only a bounded opaque after cursor and reconstruct
fixed paths. Reject loops, duplicate IDs, foreign ownership, missing parents, truncation,
malformed numeric fields, currency/timezone mismatch, expired context and generation
change. All statuses must be requested; unknown status or insufficient historical
coverage cannot imply a qualified portfolio. Optional absent fields remain null, not
zero/false. Native minor-unit counters stay explicitly labelled, not converted to an
approved monetary basis. Use exact request-bound current context before/after IO; no
DB transaction is released by this collector. Caller performs current owner/session/
mandate checks around external IO. No default/live factory, persistence or mutation.

Tests: actual MockTransport serialization and pagination, hidden later-page owner,
foreign child, omitted optional counters, explicit zero counter, unknown basis,
changed generation, expired context, next-URL origin attack, cursor cycle, overflow,
private-error sanitization; results cannot validate finite bounds. These checks close
an offline diagnostic adapter gap, not strict-cap acceptance.

## Minimal Owner Decisions And Release Gates

1. **Monetary promise:** recommend explicitly defined net billed media spend excluding
   taxes/fees only if that matches the intended product, because native billed-cap
   candidates may then be useful. Gross served or all-in cash requires additional
   enforceable evidence. This recommendation does not change existing mandates; future
   basis must be versioned and old high-water/holds cannot be reinterpreted or reduced.
2. **Restricted launch accounts:** defer an owner choice until engineering demonstrates
   an actual enforceable mechanism and eligible configurations. A dedicated account or
   promise not to edit caps is not enough. Then present precise customer exclusions,
   required controls and remaining limitations for a concrete decision.
3. **Best-effort spending:** do not infer this option. It would change the guarantee,
   disclosures, approval policy and tests. Recommendation remains strict fail-closed;
   no such relaxation is needed to finish diagnostic/source plumbing offline.

Genuine later access/live gates: approved app scopes and account eligibility, operator-
approved credentials/context, intended-environment read validation and documented
provider capability evidence; separately authorized mutation qualification/release.
Those cannot substitute for the missing code enumerated above. Next code order:
Meta diagnostics; documented TikTok inventory; current-generation diagnostic assembly
and named target discovery; then a qualified-source specification only if actual native
semantics and prevention evidence support it. Parallel accounting/customer work remains
independent. No live authority, Full run or deployment follows from this assessment.
