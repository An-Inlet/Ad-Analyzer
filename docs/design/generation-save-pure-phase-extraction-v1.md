# Generation Save Pure Phase Extraction

Source-only interface for review, based on `6986557`. No preparation artifact,
validation bypass, new schema, refreshed fact, changed error descriptor or new caching.
Purpose: expose exact existing work to later bounded attribution; not a timing fix.

## Ports And Exact Positions

All four ordinary private functions live in `app/planning_documents/repository.py`.
They receive no Session, principal, clock or callback. Existing imported functions and
exception clauses remain identical. The added `ReportingCapability` import is typing.

    _generation_entry(ticket: GenerationTicket, bundle: GenerationEvidence,
        candidate: PlanVersion
    ) -> tuple[GenerationTicket, PlanVersion, ReportingCapability]

Moves only the current contiguous entry block from ticket model_validate through
creative generated-at lower-bound refusal. Returned ticket/candidate are the same
validated values previously assigned locally. Bundle is not copied or newly validated
beyond the existing assert_ticket. Raw validation errors, capability ValueError mapping,
bundle mapping and exception causes remain untouched. Call is at repository entry,
after service's existing identity refresh, before deriving workspace/plan and locking.

    _generation_candidate_relation(ticket: GenerationTicket,
        candidate: PlanVersion, actor_id: str) -> None

Moves only the candidate.inputs/version/parent/generated_by/policy comparison and its
fixed409. `actor_id` is the existing `current.user.id` scalar evaluated at that exact
callsite. This remains after exact replay and saved input/head comparisons, before
prior-version SQL read. No change to principal loading/authority checks.

    _generation_actual_bindings(ticket: GenerationTicket,
        bundle: GenerationEvidence, candidate: PlanVersion) -> None

Moves the contiguous block beginning `reporting = ...` through the empty-catalog
binding exception clause. Selected proof, references, creative proof, complete target
mapping, allocation validation and empty-catalog validation remain in exact order.
The allocation helper retains its ambiguous/changed409 and currency422 directly;
no extra catch. Call stays immediately after the prior-version check, before owner
bundle checks. The `actual`/`reporting`/refs/targets locals do not escape this function;
no later code currently uses them.

    _generation_owner_binding(ticket: GenerationTicket,
        bundle: GenerationEvidence, candidate: PlanVersion,
        capability: ReportingCapability) -> None

Moves only existing mode branch, creative bundle isinstance refusal, and call to
assert_owner_review_generation_bundle. Remains immediately after actual bindings,
before paid_work. No owner-generation helper or nested validation change.

## Ownership And Invariants

Author owns repository.py, one new focused test module and package ledger. No service,
authority, storage, model, source-reader or existing fixture changes. Current paid,
goal, account, privacy, final_sources, retained capture, receipt TTL/opaque checks,
CAS, writes, flush, evidence expiry and final authority remain textually unchanged.
No check crosses SQL, provider refresh or a callback. All old exceptions retain type,
status, detail and cause; only extra internal traceback frames are expected. Every
public save call invokes all applicable functions, except the same early replay paths
that already bypassed their corresponding blocks. No direct function result is a
reusable proof or authority. No argument snapshot/ownership mechanism is introduced.

## Source Preflight And Bounded Qualification Proposal

Before execution, reviewer compares each extracted block to its exact prior statements
and public call ordering, including original actor scalar read. Focused tests should
check helper call order around replay/head/parent gates using the existing genuine
fixture; exact wrong-packet raw ValidationError, capability409, relation409, proof409
and allocation422 behavior; successful unchanged stored bytes and rollback on late
failures. Existing actual owner/currentness tests remain distinct from service-save
qualification. Select exact reusable nodes after source review; no test execution or
new diagnostic probe is authorized by this document.

A later observer may wrap these ordinary functions with original-once calls and bounded
payload-free timings/SQL counts. Expected helper SQL count is zero except the actor
scalar remains read at its former public callsite. Unexpected SQL would need diagnosis,
not suppression. Nested owner calls overlap their wrapper and must not be summed as
independent cost. No performance or R01/R02/R03 closure claim follows from extraction.
