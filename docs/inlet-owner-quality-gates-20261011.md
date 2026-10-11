# Six Human Quality Gates — Owner Decision Sheet

All six remain open. These are the unchanged human usefulness criteria in the
[frozen quality plan](design/comprehensive-planning-quality-cases.md), not six
automated test results. Technical policy versions V4/V5 do not denote product
completion. Inlet is not yet a live-qualified, purchasable release.

**Recommended owner action now that actual review artifacts are available:** nominate an
advertising/ecommerce expert (the owner may review). Record a separate pass/fail,
reason and required correction for each criterion and Google-only, Meta-only,
TikTok-only and three-platform case. Keep every criterion; do not average away a
failure. Engineering and remaining acceptance work continue while this is pending.

| Gate | Decision to record | Recommended pass rule |
| --- | --- | --- |
| Scope, facts and semantics | Are targets, metrics and limitations correct? | No wrong identity, inferred event, hidden data gap or unsupported attribution. |
| Campaign-specific usefulness | Can the customer act or knowingly defer? | Locatable target, concrete steps and prerequisites, and a defensible maintain option. |
| Budget and alternatives | Is the plan coherent within the approved ceiling? | No double counting, invented native setting or forecast, or increased ceiling. |
| Rationale and uncertainty | Is each recommendation supported and traceable? | Source/date/event linkage, explicit assumptions and honest uncertainty. |
| Creative feasibility | Can the customer produce it with the stated facts and capacity? | No invented assets or claims; production dependencies and capacity limits are explicit. |
| Honest lifecycle labels | Are decisions, customer reports, observations and outcomes distinct? | No provider verification or causal-lift claim inferred from a report or matching fields. |

The new [Common Basis artifact manifest](/workspace/inlet-evidence/20261011/creative-common-basis/artifacts/manifest.json)
contains 20 genuine synthetic API document/export artifacts. Root independently
verified every byte hash and strict document digest. They cover Google positive,
zero and missing selected conversions, Meta-only and TikTok-only flows. They are
review material, not expert verdicts. The bounded private portal browser result and the new four-file three-platform
artifact are linked from the [review packet](inlet-creative-review-packet-20261011.md).
They provide mechanical evidence; Q01–Q16 stay partial.

Separate operational release decisions also remain: authorized live identity,
payment, storage and provider setup; settled commercial terms; representative
customer pilots; hosted-check authority/budget; reviewed merge and deployment.
This sheet does not request those approvals prematurely or authorize credentials,
live calls, purchases, advertising writes, public claims or default-policy changes.
The qualified `9d7aa2e` evidence is preserved unchanged and does not qualify all
subsequent commits automatically.

## Decisions And Work That Can Proceed Independently

Recommended decision now: appoint one advertising/ecommerce reviewer and use the
existing provider-specific [review packet](inlet-creative-review-packet-20261011.md)
for provisional written feedback. Do not approve release from this incomplete
packet. Each of the following needs its own pass/fail and concrete correction:

| Human decision | Recommended standard | Engineering that does not need to wait |
| --- | --- | --- |
| Are the facts and metrics right? | Accept only if the chosen conversion event, dates, currency and missing-data limits are clear and correct. | Verify exact numeric/source bindings and extend the now-generated combined-platform evidence. |
| Is the advice useful for this campaign? | Accept only if a customer can locate the campaign and follow specific steps, or understand why to leave it alone. | Improve traceable targets and surface prerequisites; collect reviewer corrections. |
| Does the budget make sense? | Accept only if each alternative separately fits the approved ceiling and its tradeoffs are understandable. | Verify exact allocation/reserve arithmetic and keep alternatives separate. |
| Is the reasoning honest? | Accept only if evidence, assumptions and uncertainty are distinguishable and no unsupported performance promise appears. | Check evidence links, timestamps and uncertainty labels. |
| Can the creative actually be produced? | Accept only if the plan uses supplied facts and available capacity, with missing assets/permissions clearly identified. | Test input preservation, asset ownership and production-required labels; do not infer usage rights or visual quality. |
| Are progress labels truthful? | Accept only if customer reports, observed provider data and proven outcomes remain distinct. | Test history/currentness and manual-action labels; prevent unverified success claims. |

The owner or nominated expert supplies the judgments; automated tests cannot do so.
The PostgreSQL conflict investigation, further evidence-backed performance work, additional review
artifacts and acceptance fixes can all proceed independently. Provisioning live
services, selecting commercial terms, pilots, merge and deployment are separate
future owner decisions. No credentials, spending or advertising writes are needed
for the current review and engineering work.
