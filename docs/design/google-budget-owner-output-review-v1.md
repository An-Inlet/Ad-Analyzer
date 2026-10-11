# Q06 owner hypotheses: a bounded investigation output

Design only, based on `cd65fdd`. All existing generation refusals remain in force
until this interface, its implementation, and the genuine configured path are
reviewed. No provider research, calls, execution, policy registration, or default
switch is part of this proposal.

## Useful result and its limit

A saved daily hypothesis can be shown beside its original observed shared owner as
an **investigation**, with all affected campaigns and its independently reconciled
customer scenario. This is useful even when economic compatibility is unavailable.
It is not a suggested native setting, a safe amount, a spending ceiling conversion,
a pause instruction, or permission to apply anything. Requested daily amount less
than or equal to observed daily amount does not prove period spending compatibility.

The fixed review message is: "Customer daily hypothesis; period spending impact
and provider edit validity are not assessed. Do not apply this value from this
plan." Show observed and customer-requested amounts separately, exact currency,
daily/micros units, original observation time/expiry, scenario name, and every
affected campaign. Keep the ordinary confirmed period ceiling and alternative
allocation totals visible with their existing independent-alternative semantics;
never multiply, prorate, sum alternatives, or equate these amounts.

## Version and cycle-free contracts

Reserve, but do not register, exact canonical policy/generator pair
`inlet.descriptive-review.v6` / `inlet.descriptive-planning.v6`. Existing V1–V5
retain every non-null owner-input generation refusal, including empty. A future
private V6 constructor can accept the existing input-only fields only after exact
canonical capability and source wiring are qualified; V3 remains the default.
Never construct a fake V5 document/ticket to obtain V6 reporting or creative proof.

New `google_budget_owner_review_contracts.py` imports only existing cycle-safe
common/context, intent, and owner-witness contracts, not ports/documents/service.
The existing CatalogEvidence class remains unchanged and reexported by ports.

```
GoogleBudgetOwnerReviewV1(NoAuthority):
    schema_version = 'inlet.google-budget-owner-review.v1'
    action_key: Key
    intent: ResolvedGoogleDailyBudgetIntentV1
    witness: GoogleDailyBudgetOwnerWitnessV1
    disposition: Literal['investigate_only']
    period_spending_compatibility: Literal['not_assessed']
    provider_edit_validity: Literal['not_assessed']
    application: Literal['unavailable']

GoogleBudgetOwnerReviewProofV1(NoAuthority):
    schema_version = 'inlet.google-budget-owner-review-proof.v1'
    input_digest: Digest
    reviews: tuple[GoogleBudgetOwnerReviewV1, ...]  # <=20
```

`PlanVersion.google_budget_owner_review: GoogleBudgetOwnerReviewProofV1 | None`
is omitted when None in Python/JSON/nested/canonical output. V1–V5 require None.
V6 requires non-null input `google_daily_budget_intents` and this complete proof,
including an explicit empty proof when the input tuple is empty; absent inputs do
not silently opt in. Preserve all existing document/action/policy bytes on older
pairs. Revalidate unsafe copies at digest/serialization/admission boundaries.

The existing full witness is deliberately retained, including exact CatalogEvidence,
rather than a digest-only summary that could not reconstruct membership. Repeated
catalogs for different owners must be byte-identical; implementations validate/index
each unique full account/composite once and reuse the validated index. Existing
1MiB document bound and MAX_ACTIONS remain hard limits: overflow fails explicitly,
never truncates owners/members or emits a partial proof. No private actor/session/
authentication scalar is added to the public proof. Existing opaque input commitment
is retained as an opaque value, never represented as public proof of authorization.

## Exact pure consumer ports

New `google_budget_owner_review.py` owns these pure functions (no SQL/HTTP):

```
compose_google_budget_owner_reviews(
    *, inputs: PlanInputRevision, catalogs: tuple[CatalogEvidence, ...],
    sources: tuple[SourceFence, ...], privacy_revision: int,
    first_priority: int,
) -> tuple[tuple[ManualAction, ...], GoogleBudgetOwnerReviewProofV1]

validate_google_budget_owner_review(
    *, inputs: PlanInputRevision, actions: tuple[ManualAction, ...],
    proof: GoogleBudgetOwnerReviewProofV1,
    catalogs: tuple[CatalogEvidence, ...], sources: tuple[SourceFence, ...],
    privacy_revision: int,
) -> None
```

Both use the unchanged full-source active binding kernel, not a weakened subset.
Sources cover every full input AccountRef exactly; no unrelated account source is
invented. They validate all supplied catalogs/normal allocation/exclusion joins and
strict UTC chronology, then derive each complete witness from the actual catalog.
The proof input digest and ordered intents equal the complete immutable inputs.
Every embedded witness equals the rederived witness, including all catalog fields,
opaque inventory commitments, complete member identities/settings and reference.
All document witness source fields match the corresponding retained reporting proof
account's source fence; privacy is exact and unanimous, never defaulted to zero.

One investigation action per `(full AccountRef, owner_key)` across all hypotheses,
not one per campaign or scenario. Key is `owner-review:` plus a domain-separated
fingerprint of full AccountRef and owner_key; no amount/session/time reset. Duplicate
owners are rejected, not coalesced with inconsistent hypotheses. Action target is
the exact representative, `kind='investigate'`, `native_budget=None`,
`proposed_fields=()`, no Apply/status/pause steps. Its only owner-setting advice is
the fixed investigation wording. All affected references are in the witness;
manual steps name the shared owner scope rather than telling users to edit members
individually. Exact action/proof keys and catalog evidence keys must join both ways.

Ordinary reporting/creative diagnostics may still reference an affected campaign,
but cannot acquire a second owner-hypothesis attachment or any native budget/status
proposal for that owner. This uniqueness rule concerns an owner-setting review,
not deletion of valid campaign measurement diagnostics. Validate the entire output
for conflicting budget/status proposals on affected members and reject rather than
silently dropping one. Existing action priority, global creative capacity, customer
constraints, exclusions and scenario reconciliation remain unchanged. Reserve space
for every required owner investigation; fail closed if the complete result cannot
fit MAX_ACTIONS. No loss of an owner entry to a creative-priority selection.

## Original receipt, final save, current and historical joins

1. Admission remains the integrated original-session receipt path: opaque selector
   is recomputed from actual actor/session/authenticated_at, full source and witness;
   final input/link writes are atomic. V6 does not relax that input contract.
2. Generation first validates the original retained input receipts and their scalar
   commitments. Current lookup uses the same original-session/paid/source/privacy/
   goal/window/expiry gates and original receipt; no latest-catalog fallback or
   fresh observer rebasing. The collected generation bundle must contain the exact
   catalog used by the saved allocation selector for each owner intent.
3. Pure composition uses actual bundle catalogs and sources. Final repository save
   compares every embedded witness with those actual catalogs, not merely with its
   own rehashed DTO or echoed input digests. Then repeat original receipt and full
   source/goal/privacy/authority checks in the existing owned SQL transaction before
   commit. No provider I/O under SQL and no new authority renewal/deadline extension.
4. Document validation enforces complete proof/action/input/source joins. Pure
   validation cannot authenticate opaque session commitments; SQL current/history
   wrappers must also run `validate_retained_input_receipts` against actual original
   rows. Missing input links never degrade to a display-only primitive hypothesis.
5. History/export preserve original observations unchanged. Add a genuine V6 branch
   to the complete selected/traffic/commerce/creative history validator, retaining
   all existing witnesses plus the owner proof. Reconstruct linked catalog evidence
   from original receipt rows; use the existing historical owner-input kernel and
   scalar commitment checks. Only the linked subset is needed for historical owner
   reconstruction, and its fences come from original rows, not current account
   state. Full existing selected/traffic/creative proof remains independently
   required; this subset cannot replace that validation.
6. Historical READ_ROLES and privacy/erasure gates remain; no current paid, receipt
   TTL, provider inventory, media-byte read or current session matching requirement.
   Input-link/catalog loss refuses history/export. Current reads prove persisted
   fences, not absence of out-of-band provider changes. Do not claim fresh native
   inventory on every SQL read.

No new table or retention period is proposed. Use the existing immutable
InputCatalogReceiptRow graph, PlanVersion canonical document and existing complete
reporting/creative dependency records. Before implementation, verify the current
complete-history validator can explicitly require the linked input graph alongside
its existing dependency set; do not omit it or add a speculative private ledger.

## Zero ceiling, empty input, and Q08

Existing admission rejects a positive daily hypothesis when the confirmed ceiling
is zero. A requested zero with zero ceiling may be retained and displayed only as
an unassessed investigation: zero does not establish a provider-valid budget,
pausing, stopped delivery, or zero spend. No positive native budget is synthesized.
Explicit empty owner inputs on V6 yield an empty owner proof and no owner action,
while the actual ordinary reporting/creative composition remains complete.

Q08 inputs have absent owner fields and continue genuine V5 unchanged. V6 does not
turn empty-account preparation or an absence observation into owner membership.
No witness can be created from an unavailable/partial owner catalog. Q06 partial
membership remains a refusal/reacquisition requirement, not an empty review.

## What would be needed for an actionable native-change proposal

This package intentionally does not choose new financial policy. A later proposal
would need verified provider semantics for actual daily-budget delivery/overdelivery
and any applicable charging/spending limits, exact effective-time/time-zone interval
and past spending/remaining exposure across the confirmed period, complete shared
owner membership and other simultaneous reservations/changes, native minimum/zero/
edit restrictions, and a qualified model bounding the proposed setting's future
period exposure. It would also need an explicit total-envelope/remaining-cap rule,
reconciliation of unknown outcomes, original mandate/consent and current session/
source authority, and policy evidence for each supported profile. Daily requested
<=observed, account billing availability, receipt freshness, and a human reviewing
a document establish none of these by themselves.

Selecting a review-only representation and precise proof joins is routine
engineering. Choosing supported financial risk/exposure policy is a genuine later
owner/product decision informed by those observations; do not ask the owner to
approve a weakened ceiling claim, guessed multiplier or unsupported zero edit.

## Ownership and ordered qualification (not authorized by this design alone)

A: pure new review contracts/composer/validator and omission/cycle/digest tests;
no registered capability. B: reviewed genuine V6 paired reporting/creative
composition and complete document/history/currentness dispatch, preserving V1–V5.
C: service/repository final actual-catalog binding, canonical private capability and
actual API qualification. Existing generation refusal is replaced only for exact
qualified V6; never remove the shared old-pair guard globally. Browser presentation
requires a separate reviewed UI contract after actual API/artifact qualification.

Required cases: original full owner appears once with all affected campaigns;
independent scenarios unchanged; daily amount has no NativeBudget/FieldProposal;
zero and empty distinctions; changed currency/member/source/window/facts/opaque
commitment and valid-rehash witness substitution fail; partial catalogs refuse;
foreign/session/goal/CAS/expiry/privacy drift fails atomically; completed replay and
historical export retain exact original proof; missing links/erasure refuse; no
extra provider calls on replay/export and no financial/execution effects; old
nested byte goldens/Q08 unchanged. Preserve actual Q06 artifacts as predecessors,
not silently relabel them V6 or claim full expert/live qualification.
