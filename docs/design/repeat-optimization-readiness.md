# Repeat Optimization Closure And Readiness

Assessment baseline: assembled `1c82e03`. This is an offline code/readiness assessment,
not a live provider qualification. The customer-facing product remains Inlet.

## Current Capability And Missing Implementation

| Area | Implemented and verifiable offline | Remaining work |
| --- | --- | --- |
| Customer flow | `customer_optimization` resolves owned target catalogs, confirmed goals, separate versioned mandates/consent, initial/repeat exact reviews, approval and run creation. `customer_execution.advance` calls the actual durable optimization adapter path; reconciliation and cancellation are available. Browser/API tests exist. | Production `get_customer_optimization_runtime()` returns `None`; runtime assembly and qualified server sources are missing. This is a manual exact-review/step flow, not automatic optimization. |
| Provider operation | Google Search/manual CPC independent-budget and bounded Meta/TikTok budget/pause transports use exact current state/topology, one mutation, readback and original-fence reconciliation. | Unsupported providers/topologies stay ineligible. Native daily/lifetime budget fields alone do not qualify total spending exposure. |
| Repeat transfer | Exact wrapper preserves v1 plan/request hashes. Server `ReplacementReader` must bind complete predecessor receipts, original-request closure, current portfolio and a transitional bound. Atomic superseded-to-held transfer preserves accounting. | No production original-terminal/transition producer exists. The optional reader is `None`; injecting a typed object is not qualifying its native semantics. |
| Accounting | One immutable environment/period ledger, locked accounting account set, mixed-currency hold rejection, all workspace/environment held reservations including older periods, spend high-water, cumulative action and positive-change charges, cooldown and per-change aggressiveness checks. | No FX, cross-period transfer, or joint-envelope mode. Native complete facts and bounded reporting/exposure semantics are missing. This is not solved merely by supplying credentials. |
| Uncertainty | Unknown original requests retain original attempt/fence and hold; no blind replay. Latest contradictory ancestor receipt blocks successor emission after final context lookup. | Native finality/late-effect-impossibility evidence remains missing. Polling old target state, timeout, request ID, pause, age or period end does not establish it. |
| Settlement | Full predecessor traversal includes original effects even if a successor never emitted. Complete terminal/reporting/zero-future evidence is required; no-attempt inherited refund is prohibited. | `get_settlement_runtime()` is `None`; no qualified terminal/reporting producer or scheduled settlement operator exists. |
| Recurring optimization | Imports/analysis/billing worker orchestration exists in `jobs/customer_runtime.py`. Financial limits survive repeated and canceled/settled attempts. | No optimization decision producer, automatic target/action selection policy, durable scheduling queue, fairness/backoff dispatcher, or mandate-derived automated execution provenance. These are missing code, not provider-access-only gates. |
| Learning | Owned receipt projections retain exact environment, original request/fence, mandate/goal/account/generation lineage; verified target state does not invent delivery time. | Mature learning is a separate package. Candidate selection must not treat illustrative/immature/descriptive results as causal qualification or fabricate effective timestamps. |

Actual native Google inventory is diagnostic-only (`collectors/google_native_inventory.py`):
watermark/U/F/P remain null and cap semantics unqualified. Native source ownership stays
with the provider-source workstream. Selected-target Meta/TikTok topology transports
are not whole-account native exposure/finality producers. No approved joint-envelope
calculation or preventive external-writer mechanism is supplied by this package.

## Concrete Bounded Defect Found

The chain reader supports 32 reservations, and a replacement snapshot accepts 32
ancestors. Previously a 32-reservation head could prepare and transfer a 33rd successor,
which the same reader could not later settle. A controlled test built 32 real database
reservations from one actual mocked Google request and 31 canceled unattempted
successors; the expected rejection failed on the baseline.

The repair reserves one slot before preparation, approval and transfer. At capacity,
forward replacement fails closed; historical reading, original-attempt reconciliation
and terminal settlement remain available. No bound is widened, history truncated,
reservation refunded or ledger reset. This also protects previously persisted but
unadmitted reviews at the boundary.

## Recurring Native Effects And Expiry

Each admitted operation is one original request, but its configuration can continue
influencing provider spend. A repeated scheduler tick is not an accounting period
reset. Native delivery does not stop merely because a mandate expires, a session
logs out, a run is canceled or the last budget is lower. Expiry stops new mutation
authority; it does not authorize an unapproved post-period pause/restoration, release
holds, erase positive-change charges or fabricate a terminal effective time. Future
qualified source profiles must bound continuing/delayed effects and reporting residuals
explicitly. Unsupported post-period/control semantics remain ineligible; retained
older-period reservations still count against later compatible-currency admission.
No currently shipped native source establishes these guarantees.

## Proposed Shared Automation Interfaces — Not Implemented Or Enabled

The user's product scope allows existing-campaign optimization within an approved
spending mandate. Automatic operation therefore must not be represented forever as
manual per-action clicks, nor may a worker fabricate human review approval records.
The following separate ports need agreement before dependent scheduler work:

1. **Server candidate producer.** A versioned `OptimizationCandidate` binds workspace,
   environment, current mandate/consent revision, confirmed goal revision, exact owned
   account/generation, native budget owner and complete allowed target set, one existing
   typed budget/pause action, bounded observation time, decision-policy version and
   server-held evidence references. It carries no credential or customer-supplied
   exposure/closure assertion. A candidate is a suggestion, not dispatch authority.
   `CandidateProducer` returns a bounded candidate list or audited no-action reasons;
   current qualification and plan compilation must still reread server facts.
2. **Mandate-derived automated authorization.** A distinct persisted provenance record
   binds the compiled plan digest, approved mandate revision/consent, allowed action
   and target set, decision-policy version and worker delegation revision. It says
   `automated_existing_campaign`, never `customer_exact_review`. It cannot authorize
   new campaigns, creative, activation/resume, broader accounts or an increased overall
   spending limit. Manual exact-review paths retain their original session guard.
3. **Durable work item.** A server-created item contains only workspace/environment,
   owned run/authorization IDs, original attempt ID when reconciling, purpose and
   bounded scheduling/retry metadata. Purposes are distinct: prepare a candidate,
   admit an authorized original operation, reconcile that same original, or seek
   qualified settlement. Runtime, provider requests and proof objects are resolved
   server-side, never embedded by a browser or replayed as mutation retries.
4. **Worker authority resolver.** Before every blocking source/context operation and
   immediately before durable emission, reread workspace state, master control,
   current entitlement, approved mandate/delegation, consenting owner's current
   eligibility, target/account/generation, currency/account-set ledger and original
   approval provenance. Reconciliation may inspect an original after forward authority
   is revoked, but cannot turn that inspection into new permission or a refund.
5. **Dispatcher.** Bounded per-workspace fairness and failure isolation; durable due
   time/backoff and idempotent work deduplication; current ownership checked on every
   fetch and after waits. Unknown attempts always select reconciliation of the same
   fence. Stale candidates are recompiled, never silently reapproved. Reservation
   admission/replacement stays in the existing workspace-first transactions. All
   factories default absent and no scheduler branch activates without qualified
   producer/authority assembly.

These ports should reuse existing typed action/current-state/receipt contracts and
one ledger; they must not introduce a second reservation pool or infer a transition
bound as `max(old,new)`, U=0, F=0, budget ratios or absent readback. The exact automatic
policy-to-plan authorization is missing implementation, not an access checkbox.

## Minimal Security Decision Needed Before Worker Implementation

Interactive mutations currently bind the original revocable customer session. A
long-lived worker cannot borrow that session indefinitely or silently replace its
validator with an owner-ID check. Recommended design: separately version an explicit,
revocable `automated_existing_campaign` delegation within spending-mandate consent;
show that it continues after logout until paused/revoked/expired. Only a server worker
principal may resolve this delegation, and every operation still revalidates the
current owner, consent, scope, controls and ledger. Logout continues to invalidate
interactive requests; pause/revoke/closure invalidate future worker dispatch. Pending
unknown operations retain exposure and reconciliation lineage.

This needs an explicit security/product contract decision about logout versus
long-lived delegation semantics and the policy version allowed to select actions.
No such delegation or fabricated human approval is implemented here. The alternative
is a session-bound scheduler that stops when the original session expires; that is
safer than silently weakening authentication but does not deliver durable autonomous
optimization. Recommend the explicit bounded delegation, with default-disabled runtime
and offline revocation/ownership/expiry/concurrency tests before any live qualification.

## Next Packages And Acceptance

- Finish and independently review this capacity repair and current customer/core
  regression checks; preserve migration/restore history and exact source blockers.
- Freeze the candidate/automated-provenance/delegation contract above with the owner
  of customer authorization before shared schema or dependent scheduler code.
- Implement deterministic no-network candidate policy and durable worker queue/fairness
  using actual adapters with mocked sources. Demonstrate approved cap/target limits,
  fresh source and session/delegation boundaries, unknown reconciliation, recurring
  effects and cumulative limits across multiple worker ticks. Do not auto-approve
  new campaigns/creative or claim a learning policy from immature data.
- Native producers separately need qualified complete accounting facts, original
  request terminality and full transitional exposure guarantees. Diagnostic inventory
  may explain missing evidence but cannot be wired as a qualifying source.
- Production assembly, credential/access provisioning, controlled provider qualification,
  live authorization and release remain separate gates. Completing code and tests does
  not establish native cap semantics or make Inlet purchasable/live by itself.
