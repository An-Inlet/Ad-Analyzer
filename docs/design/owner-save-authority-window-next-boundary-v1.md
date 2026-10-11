# Owner Save Authority Window — Next Boundary Proposal

Status: source-only proposal, not implementation or execution authorization. Based on
reviewed context `fb2d864` and inspection of the current combined service worktree.
The parent supplied combined06 observations; this document does not remeasure them.

## Observed Failure And Attribution Limits

Combined06 still refused before CAS at `repository.save_generation`'s authority final
check following retained capture, at fact age 6.51986 seconds. Save elapsed was about
6.515 seconds. The storage pair site was not reached. Retained capture was about
2.3258 seconds; seven nested owner-document validations occupied about .7958 seconds.
The save-exclusive interval of about 2.378 seconds includes 878 SQL calls, unwrapped
work and observer overhead: it is **not a pure-validation measurement**. Nested
intervals must not be added to enclosing intervals.

The restriction change eliminated one adjacent validation; it did not establish
adequate headroom. Even eliminating the measured .7958 seconds entirely would not
bring this particular 6.51986-second interval below five seconds, and most of those
validations cross freshness boundaries and cannot simply be eliminated. There is no
basis to promise that another small duplicate-call deletion will qualify the flow.
The observed run fails acceptance; it does not prove that every deployment or valid
input can never finish within five seconds. R01/R02 and the owner-flow incidents retain
their distinct evidence and unresolved original causes.

## Actual Save Boundary

`PlanningDocumentService.generate` composes outside the final fact window, then calls
its existing `authority.refresh(principal, provider)` once. It constructs the final
source callback and opens the save transaction. `repository.save_generation` performs:

1. Strict ticket/candidate parsing, exact capability dispatch, bundle/ticket binding and
   generation lower bounds, then the first authority lock.
2. Receipt replay, plan/input/parent checks against SQL; candidate/ticket bindings;
   pure reference, proof, target, allocation, empty-catalog and owner-bundle checks.
3. Paid/goal/account/privacy checks; final source callback; retained-source capture;
   authority final and current expiry; CAS.
4. Canonical row construction, dependencies/request receipt, flush, current expiry
   and authority final again.

Some pure work in step 2 uses only the original candidate/ticket/bundle but is currently
interleaved with SQL. Other work consumes freshly loaded SQL documents. These are not
interchangeable. No proposal moves SQL-derived validation, the source callback,
retained capture, or their guards outside the original fact window.

## Recommended Next Package: Establish Pure Admission Boundary And Its Cost

Do **not** implement a prepared-object bypass yet. The old V5 pure admission probe
found only about .09 seconds; that did not justify the ownership mechanism then. V6
has additional work, but combined06's exclusive residual is not evidence of its cost.
The smallest justified next package is a reviewed extraction of the existing pure
admission computation into an ordinary internal function, still called at the same
logical validation boundaries inside `save_generation`, plus a payload-free cost
observer at that exact function. This makes a later placement decision falsifiable
without introducing any trusted prevalidated object.

Proposed internal functions (names subject to source review):

    _validate_generation_packet(*, ticket, bundle, candidate)
        -> tuple[GenerationTicket, GenerationEvidence, PlanVersion]

    _validate_generation_candidate_bindings(*, ticket, bundle, candidate) -> None

The first performs exactly the existing initial strict parse/capability/assert-ticket/
UTC checks and returns those validated values. The second performs only original
packet comparisons: actor/version/parent/input relation; selected and creative proof;
full reference/cardinality/expiry/privacy; targets; allocation; empty-catalog binding;
owner generation-bundle binding. Its call remains at the existing post-SQL position.
Current plan/head/input/parent comparisons, receipt replay ordering, and SQL helpers
stay in their current positions. No new model, schema, version, cache, callback or
public entry point is introduced. Public `save_generation` must invoke both functions;
callers cannot supply a success flag. If extraction cannot preserve error/replay
ordering exactly, split the second function at those boundaries rather than move it.

An observer wraps only these ordinary functions, original-once and exception-preserving.
Report exclusive and inclusive time, SQL counts (expected zero), calls and enclosing
save/fact ages; never SQL text, arguments, graph contents or principal identifiers.
One coherent next source milestone may be selected by the parent for qualification;
this proposal does not authorize a retry of combined06 or any execution now.

Required checks for the extraction: exact V1–V6 rejection/output parity; unsafe copied
primitive/nested fields; original proof/ref/target and private-image pins; exception
ordering and exact completed-request replay; unchanged retained/currentness call order;
actual atomic rollback on late source/fact expiry. A real six-second delay must still
produce `planning_authority_expired` with no durable writes. No changed wall clock.

## Consequential Follow-On, Only If Measured Worthwhile

If the measured original-packet-only work offers useful margin, separately approve the
already designed private preparation mechanism in
[creative generation save preparation](creative-generation-save-preparation-interface-v1.md),
updated explicitly for V6. The intended location is **before the existing single final
identity refresh**, not a refresh after a failed/elapsed fact and not a second refresh.
It requires deeply owned strict snapshots, type-aware commitments including excluded
session/private pins, no alias/callback escape, one-use consumption before callbacks,
and tamper checks through final flush. Public unprepared save remains fully validating.
The new risk is trust in a previously checked in-process graph: ordinary frozen
Pydantic objects are insufficient because unsafe copies and object mutation exist.
No source/currentness result may be carried in that packet. All SQL checks, fresh
independent passes, original observation expiries and five-second acceptance remain.

If those pure costs are too small, do not build that mechanism or claim it fixes the
incident. The next decision needs actual attributed fresh-reader costs and a separately
reviewed **same-pass bounded query batching** proposal; not cross-pass caching. The
available aggregate measurements do not identify such a query change yet.

## Decision And Blocker Classification

This is an engineering qualification blocker, not a missing credential or a customer
permission problem. Current tested source cannot be called reliably qualified while
normal accepted inputs hit the five-second guard. There is no demonstrated remedy yet
that guarantees adequate margin under the preserved rules.

The recommended extraction/measurement requires parent technical review, not an owner
product decision: it changes no acceptance boundary. Moving pure validation before the
single fact acquisition is a consequential internal trust-boundary change and requires
its own reviewed ownership/mutation contract, even though it need not change public
policy. AGENTS prioritizes safety/isolation over speed; it does not authorize treating
a timeout as success or bypassing fresh checks. If later evidence shows mandatory fresh
work itself cannot fit, bring the owner a concrete architecture/acceptance choice with
measurements; do not silently extend/renew the deadline, remove passes, or label a
repeated successful retry as qualification. No such owner decision is requested now.

## Parent-Requested V6 Preparation Contract (For Review, Not Yet Approved)

The parent requests the concrete preparation option now rather than authorizing another
measurement first. The following supersedes the recommendation to extract alone if
reviewed and approved. It extends the earlier V5 proposal only to the exact canonical
V6 pair; V1–V5 public behavior remains unchanged. It is routine internal engineering
under the offline assignment, subject to technical security review, not an owner
request to weaken the authority model. No sufficient savings are promised.

### Exact Private Ports

    _prepare_owner_save(*, ticket: GenerationTicket,
        bundle: CreativePairedEvidenceV1, candidate: PlanVersion,
        request_key: str, request_digest: str) -> _PreparedOwnerSave

    repository._save_prepared_owner_generation(db, *, principal, fact,
        prepared: _PreparedOwnerSave, now, recheck) -> PlanVersion

Only `PlanningDocumentService.generate`'s exact V6 branch calls the factory after
composition and before its existing final `authority.refresh`. The fact is acquired
once, in its current relative order before all transactional currentness checks.
The prepared artifact is never an API field, public repository argument, policy flag,
constructor injection or transferable authority. Public `save_generation` retains
complete validation, including for V6 direct callers. Shared private SQL code is
permitted; an untrusted caller cannot choose a prevalidated boolean.

### Complete Owned Graph Inventory

| Root | Required owned content and commitment |
| --- | --- |
| Ticket | `operation_id`, `actor_id`, **`session_digest`**, complete `inputs`, `expected_version`, nullable `expected_parent_digest`, `privacy_revision`, complete ordered `sources`, `policy_version`, full `policy_digest`, original `prepared_at`, inherited authority flags. |
| Inputs | Every declared field, including original goal definition/confirmation, account identities, scenarios/exclusions/constraints, selected reporting selectors, creative input, and resolved owner intents with original selector/observation/facts commitments. No reconstructed reduced request subset. |
| Reporting | Complete `bundle.reporting.selected`: catalogs including full native/metadata documents and references, selected captures/proof, performance, commerce, context, all gaps and window gaps; complete paired traffic windows/gaps and envelope fields. No merely matching digest substituted for the actual graph. |
| Images | Complete `bundle.creative.basis`, exact requested creative input, every original observed image/time/hash/dimensions/metadata; complete ordered `rows` including each witness and private `created_by`; original `ticket_digest`. No media bytes or provider tokens enter this packet. |
| Candidate | Every declared `PlanVersion` field: inherited no-authority flags, schema, complete inputs/version/parent, exact policy/generator, readiness/limitations, actor/times, evidence/actions/scenarios/briefs/summary, quality status, selected proof, creative proof/composition, V6 owner proof and **complete ordered original `google_budget_input_catalogs`**. |
| Request | Exact request key/digest; bind additionally to ticket operation/actor/session/workspace/plan, not just document digest. |
| Derived | Exact canonical document UTF-8/digest, original input commitment, full type-aware structural commitments, expected complete evidence/target bindings. No SQL row, principal, fact, callback, clock, currentness result or live Session is stored. |

The factory strictly validates the supplied original graphs before reconstructing them.
It recursively copies **every declared field**, including fields omitted by public
serialization, into independent model instances/tuples; no shared mutable model or
container with callers. Revalidate reconstructed graphs and reject unsupported private
attributes or types rather than silently discard them. Field inventory must be asserted
against actual `model_fields` in tests so a future field addition cannot escape copying
or commitment. Runtime data is bounded by existing graph limits.

Commitment includes concrete model/enum classes, field names, strict primitive types,
ordered containers, Decimal tuples, and datetime wall representation, UTC instant,
offset/fold and timezone identity. Numeric false versus bool, bytes versus text, and
string versus datetime must differ. Include excluded session and image pins. Public
JSON/digest alone is insufficient. Do not use `model_construct` or JSON coercion as
proof of original validity. The artifact has an unforgeable-by-normal-callers local
factory seal and consumed state; Python reflection is not claimed as a sandbox.

### Pure Versus Current Map And Error Order

Factory can compute all original-graph checks listed in steps 1/2 above, including
`assert_owner_review_generation_bundle` on original collected catalogs. It **cannot**
replace `recheck_owner_review_input_receipts`'s `_linked` call after actual receipt
loads, nor any nested validation consuming data after a SQL/callback boundary.

Keep these operations in SQL exactly where they are: authority lock/current original
session; completed receipt lookup; plan/head/input/parent loads and comparisons;
paid/goal/account/privacy; all selected-image-selected source checks; current original
receipt TTL/opaque commitments; retained capture and every dependency; CAS, writes,
flush, final evidence expiry and final original-fact checks. No historical SQL document
may be treated as covered by the prepared original bundle.

Expected preparation failures must never precede the service's existing final identity
refresh. Even the former repository pre-lock checks occur **after** that provider call.
Use the exact phase inventory below. This replaces the earlier incorrect instruction
to raise pre-lock validation errors immediately in the factory.

#### Closed Error Descriptors And Phase Inventory

An internal descriptor is a fixed enum only, with no caller text, exception, traceback,
SQL object, principal or arbitrary status payload. The enum maps to the exact fixed
status/detail below. A phase stores success or the first descriptor in existing order;
subsequent phase failures cannot override it. Factory results do not raise those errors.
Only consumption after the existing refresh can emit a descriptor at its original site.

| Phase / existing position | Closed descriptor → exact status and detail |
| --- | --- |
| ENTRY: after final refresh, at repository entry, before authority lock | `UNKNOWN_POLICY` → 409 `unknown planning policy or generator`; `POLICY_EVIDENCE` → 409 `planning evidence policy differs`; `TICKET_EVIDENCE` → 409 `planning evidence does not match generation`; `EARLY_CREATIVE` → 409 `candidate generation predates original creative collection`. |
| CANDIDATE: after authority lock, original session check, exact receipt replay, plan/input-head checks; before prior-version SQL | `CANDIDATE_TICKET` → 409 `candidate does not match generation`. |
| SELECTED: after prior-version SQL/digest check | `SELECTED_PROOF` → 409 `candidate selected proof differs from actual read bundle`. |
| CREATIVE: at existing creative-proof comparison | `CREATIVE_PROOF` → 409 `candidate creative proof differs from actual read bundle`. |
| REFS: at existing full reference comparison | `EVIDENCE_REFS` → 409 `candidate evidence differs from actual read bundle`. |
| TARGETS: after existing target derivation | `OWNED_TARGET` → 409 `candidate target differs from actual owned catalog`. |
| ALLOCATIONS: existing `check_allocations` site, in its original iteration order | `AMBIGUOUS_CATALOG` → 409 `Selected target catalog is ambiguous. Read the current catalog again.`; `CHANGED_TARGET` → 409 `Selected target changed. Read the current catalog and select again.`; `ALLOCATION_CURRENCY` → 422 `Planning allocations must use the confirmed goal currency.` |
| EMPTY: after allocation validation | `EMPTY_CATALOG` → 409 `empty catalog witness differs from actual collected evidence`. |
| OWNER: after empty-catalog validation and before paid/goal checks | `OWNER_BUNDLE` → 409 `owner review differs from actual collected evidence`. |

This table enumerates possible fixed domain outputs, **not permission to catch every
ValueError or every HTTPException from the containing function**. Extraction must
identify the exact predicate or already documented expected-domain branch producing
each descriptor. A different status/detail is never serialized into the packet.
Neither provider errors nor clock, SQL, callback or arbitrary validator exceptions
are converted into these enums.

Unrepresentable checks remain in their existing call positions and are not executed
speculatively before refresh. In particular, raw `GenerationTicket.model_validate` and
`PlanVersion.model_validate` failures are not assigned new fixed409 meanings. Preserve
their current entry behavior after refresh. Any validator whose unexpected failure
cannot be distinguished without broad capture remains at its original site; a pure
function label alone does not justify moving it. Private strict ownership construction
must therefore have a non-throwing closed structural preflight: unsupported/corrupt
original graph selects an unprepared fallback, which invokes original public validation
after refresh. It must not silently coerce a copied graph into valid input. No arbitrary
user-defined property, serializer or validator runs in this structural preflight.

The prepared route may reuse only checks actually and safely completed under this
closed contract. Retained checks are not marked prevalidated. This narrows the potential
savings and must be reported; implementation must not enlarge the hoisted set merely
to hit the deadline. Full original validation remains mandatory, either in a separately
reviewed safely preparable branch or at original entry. The structural fallback is not
an authority-bearing packet and cannot skip any work.

Before implementing, a check-by-check source diff must mark each entry as safely
prepared or retained in place. Until such a branch is proven, the conservative default
is retained. Exact replay bypasses only the post-replay phases it already bypasses;
ENTRY still executes first, and provider revocation/failure precedes every ENTRY result.
Tests must combine provider revocation/failure with invalid packet, invalid packet with
completed replay, head mismatch with later allocation422, and a valid replay with later
metadata loss. No phase may change which original failure wins.

### One Use, Callback Isolation And Late Mutation

Consume verifies exact artifact type/seal/request commitments and burns it **before**
any callback or SQL invocation, including unsuccessful attempts and completed replay.
A second consume refuses. Source caller mutations after preparation cannot alter the
owned original. Prepare separately owned callback ticket/bundle copies before refresh;
callbacks never receive the candidate or artifact. Verify callback copy commitments
before/after each callback and never replace the prepared originals with callback values.

At consume entry, before/after external callbacks, before persistence and after final
flush, verify the original packet's type-aware commitments. Any tamper fails the entire
outer transaction; no partial head/dependency/receipt persists. Returning a candidate
must not leak the private artifact or reusable proof. No commitment walk renews clocks.
All existing final expiry/fact checks still run after potentially expensive walks;
commitment overhead counts inside the five seconds. This is not a mechanism for
accepting a stale currentness proof merely because original bytes remain unchanged.

### Exact Qualification And Decision Gate

Before implementation: independently review this field inventory, strict copy/commitment
algorithm, deferred error phases and private consume route. Required tests include
V1–V6 public parity; V6 complete/empty owner inputs; full original catalog substitution;
private session/image-created-by mutation; datetime/Decimal/enum lookalikes; original
aliases and callback mutation; reused/forged packet; replay after later metadata loss;
wrong actor/session/request; all current SQL mutation races; pre-CAS and post-flush
expiry rollback; real six-second authority refusal. Saved bytes/digests/dependencies
must match the public path exactly. Current SQL pass counts/order must remain unchanged.

One reviewed coherent uninstrumented API cohort plus a bounded observer can assess
whether the new placement actually reduces final-window cost. Neither a successful
single probe nor a lower pure-call count establishes reliable acceptance. If preparation
plus mandatory fresh work still exceeds five seconds, record that outcome and stop
claiming this slice resolves qualification; do not renew the fact or retry automatically.
