# Q08 Owned Empty Account Preparation — Proposal

Design only, inspected at `dce7790`. No implementation, test execution or provider
calls. This proposes a connected, owned Meta account with an observed empty catalog;
it does not extend planning to an unconnected brand. Default V3 is unchanged.

## Actual Source Baseline And Expected Gap

`selected_composer.py` already emits an `AccountTarget` investigation when no
included campaign exists. It preserves the zero ceiling, produces no native budget
change or forecast, and warns against replacing absent events with zero.
`creative_composition.py` instead defers creative work whenever no included campaign
exists. `CreativeProposalV1.coherent` requires campaign scope even though the shared
`ManualAction` and `CreativeBrief` types already permit account scope. Thus an owned
empty-account V5 API journey is expected to retain measurement prerequisites but
lack the requested product/image preparation brief. This is source inspection,
not a reproduced API result or a finding that history contains zero conversions.

The distinction matters: all campaigns excluded, catalog unavailable, supported
query returning no campaigns, and a truly empty entire provider account are not
interchangeable. Meta inventory currently qualifies only its declared query scope.
No new output may claim there are no campaigns outside that scope.

## Smallest Actual Fixture First

New isolated `tests/creative_q08_fixture.py` and API test module; no shared Q05/Q07
fixture edits. Reuse the actual social Common Basis identity, Shopify baseline,
confirmed goal and owned image upload. Before creating any plan, create/confirm a
new legitimate goal revision with budget zero through the public goal API, retaining
the same metric, windows, target and original owner. Use its actual returned
revision/confirmation in the new request. Never mutate an immutable revision or
fabricate a zero-budget saved input.

Inject a local read-only Meta HTTP responder whose account metadata is exact and
whose campaign/adset query responses are complete empty arrays (no next cursor).
It must also handle the actual named-metadata collection request with empty arrays.
Retain actual owner/vault/account context, source generation and native catalog
acquisition; do not seed a CatalogEvidence, plan, proof or synthetic campaign.
No DailyMetric or selected-event capture is seeded. Request September primary and
August comparison, one owned PNG, declared mug/name/price/restrictions, one creative
slot, and no exclusion/fixed/scenario allocation. This narrows "empty advertising
history" to unavailable imported performance plus empty declared native query,
not a guarantee that the provider has never served ads.

First run the actual API baseline under its own approved slot and retain document,
export, hashes and exact source receipts. Assert observed catalog entities empty,
selected performance unavailable (never selected count zero), zero paid allocation,
and existing investigation plus creative deferral. If actual behavior differs,
stop and reconcile the interface before production edits.

## Proposed Additive Output Contract

Use the existing `CreativeProposalV1` with one bounded discriminator:

- `target_basis: Literal["existing_campaign", "observed_empty_account"]`, default
  `existing_campaign`, omitted from serialization when default to preserve existing
  V5 campaign documents/digests and all legacy outputs.
- Existing campaign validation remains exact. The new value requires both action
  and brief targets to be the same `AccountTarget`; no provider reference, invented
  campaign name/ID, proposed fields, native budget or execution authority.
- `production` remains the existing image-creative proposal with owned byte witness,
  exact source-image selections, `production_required`, and visual/rights assessment
  unclaimed. One proposal consumes one global production slot.
- Account-scope permission is not established by this discriminator alone. The pure
  composer/document boundary must bind the exact supplied owned catalog reference,
  its complete entities array and its existing declared-scope coverage. Require an
  actually empty entities array, not merely zero included campaigns after exclusions
  or orphan children. Missing/unavailable catalogs and unsupported providers defer.
- First implementation supports Meta image preparation only. Google unsupported
  creative policy and TikTok's distinct video/storyboard policy remain unchanged.
- Initially require exact zero ceiling, typed product, at least one owned image,
  explicit positive creative capacity, and no unresolved global constraints.
  Do not imply the ceiling pays for creative production or guarantees no other costs.

The account action is `creative_review`, manually preparatory, with its catalog,
customer, policy and creative-basis references. Deterministic key remains
`creative:account_<owned account id>`; brief links exactly to it. The existing
measurement investigation remains a separate prerequisite; the creative action
names it in `prerequisites`. No publishing/activation/campaign-creation instruction.

Concrete steps: verify the declared product/offer and rights; inspect the witnessed
image without claiming it depicts the product; draft one factual image concept
using only supplied facts and restrictions; verify the destination manually; list
the event/window/attribution questions requiring supported evidence; retain the
concept for review without buying distribution. A learning task asks the customer
to record unanswered questions and later evidence, not to infer CPA, conversion
rate or sales effects from absent history. No health/testimonial/discount invention.

## Exact Consumers And Dependency Order

1. Review this contract, then fixture/API baseline only.
2. Pure contract/composer changes in `creative_production_contracts.py` and
   `creative_composition.py`; pass exact existing measurement prerequisite key from
   `selected_composer.py` rather than synthesize a separate action graph.
3. Inspect/add document cross-validation in `documents.py` as required so a copied
   proposal cannot switch to account scope without matching retained catalog
   evidence and zero-ceiling context. A metadata-only reference cannot prove the
   entities array empty: reuse retained composition evidence validation at save,
   and persist an explicit exact catalog commitment in the new proposal if the
   immutable document otherwise lacks a checkable empty-catalog witness. Freeze
   that exact commitment shape before coding; do not assert a reference alone proves
   emptiness. No new SQL schema is expected, but this is a remaining design detail.
4. Pure tests: existing campaign bytes/digests unchanged; copied discriminator and
   target tampering rejected; nonempty/excluded/orphan/unavailable scope cannot
   trigger account preparation; capacity zero/missing and absent image defer.
5. Actual V5 API on SQLite/PostgreSQL: zero confirmed goal -> generation -> current
   read/export/replay, exact account identity/proof/image, empty observed query,
   explicit history gaps, zero scenario allocation/reserve/ceiling, no forecast,
   one useful preparation brief, no native calls after generation, zero financial
   or execution rows. Preserve baseline and new artifacts separately.

No owner decision is needed for this bounded connected-account preparation path.
Supporting a brand with no connected account is a separate scope decision and must
not be smuggled in through a fixture. Human usefulness assessment and live provider
qualification remain separate gates. This proposal does not claim full Q08 closure.
