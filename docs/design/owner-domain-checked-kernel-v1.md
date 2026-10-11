# Owner Domain Checked Kernels — Intrinsic Validation Proposal

Status: source-only design, no implementation/execution authority. Inspected owner
contracts/review contracts/common digest and review construction at `6df589b`.
No new probe, SQL, provider or import execution. This is a coherent model-specific
validation design, not another wrapper deletion or a claim of sufficient timing margin.

## Source-Proven Amplification

`Frozen` has `revalidate_instances='always'`; its public digest validates the model and
then serializes it. Owner review and owner proof have wrap serializers that validate
again before invoking their handlers. Consequently a digest or equality serialization
can perform validation even when its immediate caller has just validated the model.
The full PlanVersion owner validator invokes these public methods repeatedly. The
parent reports multiple PlanVersion parses per save, but this document does not infer
a measured multiplier or add overlapping timings.

Specific lexical duplication:

- `resolve_google_daily_budget_intent` validates its witness, then calls witness.digest
  (validates it again) and owner_facts_digest (validates it again before deriving facts).
- `GoogleBudgetOwnerReviewV1.exact` runs after Pydantic has validated its nested witness,
  then calls resolve_google_daily_budget_intent (revalidation above), then
  owner_review_action_key (another witness validation).
- `GoogleBudgetOwnerReviewProofV1.complete` runs after its review children have passed
  their full validators, then constructs its byte-bound payload using each child's
  model_dump. Each child wrap serializer validates that complete child again, including
  witness resolution and hashes, solely to obtain size-check bytes.
- Public proof serialization first validates the proof, whose complete validator does
  the child serialization above; its handler subsequently invokes the child wrap
  serializers again. Public Frozen.digest first validates before calling this public
  serialization. These entry protections cannot simply be deleted globally.

`derive_google_daily_budget_owner` also calls `_parts` then constructs a witness whose
validator calls `_parts` again. This proposal does NOT bypass that constructor or weaken
its invariants. No `model_construct`, Pydantic context skip flag or cached derivation.

## Proposed Bounded First Coherent Package

Own `google_budget_owner_contracts.py`, `google_budget_owner_review_contracts.py`,
focused pure tests and ledger only. Do not change Frozen, PlanVersion, source readers,
input admission, repository, service, current/history dispatch or API. Every full
PlanVersion call across SQL remains. No token/epoch/cache survives a function call.

Private checked functions, callable only from explicitly enumerated validated sites:

    _owner_witness_digest_checked(witness: GoogleDailyBudgetOwnerWitnessV1) -> str
    _owner_facts_digest_checked(witness: GoogleDailyBudgetOwnerWitnessV1) -> str
    _resolve_owner_intent_checked(intent: GoogleDailyBudgetIntentV1,
        witness: GoogleDailyBudgetOwnerWitnessV1) -> ResolvedGoogleDailyBudgetIntentV1
    _owner_review_action_key_checked(witness: GoogleDailyBudgetOwnerWitnessV1) -> str
    _owner_review_payload_checked(review: GoogleBudgetOwnerReviewV1) -> dict[str, Any]

These are implementation-local pure derivations, not exported proof objects or flags.
They do not validate arbitrary callers and cannot be accepted by an external API.
Existing public functions continue full strict revalidation then call the private kernel.
No external caller is converted to a checked kernel merely because it claims a prior
check. The intended internal callers are exactly:

| Caller | Validation already completed within this lexical invocation | Permitted substitution |
| --- | --- | --- |
| Witness.digest | `type(self).model_validate(self)` | Compute unchanged domain hash from the checked witness once. |
| owner_facts_digest | `GoogleDailyBudgetOwnerWitnessV1.model_validate(witness)` | Existing `_parts` + identical facts payload/hash, without another public wrapper. |
| resolve_google_daily_budget_intent | Exact request and witness model_validate | Call `_resolve_owner_intent_checked`; it uses checked witness/facts hash functions and unchanged account/currency/observation/facts comparisons; construct resolved DTO normally. |
| Review.exact | Pydantic nested request/resolved-intent and witness validation plus `_originals` before-validator | Validate reconstructed request as today, then checked resolver and checked action-key function. Keep full resolved serialized equality and all action-key comparisons. |
| Proof.complete | Pydantic nested reviews completed all strict validators | Size payload uses `_owner_review_payload_checked` rather than child wrap serialization. Keep unique action/full-owner checks, complete account catalog equality and byte bound. |

Public `owner_review_action_key` still validates the witness before its checked function.
Public Review/Proof wrap serializers remain unchanged in this first package: externally
serializing an unsafe copied graph must still revalidate. Frozen.digest remains unchanged
for every class, including these models. This deliberately leaves some public serializer
revalidation; no claim this package eliminates the entire amplification.

## Exact Invariants And Payload

Witness validation remains responsible for original strict primitives/aware times;
full catalog source/account/generation/privacy and UTC window joins; complete recognized
campaign coverage; native/metadata owner membership/status agreement; shared DAILY,
ENABLED/STANDARD/micros profile and no total amount; all represented rows before REMOVED
filter; ordered active affected set and representative; exact current amount/currency/
reference count; no authority flags and witness byte bound.

Checked witness digest preserves `fingerprint(schema_version, witness JSON tree)` and
all fields. Facts preserves `inlet.google-daily-budget-owner-facts.v1` domain/payload,
full source/account/native currency/timezone/settings/represented rows/affected keys,
removed policy and both coverage arrays; no observation time added to stable facts.
It still computes `_parts` for these facts; no stored derivation is trusted.

Checked review payload is an explicit JSON-mode tree with exactly: schema_version,
inherited advertising_writes_enabled/spending_authority, action_key, full resolved
intent, full witness, disposition, period_spending_compatibility,
provider_edit_validity, application. Nested intent/witness public serialization remains
as today (witness has no checked wrap serializer); do not substitute reduced hashes or
omit catalogs. No model serialization option is changed: this private payload is used
ONLY by the existing proof size check, which currently requests default JSON mode.
Do not replace public wrap handlers with this payload; include/exclude/by-alias/roundtrip
semantics are deliberately outside scope.

Proof size payload retains schema/no-authority fields/input_digest and exact ordered
review payloads; same json.dumps options, UTF-8 and MAX_DOCUMENT_BYTES boundary.
Assert explicit field inventory equals actual model_fields so a new field cannot be
silently omitted. Checked helpers cannot process an unsafe copied nested child merely
because its outer type matches; the only allowed nested calls are model after-validators
whose field parsing has completed with revalidate_instances='always'. Subclass/custom
validator behavior must be examined before source approval; use concrete supported
classes or preserve original public fallback where the guarantee does not hold.

## Qualification Before Acceptance

- Exact prechange witness/facts/action-key/review/proof JSON and digest bytes for complete,
  empty, removed-member and multiple-owner cases; all original goldens unchanged.
- Invalid model_copy nested bool/bytes/numeric time, source revision, member/settings,
  changed resolved intent, mismatched action key, extra fields and oversized payload
  rejected by every PUBLIC validate/digest/serialize/resolve entry as before.
- Public serializers' include/exclude options and unsafe-copy refusal unchanged; proof
  size at boundaries uses identical bytes. Private field-inventory assertion prevents
  accidental schema drift.
- Count `_parts`/full witness validation calls on real validators with spies to prove
  reduced redundant work within one pure call, without replacing validation with stubs.
  A separate invocation must perform fresh validation again; mutate between calls to
  prove no cache or reusable authority. No numerical performance threshold invented.
- Existing pure source/input/history/review tests, V1–V5 byte goldens and bounded actual
  V6 save/expiry checks selected after source review. Five-second/real-six-second refusal
  and atomic rollback remain; no full retry loop follows from this proposal.

## Recommendation And Limits

This offers a source-justified model-specific approach without moving work across the
identity refresh or any SQL boundary. It attacks repeated strict graph validation caused
by internal public-helper recursion, rather than trusting an arbitrary prepared graph.
It is technically reviewable as routine offline engineering. Actual savings and reliable
normal-flow qualification remain unknown; no incident closure is implied.

If internal checked preconditions cannot be proved for a callsite, retain the public
helper there. Do not weaken primitives/size checks to hit timing. A longer/renewed fact
or dropped fresh pass remains an owner authority-architecture choice, not an implicit
fallback. No such choice is requested while this concrete domain-level design is under
review, and no new implementation is authorized by this document alone.
