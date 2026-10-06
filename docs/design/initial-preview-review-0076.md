# Initial Preview To Exact Review: Proposed 0076 Contract

Isolated branch `codex/inlet-preview-review`, worktree `/workspace/inlet-preview-review`,
base `31a412d`. Proposal only until root freezes this interface. Migration0076 is
reserved exclusively, down0075. No production factory/live/financial gate changes.

## Durable Identity And Retraction

Add `ProviderExecutionReview.initial_preview_provenance_required` (non-null false
for ordinary legacy/manual reviews). A DB trigger forbids true→false; guards reload it
from storage rather than relying on cached ORM state. Initial-review writers set it in
the same transaction that persists the review and its provenance. Missing link never
means ordinary review. Marker enforcement is also registered for metadata test schemas.

One new table `initial_preview_reviews`:

- `review_id` primary key, `workspace_id`, composite FK to protected execution review,
  ON DELETE RESTRICT; unique(review_id, workspace_id).
- `original_preview_id` immutable32-character local reference, unique(workspace_id,
  original_preview_id). This survives derived erasure and is the idempotency identity.
- Nullable `preview_id, preview_workspace_id, preview_account_id, preview_campaign_id`,
  composite FK to PreviewRow owned4, ON DELETE SET NULL, all-present matching workspace
  or all-null check. Expiry/correction/source/privacy cascades therefore leave a
  retracted pointer, not renewed authority.
- `actor_id` protected customer FK, `original_session_digest` internal/nonexportable,
  `environment`, `preview_digest`, `intent_digest`, `policy_digest`, `evidence_digest`,
  `native_state_digest`, `mandate_digest`, `review_digest`, `plan_digest`, `expires_at`,
  `created_at`. Minimal commitments only: no calibration values, provider payload,
  credentials, amount copies or aggregate documents. Bind every field at read.

Immutable fields cannot change; the FK tuple may only transition once from present
→all-null. Never reattach to a replacement preview. Raw link deletion would also fail
closed because the protected marker survives, but preserve this minimal link for
idempotency and audit in ordinary lifecycle operations. Classify it with protected
execution provenance, strict safe export excluding session digest. Downgrade refuses
if marked reviews/links exist. Do not weaken attempted financial FK retention.

## Shared Runtime And Guard

Add separately named `initial_preview_review_guard` and `initial_preview_review_writer`
to `OptimizationRuntime`, both optional None. Their callable shapes match existing
review guard/writer signatures but do not use candidate-learning schemas or markers.

Introduce `publication.forward_provenance.check/check_id` that reloads the review,
runs the unchanged candidate/session-automation guard, then independently checks the
initial marker. If initial-required and its callback is absent, reject409. Route all
existing forward check sites in optimization.py (checked_review, approve, create_run,
claim before/after IO, final execute) and replacement.py through this aggregator.
No change to historical evidence_lock, receipt recording, reconcile or settlement.
The common prepare persistence helper invokes each separately named writer before its
single review commit; writer failure rolls back review+link together.

`InitialPreviewReviewRuntime(planning: InitialPlanningRuntime,
 optimization: CustomerOptimizationRuntime)` supplies existing actual dependencies.
No default registry; both runtime factories stay disabled. Normal customer optimization
assembly gains optional `initial_planning` context (TYPE_CHECKING reference). Its `bind`
uses actual current CustomerPrincipal and IdentityProvider to install
`initial_planning.review_bridge.guard_for(planning, principal, provider)`. This ensures
generic approve/start/advance routes enforce the same provenance without an endpoint
special case. A worker/runtime missing that binding fails closed. No inferred principal.

Guard under workspace-first locks:

1. Verify current actor/session equals link's original session; reauthorize it freshly.
2. Resolve owned preview via existing `preview.read_preview`, strict intent/document
   commitments, current confirmed goal, source epoch/current completion, policy,
   observation/calibration dependencies, explicit consent and dual app/DB expiry.
3. Reload and lock link after those fences; reject missing/null/changed pointer. Bind
   exact persisted plan to preview campaign/native state/choice/mandate and budget action.
4. Reauthorize original session and use fresh effective clock again after waits. Run
   existing financial current/qualification/exposure checks unchanged at their gates.

These are local DB checks; no provider IO while holding the final guard's locks.

## Actual Preparation And Idempotency

New POST `/initial-planning/previews/{preview_id}/review`, owner+CSRF, body only
`expected_preview_digest`. No client amount, financial proof, policy or native ID.
Response is existing exact review view plus preview provenance identity; no approval.

`prepare_preview_review(session_factory, principal, identity_provider, workspace_id,
 preview_id, expected_preview_digest, runtime)`:

- Own short-lived session. Read valid proposed preview with exact native amounts,
  complete choice and separately consented mandate. Reject hold/insufficient/no-native
  previews. Derive target/action from persisted intent and preview, never request JSON.
- If a provenance link already exists, validate its original session, pointer, preview,
  exact review and current financial review predicates; return that same review or a
  precise stale/retracted error. Do not create a replacement for a lost response.
- Otherwise use existing customer optimization catalog discovery and
  `optimization.prepare_optimization` with actual qualification_reader, transport
  read_current and exposure_reader. Preserve their commit/IO boundaries; this service
  owns its DB session and never commits the caller's transaction.
- Use preview-specific rationale digest so a coincidental ordinary manual review is
  not adopted. After external reads, the atomic writer rereads preview/dependencies,
  original session and fresh clock, verifies exact before state and resulting action,
  then sets marker+link before commit. Current exposure/financial validation is real;
  preview nominal amounts are never financial proof.
- Unique(workspace, original_preview_id) resolves concurrent/lost-response attempts.
  On unique collision roll back the new review, fresh-load and validate winner; no
  second committed review. Do not blindly retry provider calls or create reservations.

Ordinary manual plans remain ordinary explicitly reviewed plans. A marked preview review
cannot be approved/claimed/executed through any generic/manual route without its guard;
passing its ID or deleting its link does not remove required provenance. Do not treat an
independent newly authored manual plan as revived preview authority.

## Acceptance Before Freeze

Real Meta HTTP native reads plus actual qualified contract-test financial fixtures:
exact preview→financially validated review→manual approval/run/claim/final emission.
Missing actual qualification/exposure must fail; factories remain None in production.
Test original-session mismatch, stale native response, correction during qualification,
expiry during IO, duplicate concurrent/lost-response creation, mismatched action/digest,
FK-null/deleted link, attempted marker downgrade, generic approve/start/advance bypass,
retraction after claim before final emission, and PostgreSQL lock races. Assert no new
provider write after invalidation and no duplicate review/reservation. Preserve existing
attempted receipts/holds and successful historical reconciliation/settlement after
capsule erasure. Actual0076 upgrade/downgrade and lifecycle export classifications required.

Consumer UI owner may add a current-preview Review button and navigate to existing exact
execution review only after this shared contract is frozen. Frozen InitialPreviewV1
`review_available=False` bytes remain unchanged; expose new review capability/status in
an additive endpoint/projection rather than relabelling old stored documents.

## Frozen Refinement And Callable Names

Idempotency is anchored on protected ProviderExecutionReview.initial_preview_origin_id,
unique(workspace_id, origin), consistent with its required marker. The origin is immutable
once set; deleting the child link cannot reset it or mint another review. Missing link
returns retracted409. Candidate/automatic and initial markers cannot be mixed.
The earlier child original_preview_id proposal is replaced by this protected origin.

Frozen types: review_contracts.InitialPreviewReviewIntent/Prepared/Runtime/Guard/Writer;
review_models.InitialPreviewReviewLink. Optional CustomerOptimizationRuntime.initial_planning
and OptimizationRuntime.initial_preview_review_guard/writer have None defaults.

Implementation callable (next backend commit):
`review_bridge.prepare_preview_review(runtime, principal, identity_provider, workspace_id,
preview_id, expected_preview_digest) -> InitialPreviewReviewPrepared` owns its session
via runtime.planning.session_factory. `review_bridge.guard_for(planning, principal,
identity_provider) -> InitialPreviewReviewGuard` is request-bound, never global.

This contracts/models checkpoint does not claim migration/guard/bridge implementation.
0076 backend owns the required immutable-origin triggers and complete schema migration.
