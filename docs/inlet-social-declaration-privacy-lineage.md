# Social Declaration Privacy And Original Attempt Closure

Design inventory against assembled a95ca7c (2026-10-06). No runtime or schema
change. Revision0059/down0057 remains reserved for social configuration review;
0058 belongs to replacement audit. This document refines the companion review
design: personal payload erasure must not delete an economic obligation.

## Actual Copy Graph

| Storage / type | Declaration copy | Current dependency |
| --- | --- | --- |
| Proposed social configuration review payload | Explicit Meta beneficiary/payor | Customer confirmation and exact producer input |
| `ProviderExecutionReview.document`, `CreationExecutionReview` | `plan.review.configuration.dsa_*`; repeated in `plan.steps[*].operation.configuration.dsa_*` for campaign/adset/creative operations | Canonical recompilation, review hash, qualification and dispatch admission |
| `ProviderExecutionAttempt.request`, `SocialBoundRequest` | `step.operation.configuration.dsa_*` for those operations | Original request digest, fence validation, provider reconcile and receipt projection |
| `ProviderExecutionReview.document`, `ActivationExecutionReview` | `creation_plan` copies the original plan; `plan.targets[*].original_request` copies original creation requests | Parent graph proof and exact activation review |
| Activation `ProviderExecutionAttempt.request` | `target.original_request.step.operation.configuration.dsa_*` | Activation request hash and original target verification |
| `ProviderExecutionResponse.response` | No names: typed request digest/resource/outcome only | Request-scoped response and original-attempt reconciliation |
| `ProviderExecutionReceipt.receipt` | No names: scope/plan/request/fence/resource/readback digest/outcome/time | Immutable ordered receipts and supersession |
| `ProviderExecutionReceipt.projection` | No names: normalized scope/goal/mandate/source/attempt/digests/environment/outcome/time | Owned outcome read and settlement snapshot |
| `ProviderExposureReservation.evidence` / `settled_evidence` | No DSA values in typed exposure or normalized receipt snapshot | Amount, currency, account set, original period, held/settled state |
| `ProviderReviewRecord.review` / `.plan` | Potential copies if a future social qualification producer uses this generic store; current customer Google path only | Must classify before adding social writer; cannot assume generic JSON is harmless |
| Legacy `PublicationPlanRecord` / steps / receipts | Current service validates the separate simulation `PublishPlan`/`BoundRequest`, not this social plan type | No demonstrated DSA writer; keep disallowed rather than inventing a propagation edge |

All descendants of a creation review must be found by owned relational run/parent,
review and attempt links, not a substring search for names in arbitrary JSON.
Names may repeat across typed operations; clearing only `plan.review` is inadequate.
No new actor-email/name copies should be introduced by confirmation auditing.

The receipt itself is NOT a plaintext declaration snapshot. Do not erase raw or
normalized receipts solely because they refer to an erased declaration. Preserve
latest-sequence semantics, including unknown/conflict superseding earlier success.

## Demonstrated Finality Conflict

`coordinator.read_owned_outcome_receipt` enters `evidence_lock`, reconstructs the
entire original execution review and request, and recomputes their exact digests.
`settlement.locked_snapshot` invokes that reader for every original attempt. The
activation reader similarly parses `ActivationExecutionReview` and the original
request nested in its target. Therefore replacing names with null or dropping the
review/request breaks the current settlement path even though names are not inputs
to exposure arithmetic. Keeping stale hash columns and calling the redacted JSON
canonical would be false evidence. Deleting a reservation or marking unknown as
no-effect to bypass the failure would release potentially spent money unsafely.

A privacy-safe implementation needs a distinct historical closure representation,
not a permissive exception in the current canonical-plan reader.

## Proposed Closure Binding

Scheduler-owned strict `OriginalAttemptClosureBindingV1`, captured server-side in
the same transaction as original durable admission, before provider IO:

- owned workspace, environment, account/integration/generation;
- original run/step/attempt IDs, purpose, operation kind, fence and dispatched_at;
- original review/plan/request digest commitments, never recomputed from a tombstone;
- original consent/mandate revision, goal/source revision, ledger/reservation ID;
- budget owner, currency/period and exact exposure-evidence digest;
- typed scoped resource references needed to identify original request closure;
- explicit `forward_authority = false` for the closure-only projection;
- no creative text, DSA values, contact identities, full operation body or secrets.

This is not an assertion that scoped IDs or hash commitments are anonymous. It is
a minimized technical lineage record under the existing financial obligation/audit
policy. No new free-standing hash of beneficiary/payor or declaration-only payload
is retained. If that policy does not permit a necessary field, owner classification
must resolve it before the DSA path stores personal values; inventing retention is
not acceptable.

Commitment integrity is established at original admission and again before erasure
while canonical originals still exist. Do not derive a trusted binding from a
customer-supplied projection or accept a mutable JSON digest as sufficient. Existing
pre-binding attempts can migrate only through verified owned canonical originals;
otherwise retain the financial hold and expose a specific historical-lineage gap.
Do not call that gap successful settlement or complete privacy qualification.

## Atomic Erasure And Read Behavior

With canonical workspace-first locking and the final-emission privacy fence:

1. Lock the owned declaration and all dependent reviews/runs/attempts; resolve and
   verify the closure bindings while originals exist. Discover descendants in a
   bounded, resumable privacy process if necessary, denying forward use immediately.
2. Revoke configuration forward authority and cancel future run steps. Never replay,
   re-fence or delete an already admitted original attempt. Preserve held reservation
   amounts, original account set, currency, ledger and spent high-water values.
3. Replace personal-bearing documents with a separately typed erased envelope,
   containing only owned record ID, payload state, privacy revision/time, and the
   closure binding identifier. Clear declaration payload and its standalone digest.
   Preserve original technical commitments in the closure binding only; do not label
   the erased envelope as an executable plan with the old digest.
4. Preserve append-only minimal receipts and responses, sequence and supersession.
   A late provider result can append to its original attempt using the closure
   binding; it cannot restore a plan, resume dispatch or infer no-effect.
5. Bump workspace export privacy revision atomically. Strict export emits erased
   envelopes/minimal closure facts and no erased names or canonical JSON copies.
   Existing archive delivery fences abort stale in-flight export.

New forward preparation, approval, activation, optimization and final emission
must reject erased configuration. Historical reads are explicitly erased/unavailable
for original configuration. Receipt read revalidates owned closure binding and
latest immutable receipt chain without reconstructing deleted private bytes.

Settlement still requires authoritative terminal original-request closure and
complete reporting over the original scope. It may use the closure-only snapshot;
absence of personal names is not proof of closure. Exact configuration readback
reconciliation may become unavailable after erasure if provider evidence requires
those names; that retains the hold and reports the limitation. A provider-specific
minimal terminal-closure reader is a separate frozen interface, not guessed here.
A request already emitted before erasure may still finish externally; no recall or
external deletion claim is made.

## Implementation Split And Coordination

No general privacy-safe receipt/settlement reader exists yet for these tombstones.
This is a shared engineering dependency, not an owner request to retain names
indefinitely. Scheduler must own/agree the admission binding and closure read port;
portal/lifecycle owner must agree typed erasure propagation and export schema.
Personal DSA capture remains unavailable until this path and all copies are covered.

Continue0059 with exact TikTok cover review and Meta explicitly confirmed
no-special-category profiles whose VERIFIED requirements do not require DSA names.
Reject supplied beneficiary/payor fields in that incremental API rather than saving
and ignoring them. DSA-required or unverified-requirement profiles return an honest
blocked reason. No default assertion, runtime enablement or special-category
expansion. Independent media/declaration review still binds exact option/profile,
source revision, generation and current confirmer ownership/session.

Before a later personal-data path: test erasure before dispatch, during admitted IO,
after unknown, after verified receipt, and after activation; preserve reservations,
late-receipt sequencing, supersession and authoritative settlement. Both databases,
strict exports and a cross-workspace denial are required. A held/unknown attempt
must remain economically held after all private declaration bytes are gone.
