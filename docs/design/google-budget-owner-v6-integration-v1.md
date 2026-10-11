# Genuine private V6 owner-review integration

Design only, following reviewed standalone `072f6c3`, based on that immutable
implementation. No code, capability registration, tests or runtime activation in
this proposal. Default V3 and genuine V5/Q08 remain unchanged.

## Exact capability and document contract

Reserve exact canonical `inlet.descriptive-review.v6` / `inlet.descriptive-planning.v6`.
Future ReportingCapability mode is `owner_review_creative_selected_requested_window`,
with existing `local_reporting_v3` witness kind. Canonical digest equality is required
in ticket and service constructor; no environment flag, implicit latest policy, or
public default switch. Constructor injection remains private qualification only.

SelectedPolicyContractV1 may recognize the exact V6 pair with requires_creative=True;
add a derived (nonserialized) `requires_owner_review` property keyed to that exact
pair. Preserve old descriptor bytes. Existing assertion helpers recognize V6 only
in the reviewed pure recognition slice; runtime registry support is a later slice.
CreativePairedEvidenceV1 remains the genuine structural bundle: its full original
V6 ticket, selected/traffic sources and private image collection are checked through
exact canonical recognition. No fake V5 ticket, policy, stripped input or document.
GenerationEvidence needs no duplicate shape/union member when this same validated
bundle is used; the distinct capability dispatch selects the V6 composer.

PlanVersion adds omitted-by-default `google_budget_owner_review:
GoogleBudgetOwnerReviewProofV1 | None`. Exact V6 requires explicit non-null input
owner tuple and complete non-null proof, even when both are empty. Other pairs
reject non-null owner inputs and proof exactly as today. V6 requires all existing
selected, traffic, commerce, creative proof and composition fields; the owner proof
is additional, never a substitute. The document schema remains the extensible
`inlet.plan-version.v1`; the exact generator/policy pair carries the new semantics.
Old Python/JSON/nested/canonical bytes and historical hashes remain unchanged.
Normalize V6 instant comparisons to UTC without restamping any original value.

## Pure document validation and genuine composition

The new document invariant calls the reviewed active full-source owner validator
with actual input, all document actions, owner proof, the embedded linked catalogs,
and every SourceFence from selected_reporting_proof.accounts. Derive privacy only
from that complete retained proof; reject mixed or missing epochs. This checks
structural joins, not authenticity of opaque session commitments. The SQL boundary
below must authenticate those against original receipt rows.

New `GoogleOwnerReviewPlanComposer.compose(*, ticket, evidence:
CreativePairedEvidenceV1, policy, generated_at) -> PlanVersion` accepts only exact
canonical V6. It validates the complete original ticket/bundle, composes owner
investigations from actual `evidence.reporting.selected.catalogs` and ticket.sources,
and builds a genuine V6 document. The standalone owner proof functions stay unchanged.

Current SelectedPlanComposer._compose constructs the final document and is also a
direct old-version entry point with a refusal guard. Extract its shared section/
document-building body into a private typed function accepting the actual ticket,
paired evidence, creative collection and `owner_review: GoogleBudgetOwnerReviewProofV1
| None`. This is not an unchecked allow flag: the shared function must validate
exact canonical pair, the None/non-null matrix and the complete owner proof against
its actual catalogs/sources before building anything. Existing Selected/Creative
public and internal wrappers keep their old non-null refusal and exact-pair gates.
New V6 composer alone passes a validated non-null proof with the original V6 ticket.

Insert all owner investigations after ordinary campaign diagnostics and before
creative production, then generate creative priorities from the resulting action
count. Never silently discard owner reviews to fit creative capacity. Existing
global maximum_creative_assets, exclusions/constraints, scenario reconciliation,
conflict rules, MAX_ACTIONS and MAX_BRIEFS remain unchanged. Check the complete final
PlanVersion canonical byte size against the existing 1MiB bound, not merely the
standalone owner subset. Overflow is a fixed refusal without partial persistence.
One owner-setting review per full account/owner; no NativeBudget/proposed field or
Apply/pause promise. Ordinary measurement diagnostics remain separately identifiable.

## Separate active and historical owner validation ports

Keep the reviewed active `validate_google_budget_owner_review(...privacy_revision)`
full-source invariant unchanged. Add the separately reviewed pure port:

```
validate_retained_google_budget_owner_review(
    *, inputs: PlanInputRevision, actions: tuple[ManualAction, ...],
    proof: GoogleBudgetOwnerReviewProofV1,
    catalogs: tuple[CatalogEvidence, ...], sources: tuple[SourceFence, ...],
) -> None
```

It uses the existing historical owner-input binding kernel for the exact linked
catalog/source subset, no explicit/fabricated privacy argument. Share a private
validated action/proof comparison kernel with active validation, not a public
`skip_sources` switch. Original input accounts, goal, scenarios and created_at stay
whole. Empty/no-link proof is allowed only when the existing historical kernel
accepts its complete ordinary graph; do not fabricate a zero epoch or unrelated
account source. Duplicate/missing/foreign/relabelled catalogs and sources fail.

Refactor the existing retained input receipt validator internally to return its
already validated `(CatalogReceiptRow, CatalogEvidence)` pairs to a private consumer;
retain the public `validate_retained_input_receipts(db, inputs) -> None` behavior.
Expose a narrow `load_retained_owner_input_evidence(db, inputs) ->
RetainedOwnerInputEvidence` with immutable catalogs/sources only, after that complete
validation and original actor/session/authenticated scalar commitment check. No
private scalar is returned or serialized, no current Principal is fabricated, and
no SQL call is moved into a pure validator. Callers own clean original transactions.

## Final save, currentness, history and dependency completeness

Admission keeps the integrated exact original-session receipt selector/CAS path;
future V6 input acceptance adds only its canonical supported pair. Generation
refusal is replaced only for exact qualified V6 after completed replay and owned
input validation; every V1–V5 public/internal/document gate remains.

At genuine repository save, after existing completed replay and exact actual target
proof checks but before writes, compare the owner proof with actual bundle catalogs
and full ticket sources using the active validator. Recheck saved original receipt
links, opaque scalar commitment, original-session/paid/goal/source/privacy/window/TTL
and unchanged observation before commit. Existing selected/image/selected final SQL
rechecks remain required; no provider I/O inside their transaction.

Add exact V6 orchestration in a new `google_budget_owner_retained.py`:

```
capture_owner_review_retained_sources(db, *, principal, document, now)
    -> tuple[RetainedSourceWitness, ...]
recheck_owner_review_retained_sources(db, *, principal, document, dependencies, now)
    -> None
validate_owner_review_plan_history(db, document) -> None
```

Match existing creative capture/recheck signatures and error normalization exactly
when implementing (the names above do not broaden caller authority). Extract the
shared selected+commerce+creative currentness body behind exact V5/V6 wrappers;
do not call the V5 wrapper with a relabelled document. V6 additionally validates
original owner input links and exact proof against retained catalogs. Capture and
recheck return/compare the entire existing witness set, not only owner evidence.
Repeated original SQL authority, goal/privacy, root Session and underlying Connection
transaction identity checks occur after delegated calls and final DB time sampling.
Current-read READ_ROLES behavior remains independent of paid write admission.

No new PlanDependencyRow kind/table or retention period is needed for owner input
receipts: InputCatalogReceiptRow already binds plan/input revision/account/receipt,
and the document commits the complete input digest. V6 complete history must require
that exact graph in addition to every existing selected/traffic/commerce/creative
PlanDependencyRow. It cannot accept an owner proof merely because it is self-consistent.
Dependency maximum and overflow sentinel remain the V5 maximum (no new row kind),
with the existing bounded input-link fetch checked separately. Verify this with a
whole-set missing/extra dependency and missing-input-link test before integration.

History loads the exact saved PlanVersion row and every required dependency, then
uses original linked rows and the historical pure port. Preserve original values,
READ_ROLES and privacy/erasure/export guards. No current session, paid eligibility,
receipt TTL, current inventory, or media byte read is required for historical proof.
Input-link/catalog deletion refuses read/export; SQL currentness never claims it
has observed out-of-band native changes. All generic read/replay/export paths must
reach this complete validator; preserve exact completed replay semantics.

## Validation cost and authority window

The standalone proof has at most20 owner witnesses but each contains the full
catalog. Existing strict validators intentionally revalidate them at public model,
digest and serialization boundaries. Do not claim once-per-catalog parsing or move
work under SQL to save a function call. No unchecked prepared flag, process cache,
renewed identity fact, shifted clocks or expanded five-second authority window.

First qualify exact ordinary V6 end-to-end API behavior under normal clocks with
stage observation kept separate from acceptance. Preserve any deadline failure.
If bounded repeated pure work becomes material, separately review an immutable
prepared review value built before final SQL, bound to exact canonical input, full
actual bundle, policy and source bytes. The SQL consumer must still compare its
full commitments and current original authority/source graph. That optimization is
not approved here and cannot replace source/witness checks or hidden validation.
Earlier V5 profiling does not prove V6 cost; no speculative latency claim.

## Ordered small implementation slices

1. Historical pure review port + validated linked-evidence loader, with original
   scalar/epoch and empty/unrelated-account tests. No capability/service activation.
2. Genuine document/policy recognition and shared pure composition, old wrappers
   unchanged; exact V6 complete document/size/unsafe-copy/zero/empty/tamper tests plus
   old byte goldens/Q08. Registration remains unavailable to the runtime service.
3. Complete V6 current/history/export dispatch and dependency tests (both databases),
   no default policy. Then service/repository actual-catalog binding and private
   canonical registry/constructor support as one coherent tested runtime package.
4. Actual original-session API create/edit/generate/read/replay/export, foreign/
   expired/source/CAS/valid-rehash substitution/rollback/erasure negatives, ordinary
   zero and Q06 member deduplication artifacts. No native mutations or financial
   effects. UI presentation is a later separately reviewed interface.

This is investigation output, not economic qualification. Enabling actionable
native change still needs the additional provider/economic observations and explicit
risk policy listed in the predecessor design; no owner approval of a weakened cap
claim is requested or implied.
