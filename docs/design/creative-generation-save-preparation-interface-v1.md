# Creative Generation Save Preparation — Proposed Internal Interface

Status: design only; independent review required before implementation. Inspected
production `226841a` / documentation `3675480`. No source/test execution, authority
change, runtime activation or claim that a failure has been explained.

## Measured Boundary And Limits Of The Evidence

The actual PostgreSQL browser run `both-02` received a generation 409 whose exact
response detail was not retained. Its cause remains unknown. The isolated and
instrumented journeys passed. The retained `stage-timing-05.json` records:

| Generation | Total Wall / SQL Calls | Final Save Wall / SQL Calls | Maximum Fact Age |
| --- | --- | --- | --- |
| First | 12.926 s / 8,079 | 3.582 s / 2,276 | 3.583 s |
| Second | 12.952 s / 8,113 | 3.946 s / 2,293 | 3.946 s |

Each generation contains two selected final rechecks of 692 SQL calls each, an
image recheck of 103, and retained witness capture of 697. These nested stages
**overlap**: do not add their durations or counts to their enclosing save duration.
Candidate composition is already outside the final IdentityFact window (0.280 and
0.261 seconds, zero SQL). Moving composition is therefore not a proposed improvement.
Earlier same-pass selected/traffic reuse reduced query counts but did not prove a
latency improvement. Neither measurement proves why the uninstrumented 409 occurred.

Evidence is retained at
`/workspace/inlet-evidence/20261011/creative-portal-browser/stage-timing-05.json`
and its sibling `inlet_v5_browser_timing.py`. No payloads, credentials or SQL statement
parameters belong in additional instrumentation.

## Smallest Next Slice

Prepare **pure v5 repository admission**, once, before the service's existing final
`authority.refresh`. Do not optimize database readers in this slice. In particular,
retain every independent selected / image / selected recheck and full retained-source
capture, including the double proof reads inside each selected account pass.

Concrete currently repeated pure work in `repository.save_generation`:

- Strict `GenerationTicket` / `PlanVersion` revalidation and exact capability dispatch.
- `CreativePairedEvidenceV1.assert_ticket`, including its strict nested model parsing.
- Candidate input/version/parent/actor/policy bindings to the original ticket.
- UTC generation lower bounds: ticket preparation, reporting collection and all image
  observations, including the no-image case.
- Exact selected/creative proof, full evidence set/cardinality/privacy/expiry binding,
  and action/brief/allocation targets against the complete observed catalog.
- Candidate canonical serialization/digest and input digest, currently computed again
  during final SQL persistence/comparison.

These computations depend only on original immutable inputs and observations, not
on current database authority. Their outputs cannot replace any live SQL check.
The exact timing attributable to these operations is **not separately measured yet**;
this slice is a falsifiable preparation hypothesis, not a promised latency fix.

## Private Ports And Ownership

Proposed module: `app/planning_documents/creative_save_preparation.py`.

    _prepare_creative_save(*, ticket: GenerationTicket,
        bundle: CreativePairedEvidenceV1, candidate: PlanVersion,
        request_key: str, request_digest: str) -> _PreparedCreativeSave

    repository._save_prepared_creative_generation(db, *, principal, fact,
        prepared: _PreparedCreativeSave, now, recheck) -> PlanVersion

The factory is called only by the genuine-v5 branch of
`PlanningDocumentService.generate`, after composition and before the **one existing**
final identity refresh. No new refresh, changed timestamp, retry, deadline renewal
or SQL transaction is introduced. V1–v4 continue through the existing public path.
The existing public `repository.save_generation` must continue fully validating
caller-supplied arguments; a direct caller cannot supply `validated=True` or a proof
shortcut. Shared SQL code may be factored privately without weakening that entry.

`_PreparedCreativeSave` is a private one-use in-process object, not a Pydantic public
DTO, serialized receipt, cache, service constructor option or caller extension port.
It carries independent deeply owned, strictly revalidated snapshots of the exact
original ticket, complete bundle (including private image row pins), and candidate;
original object aliases are not retained. It also carries their domain-separated
commitments, candidate canonical bytes/digest, and exact request identity. There is
no database/currentness/authorization result in this object.

Construction must call each real strict model validator before copying; this catches
invalid `model_copy` graphs rather than legitimizing their JSON-coerced forms. No
`model_construct`, fake-v4 ticket, dictionary downgrade or policy retagging. Private
pins and original session binding remain private; none are logged or exported.

### Defensive Commitment Rule

Ordinary model canonical JSON alone is insufficient as a private mutation guard:
for example replacing an aware datetime with its ISO string could serialize equally.
An internal type-aware structural commitment must cover model class/declared fields,
exact primitive types, ordered tuples, enum type/value, Decimal representation and
aware datetime representation as well as every field value. Reject unsupported graph
types and cycles, with bounds inherited from the existing models. Do not use a public
JSON serializer that drops excluded/private fields. Private image row metadata and
original ticket session commitment must be included.

At consume, reject a wrong concrete type, absent factory seal, reused/consumed object,
request substitution, or any changed private graph commitment. Recheck commitments
before and after extension callbacks and immediately before persistence/return.
Callbacks must not retain or be allowed to replace the prepared object's private
snapshots. Prefer detached callback copies; if copies would require materially
expensive parsing inside the fact window, retain strict construction outside it and
check their type-aware commitments as well. No process-wide or transaction-global
cache, cross-request reuse, shared mutable containers or caller-provided prepared
artifact. A failed consumption cannot be reused under another fact.

This defensive step is part of the performance measurement: replacing validation
with an equally expensive commitment walk is not a demonstrated win. Do not remove
mutation checks to meet a timing target.

## Checks Which Stay Inside The Final Transaction

Keep the existing workspace/user/session lock order and exact original actor/session
binding; exact completed request replay behavior; current plan/input/parent heads and
saved input digest; paid access; current goal; account/source ownership; privacy;
selected-image-selected source validation; input receipts; fresh retained witnesses;
original observation expiries and UTC bounds. No media blob/provider I/O under locks.

Current selected/image checks continue accepting the real ticket and real collection.
A prepared candidate is not authority for current source state. Currentness passes
must not reuse a prior selected graph, image row snapshot, source proof or SQL result.
All existing final authority checks remain in their current acceptance positions,
including after flush. `AUTHORITY_MAX_AGE_SECONDS` remains 5.0. Elapsed evidence and
session expiration still fail even if preparation succeeded. CAS, version/dependency/
receipt writes and rollback semantics remain atomic and unchanged.

## Required Qualification Before Accepting An Implementation

1. Pure parity: exact v5 candidate bytes/digest/evidence and private original pins;
   legacy v1–v4 outputs unchanged. Copied-instance invalid primitive/nested values,
   altered policy/proof/ref/target, early generated timestamp and empty images reject.
2. Original-object mutation after prepare cannot alter the owned snapshot. Deliberate
   private snapshot tamper, datetime-to-string canonical lookalike, callback mutation,
   artifact reuse and wrong request must fail before lasting writes.
3. Actual v5 API: Google zero/one/two images, Meta/TikTok; fresh independent reporting
   and image mutation races; privacy/session/role/goal/billing change; exact replay;
   post-flush rollback; missing/corrupt source must not become an absence gap.
4. Preserve the actual six-second authority-delay test: exact 409
   `planning_authority_expired`, zero version/head/dependency/receipt effects. No fake
   clock, extended deadline or retry in that test.
5. Instrument preparation, repository pure admission and final SQL save independently,
   with bounded counters only. Compare same genuine fixture before/after: pure
   validation invocation counts, final SQL calls, final fact age, CPU and elapsed time.
   Expected SQL counts are unchanged for this slice; an unexplained SQL reduction is
   a review signal that a fresh check may have been removed. Report normal uninstrumented
   outcomes separately; do not sum overlapping stages or claim a general speedup from
   a single pass. If preparation does not meaningfully reduce final authority-window
   work, do not present it as the remedy; retain results and propose a separately
   reviewed SQL reduction instead.

## Ownership And Decision

If approved: agent owns the new private module, narrow service/repository factoring,
focused tests and ledger. Root retains actual browser qualification and timing harness.
No other reader, schema, public interface, identity provider or default policy changes.
No owner decision is needed for this bounded engineering experiment. Runtime/live
activation and product claims remain unchanged. Implementation is not authorized by
this document itself; parent review must approve the private ownership/mutation design.
