# Sequential Optimization With An Atomic Reservation Replacement

## Current Verified Boundary

Base: assembled `c602a1b`, including immutable consented ledger accounting account sets,
no mixed-currency held exposure, cumulative positive changes across canceled/settled
runs, and one original attempt/fence. The current same-native-owner hold rejects a
second optimization even after verified target-state readback. That is safe and stays
the default until this complete replacement protocol qualifies.

No native authoritative original-request closure or transitional exposure source is
currently implemented. Google native inventory diagnostics will remain explicitly
unqualified, with null bounds/watermark. A lower observed budget, successful-looking
current state, HTTP acknowledgement, missing row, reporting age, daily budget, or
period end is not request-finality or newly reusable spending authority.

## Bounded First Protocol

Support sequential **existing-campaign optimization only**, within the same workspace,
environment, immutable accounting period ledger/currency/account set, selected account
and connection generation, and exact native budget-owner identity. Do not transfer
creation/activation holds with provisional owner keys, alias unrelated resources,
roll exposure across periods, convert currencies, change the accounting account set,
or combine owners. Ordinary first-operation reviews remain byte-for-byte unchanged.

A new separately approved exact review names the old reservation and all associated
old runs/attempts; it displays the old and successor reservation amounts and the new
budget/pause request. It authorizes retiring only the old Inlet operation runs as part
of the transfer; this is not a provider pause or an instruction to retry any old request.
New campaign/creative/activation policy is unchanged.

## Shared Typed Ports

1. `ReplacementSnapshot`: workspace/environment/ledger/currency and original period,
   exact account/generation/native budget-owner/target-set, old reservation ID/amount/
   original evidence digest, related old run IDs, each exact original attempt/request/
   fence and latest normalized receipt ID/digest/sequence. Include current ledger spend
   high-water, action count and cumulative positive budget changes. Snapshot collection
   uses the same workspace-first/session/ledger/native-owner lock ordering as admission.
   Bound inventory sizes and deterministic ordering. An unknown/conflicting/missing
   latest original receipt, pending/emitting step, foreign lineage, or an already
   replaced/settled reservation remains ineligible.

2. `OriginalClosureProof`: exact snapshot digest/environment/account/period, server
   qualification profile/version and evidence digest, observation/expiry, and an exact
   original-attempt set with request/fence bindings. The source must independently
   establish each original request **terminal or incapable of any later provider
   effect**. `verified_target_state`/acknowledgement alone does not satisfy this. No
   source currently qualifies live requests. A contract-test source is explicitly
   labeled and cannot be promoted to live.

3. `ReplacementPortfolioProof`: server-derived complete current `ExposureEvidence`
   bound to the proposed optimization intent, before-state, same current policy and
   exact replacement snapshot/closure proof. Its other-reservation component excludes
   exactly the named held predecessor, and includes every other held workspace/
   environment reservation (including previous periods), with the existing currency
   guard. Fresh reported spend cannot fall below the period high-water. Unreported
   spend and all unchanged portfolio exposure remain counted and complete.

   **The successor owner upper bound covers the transitional state**, not merely the
   desired lower budget. It must cover the current configuration continuing indefinitely
   within the mandate horizon if the new request never takes effect, the proposed
   configuration, delayed/unknown execution timing, native carry/overdelivery and all
   residual obligations not already included in reported/unreported components. Never
   infer this envelope with `max(old, new)` or a budget ratio. The qualified source must
   prove the decomposition and no omitted/double-reclassified obligation. Missing
   native bounds/watermark/control assumptions leave it unqualified. A request closure
   proof does not by itself prove historical costs completely reported.

4. `ReplacementReader(db, binding, proposed_intent, before_state, qualification,
   snapshot, now) -> ReplacementEvidence(closure, portfolio, transition_profile,
   transition_evidence_digest)`. This is server configuration, not a customer payload.
   Default absent; no diagnostic collector is registered as an authoritative reader.
   Provider/source IO runs outside locks. The reader cannot cancel runs, release funds,
   dispatch a mutation, or create authority. Recollect and compare the complete snapshot
   after IO with a fresh clock/current authenticated session before persistence/claim.

5. `RepeatOptimizationReview` uses a new schema discriminator and wraps the unchanged
   `OptimizationPlan` plus immutable replacement snapshot/evidence. Existing v1 review,
   request and receipt digests remain unchanged. Common parser supports both review
   variants. The exact new approval covers the complete wrapper digest and plan digest;
   the request remains the one new exact operation with a fresh fence, not a replay.

## Storage And Atomic Transfer

Proposed migration adds reservation state `superseded` (distinct from terminal
`settled`) and an immutable `ProviderReservationReplacement` audit table. Preserve old
reservation amount/evidence/ledger; never rewrite them into the new bound. The audit
links old reservation, new reservation, exact successor review/run, snapshot/proof
hashes and their strict typed documents, actor/time, ledger/environment/native-owner
scope. Composite workspace foreign keys; unique predecessor and unique successor
links prohibit forks or ambiguous transfers. Replacement chains remain bounded/readable.
Existing unique held-native-owner index continues to enforce one active hold.

Within one database transaction after current policy/session/owner/account locks:

1. Lock and re-read the exact predecessor held reservation, old runs/steps/attempts and
   latest receipts; reject any snapshot or closure/qualification/portfolio change.
2. Recompute all other held reservations and compare the qualified proof; check total
   cap, per-plan cap, positive-change/aggressiveness/action/cooldown limits. Preserve
   cumulative charges across all predecessor/successor runs and policy revisions.
3. Mark the old reservation `superseded`; insert the new held reservation for the same
   native owner/ledger with the qualified transitional amount. Insert the immutable
   replacement audit and retire old operation runs with cancellation fences. Bind the
   new run to the successor hold and charge its action/positive-change accounting.
4. Commit all of that atomically: never commit an unreserved gap. If any insert/unique/
   proof check fails, the old hold remains intact. Then reacquire session/current
   authority before claiming the sole original request for the new operation.

Cancellation after transfer retains the successor hold even if the new mutation was
never emitted, because the pre-existing campaign can still spend. It **cannot use the
current local zero-attempt settlement shortcut**. Settlement must follow predecessor
lineage and require terminal original requests, complete reporting and zero residual
future exposure for the whole native owner. This is a necessary adjacent repair, not
an optional cleanup. A second replacement likewise carries the entire prior obligation
chain and requires all new original requests closed; it never releases from age.

Historical original receipt records remain append-only. Superseded runs cannot emit or
be reclaimed. A later read of an old desired state may legitimately differ after the
new operation: it is not permission to reopen/replay the old request or reclaim its
exposure. Source contradiction/invalidation before transfer blocks transfer; after a
transfer it retains the current successor hold and blocks further replacements until
qualified evidence resolves the chain. No automatic refund or zeroing is inferred.

## Required Offline Acceptance

- Actual mocked provider first optimization -> qualified source closure/current
  portfolio -> exact repeat approval -> atomic successor hold -> second exact request
  -> independent readback; all three provider adapters retain their existing scope.
- Unknown/missing/conflicting original evidence, incomplete closure, stale profile,
  missing native transition bound, stale watermark, current-state/target/native-owner/
  generation/period/currency/account-set changes and changed other holds all reject.
- Successor amount may decrease only from a qualified full transitional decomposition;
  current-state continuation remains funded when the new request is delayed/no-effect.
- Cancellation/session revocation/owner change before and after admission; context lookup
  before final guard; concurrent workers/replacement reviews -> one successor and one
  original attempt; rollback/injected failure leaves predecessor held without a gap.
- Positive/action/spend accounting survives cancellation, supersession, settlement,
  mandate revision/new consent, and repeated successor generations.
- Cancel after transfer but before attempt cannot release inherited exposure locally.
  Terminal settlement traverses the chain; any uncertain descendant retains exposure.
- Existing v1 review/request/receipt hashes remain stable; lifecycle closure retains
  current holds and chain audits; model registry and explicit lifecycle/export unions
  updated for the new audit table. Disposable migration roundtrip; no lossy downgrade
  when supersession data exists.

## Risks And Remaining Boundaries

The critical risk is treating a lower planned budget as a lower guaranteed obligation
before the provider applies it. Another is mistaking target-state observation for a
closed command, or letting local no-attempt cancellation erase inherited exposure.
These require explicit proof/chain semantics above. External writers/no CAS, reporting
latency and mutable native caps remain live qualification blockers, not fields to fill
with guessed zeroes. No new business authority is introduced: exact customer approval,
existing spending ceiling and supported action policy still govern. First deployment
of any live source/runtime remains separately gated. This proposal authorizes no live
provider read, mutation, credentials, spend, workflow dispatch, merge or deployment.

## Implemented Interface And Limits

`replacement.prepare_repeat_optimization` compiles a separately approved wrapper
around the unchanged v1 optimization plan. It requires a server-owned
`OptimizationRuntime.replacement_reader`; the default is `None`. Existing approval,
run creation, claim, actual adapter, readback and original-fence reconciliation ports
remain shared. No new customer proof-input endpoint or live runtime is enabled.

`replacement_contracts.ReplacementSnapshot` enumerates every reservation and original
attempt in the chain. `ReplacementEvidence` binds exact closure evidence and a funded
current/proposed/delayed/no-effect/residual transition. `RepeatOptimizationReview`
binds both to the unchanged plan. A reader is re-invoked before transfer; refreshed
proof must equal the exact approved document, and current DB snapshot/limits/session
must still match. Changed evidence requires a new review.

Migration 0058 adds `provider_reservation_replacements` and the `superseded`
reservation state. The table is explicitly protected in lifecycle inventory, enters
the canonical model registry through `execution_models`, and exports only the strict
`ReplacementAuditDocument` plus scoped scalar allowlist. Downgrade refuses any
replacement history or superseded reservation. Replacement preserves ledger spending,
action counts, positive-change charges and canceled historical runs. Settlement reads
all predecessor attempts even when the current successor never emitted.

The bounded chain supports at most 32 reservations, 128 associated runs and 256
original attempts. Exceeding these bounds fails closed; no history truncation or
automatic release occurs. Cross-period/currency/owner/generation transfers and
creation/activation reservation aliases are unsupported. Existing over-cap/unknown
portfolio conditions still block mutations including pause; this adds no emergency
containment authority.

No native source currently satisfies original-request finality and the full
transitional bound for the supported providers. The test source explicitly uses
`contract_scenario`, rejected for live evidence. A typed proof object is a server
interface, not itself a real native guarantee. Joint-envelope arithmetic, external
writer prevention, personal DSA persistence/erasure, and customer repeat-intent UI
are separate packages. Future personal declaration support needs an admission-time
nonpersonal closure binding before erasure can preserve held obligations safely.

Independent review found an emission gap during implementation: a contradictory
ancestor receipt appended after successor claim was initially ignored. The controlled
regression failed on SQLite and PostgreSQL (successor incorrectly emitted). Final
claim validation now revalidates the immutable chain and compares every latest
ancestor receipt with the exact approved snapshot, both before preflight and after
final context lookup. Any sequence/content change fails closed and retains exposure.
Session, policy and proof time are checked again after those ancestor reads before
the emitting commit. No prior closure assertion silently overrides later evidence.
