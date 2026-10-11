# Genuine V5 Atomic Planning Service V1 — Proposal

Design only, based on `f509f3a`. Implementation requires review approval and the
frozen, reviewed [creative retained dispatch](creative-retained-dispatch-interface-v1.md)
and currentness package. This document does not register a capability, change a
runtime, introduce execution authority, or change the default v3 policy.

## Existing Implementation And Dependency Boundary

`service.py::_generate` currently prepares a genuine saved-input ticket under
original-session authority, closes SQL before owned reporting collection/composition,
refreshes original identity outside SQL, and calls `repository.save_generation` in
one final transaction. The repository checks idempotent receipts and input/version
heads, candidate/input/parent/actor/evidence/targets, paid work, goal, accounts,
privacy, source rechecks and complete retained witnesses before version-head CAS.
It flushes the version, dependency rows and request receipt together, then checks
expiry and original authority again. Those checks must remain for v1–v4 and v5.

Reviewed standalone v5 ports already exist: OwnedCreativePairedReader,
CreativePairedEvidenceV1, CreativePlanComposer, private CollectedCreativeBasisV1,
creative_proof_from_collection, recheck_collected_creative, PlanVersion's typed
proof/composition validation, creative_basis_reference and immutable history
validation. They are not yet service generation. The current capability registry
rejects v5, GenerationEvidence excludes the creative envelope, and service/repository
routing only understands the existing three evidence families.

Prerequisite retained dispatch must supply all ordinary plus local reporting,
commerce and creative dependencies, with current metadata and historical validation
remaining distinct. Do not substitute the reporting-only helper or filter creative
rows to satisfy the old v4 validator.

## Exact Additive Ports And File Ownership

1. `policy_capabilities.py`: add one exact canonical pair
   `inlet.descriptive-review.v5` / `inlet.descriptive-planning.v5`, mapped to a new
   distinct mode `creative_selected_requested_window` and existing
   `local_witness_kind="local_reporting_v3"`. Add v5 to exact canonical ticket
   digest recognition. Preserve every existing mode, descriptor byte/digest and
   rejection of mixed/altered policies. The new mode prevents confusing an ordinary
   selected bundle with a complete creative bundle. Recognition is not execution.
2. `generation_ports.py`: extend GenerationEvidence by CreativePairedEvidenceV1.
   Keep the existing reader protocol and all old concrete members unchanged.
3. `PlanningDocumentService.__init__(engine, provider, clock=utc_now, *, policy=None,
   media_store: MediaStore | None = None)`: additive keyword only. Canonical v5
   requires an explicitly supplied server-owned MediaStore; missing store fails
   construction before provider/storage/SQL work. Default policy remains exact v3.
   No user-supplied store/path, default local store, lazy storage creation in SQL or
   automatic fallback. Existing constructors remain unchanged for v1–v4.
4. `service.py`: instantiate OwnedCreativePairedReader with the exact original
   principal/provider/ticket and injected store only for the new mode; compose with
   CreativePlanComposer on that genuine ticket and complete private envelope.
   Preserve original v4 entrypoint refusal of v5; do not generate v4 and retag it.
5. `repository.py::save_generation`: retain its signature and recheck callback.
   Add exact creative bundle/candidate binding and complete evidence extraction,
   described below. Do not accept new client evidence or callbacks through an API.
6. Capability view consistency requires only a narrow addition in
   `capabilities_view.py` and the existing API capabilities calculation:
   selected_reporting_available is true for the two selected modes. Existing
   response fields and all default-v3 responses remain identical. Do not invent a
   creative UI availability flag or activate a default v5 service factory.

Private CollectedCreativeBasisV1 rows and ticket/session commitments remain in memory;
only the public immutable proof/composition enter PlanVersion/API/archive output.
Never serialize the private collection as a response or log it. New imports must
preserve fresh-process document/ports/generation/service import-order safety.

No migration/new dependency kind is expected: existing ordinary creative_basis and
local_creative_basis_v1 contracts already define exact row contents. Do not change
those commitments, reporting local_reporting_v3 hashes or old serializers.

## Explicit Storage And API Assembly

The ordinary `app/api/customer_planning_documents.py::service` factory continues
constructing default v3. Actual API qualification replaces that server-side factory
with an explicitly configured canonical-v5 PlanningDocumentService and actual local
private MediaStore; it does not fake API responses or inject ready evidence.
The factory must retain detaching the loaded original principal and rolling back
the request-authentication Session before any provider identity check.

A later production v5 assembly must explicitly pass the approved configured
MediaStore outside SQL. It may reuse the existing configured storage port, but this
package neither provisions storage nor silently selects development storage. API
injection qualification is not a deployed customer default or production storage
qualification. No browser-selected policy/store or new public configuration setting.

## Original-Session Generation Flow

- Create/revise: exact v5 requires explicit typed creative input and explicit
  selected_reporting, including deliberate empty selections. Existing prepared
  source/catalog receipts, owned media-reference admission, budgets, confirmed goal,
  actor scope, request digests, input-head CAS and paid/privacy guards remain.
  The saved creative input must survive its canonical digest and subsequent reads.
- Generate preparation: preserve original issuer/subject/user/session/authenticated
  time and owner role. Refresh external identity before opening SQL. Check the owned
  plan/request receipt, expected input/version heads, current saved input and goal;
  prepare the original source/privacy ticket with the complete canonical v5 digest.
  Close this transaction before reporting, blob reads, decoding or composition.
- Collection/composition: use the actual OwnedCreativePairedReader and its strict
  post-context deadlines; use the actual CreativePlanComposer. Both operate on the
  original ticket including its creative input. No synthetic replacement ticket,
  private collection restamping, copied v4 document, removed proof or implicit latest.
- Refresh the same original external identity after collection and before final SQL;
  this is not permission to adopt a replacement session. Preserve the five-second
  IdentityFact freshness and current DB principal checks after all lock waits.

## Final Candidate Binding And SQL Recheck

Before mutation, revalidate the genuine ticket, candidate and complete bundle. Exact
canonical ticket capability, configured generator and candidate pair must agree.
The new mode accepts ONLY CreativePairedEvidenceV1. The bundle must assert_ticket.
Preserve full input digest, actor/session, source set, expected version/parent and
privacy checks; candidate.generated_at must not precede original ticket preparation
or any original collection/image observation. Compare aware bounds as UTC instants.

For v5 define these local views without modifying their objects:

- reporting = bundle.reporting; selected = reporting.selected;
- expected_creative_proof = creative_proof_from_collection(bundle.creative, ticket).

Candidate selected_reporting_proof equals selected.reporting_proof in full.
Candidate creative_proof equals expected_creative_proof in full, retaining all image
observed_at and row commitments. Candidate creative_composition must bind that same
basis, and PlanVersion must enforce exact typed proposals/actions/briefs, creative
reference, customer capacity and every existing target/exclusion/budget/authority
invariant. Repository does not independently certify prose quality or visual claims.

The exact expected evidence set comprises selected catalogs, selected performance,
selected context, commerce when present, all reporting.traffic references, plus
creative_basis_reference(expected_creative_proof, ticket.inputs,
candidate.valid_until). Require equal key cardinality and complete value equality
with candidate.evidence, not a subset; no manufactured extra reference or substituted
source digest. Every privacy revision equals the ticket. Candidate validity cannot
exceed ANY original reporting/traffic reference expiry. Check actual native targets
against the original collected catalogs for actions, briefs and allocations.

After existing workspace-first authority/input/version locks, paid/goal/accounts/
privacy checks and before any CAS/write, the service recheck callback performs:

1. recheck_selected_paired_sources on the original reporting envelope;
2. recheck_collected_creative on the actual private collection with fresh aware UTC
   time and SQL-only original authority callback; require returned proof equal both
   expected_creative_proof and candidate.creative_proof;
3. recheck_selected_paired_sources again after image locks;
4. recheck_saved_input_receipts using the actual collected catalogs and original
   ticket, retaining all existing source/catalog receipt requirements.

No identity-provider calls, native requests, private blob reads or decoding occur
inside this transaction. Row locks use the existing order; rechecks must operate
on the clean active root/Connection expected by their approved ports. Never bypass
clean-root checks or catch them to retry within the same transaction.

Then capture the COMPLETE current retained witness set through the approved generic
v5 dispatcher before writes: one local reporting witness per account, commerce,
and exactly one original creative witness, even for zero images. Verify expected
cardinality and bindings. Keep ordinary evidence dependencies separate and complete.
Resample fresh DB UTC and original authority after all rechecks/lock waits. Paid,
goal, account/source and privacy authorization must still hold before head CAS.

Persist version-head CAS, immutable canonical document, all ordinary/local dependency
rows and actor-scoped generate receipt in one transaction. Preserve exact canonical
bytes and original proof timestamps; no media-row or external-account mutation.
After the final flush, perform fresh expiry and original-authority checks before
acceptance/commit. A late failure rolls back the head and every inserted row/receipt.
No nested-savepoint release may commit a losing partial result; qualify real SQLite
transaction behavior as well as PostgreSQL.

## Idempotency, Errors And Historical Reads

Both pre-collection and final-transaction receipt lookups retain workspace/actor/
operation/request digest/plan binding. An exact completed request returns its exact
stored immutable version without recollection, image reads or new observed timestamps.
A conflicting body/plan/actor must not obtain a foreign receipt or replace history.
If another request wins the final CAS, the loser leaves no version/dependencies/
receipt. Unknown response is resolved by the existing request lookup/replay flow.
Historical replay is not a claim that the image blob or source remains current.

Use explicit known domain errors (PlanningImageUnavailable, RetainedSourcesChanged
and existing fixed HTTP409) for source-conflict mapping. Preserve 401/402/403 and
unexpected provider, clock, database or storage exceptions under the existing
underlying contracts. In particular, do not copy the existing broad v4 collect-call
ValueError catch into v5: unexpected callback ValueError/ValidationError must not
be mislabeled optional source absence. Pure DTO validation/composition errors may
be normalized only around those specific calls, outside callback/provider I/O.
No raw private paths, token/context material or provider payloads enter responses.

Version loading already dispatches selected history when the reporting proof is
present; the reviewed v5 complete-history path must be used unchanged. Current reads
and new decisions/assertions require complete current reporting+creative witnesses;
metadata loss means source_changed. Immutable historical export remains readable
without current blob access or paid entitlement while viewer/lifecycle authority
still holds. Semantic privacy erasure removes the owned retained graph. Do not turn
historical readability into currentness or execution permission.

## Qualification Before Freeze

Use existing actual login/owned source/confirmed goal/fixture billing/image-upload
ports and injected native MockHTTP, then actual HTTP input save -> generation -> SQL
version/dependencies/receipt. No direct version seeding, validator stubs or prebuilt
reporting/image envelopes in the positive service journey.

- Both databases: Google selected/raw traffic plus image; Meta/TikTok explicit
  unsupported selected gaps with typed creative proposals, empty and multiple images.
  Retain actual product/price/media/source context and no invented social conversions.
- GET current, versions, exact export and request lookup/replay; unchanged original
  image times/proof digests; new input correction/reconfirmation -> next generation
  with exact parent digest and immutable prior version; compare versions normally.
- Foreign workspace/account/media/request, wrong original actor/session, mixed or
  altered policy, missing production store, absent selected/creative inputs and stale
  input/version/catalog/source/goal/privacy/billing/role/session. Reject without
  partial rows or provider/storage work where the failure is knowable beforehand.
- Reporting during image I/O, media metadata after inspection, stale receipt, candidate
  proof/reference/target substitution, dropped/extra dependency and empty-image paths.
  Verify current source_changed versus readable original history after metadata loss.
- Actual closure/archive and semantic erasure cover a service-produced version and
  all creative/selected/traffic dependencies, not only manually persisted fixtures.
- Before-write and after-flush faults, expired identity after lock wait, expired
  evidence, concurrent generation/CAS loser and lost-response replay. Inspect SQL
  counts/head/digests and verify no new receipt or source side effect on failed saves.
- Assert provider/storage I/O never occurs inside SQL; callback errors retain identity;
  final original authority/time checks still run. READ_ROLES history/currentness
  remains distinct from owner-only generation and paid work.
- Unchanged v1–v4 API/composition/document/witness/history behavior and default v3
  capability response. Updated v5 capability is available only through the explicit
  injected service; no production factory switch, ad mutation or publication.

Run bounded coordinated SQLite/PostgreSQL tests, whole Ruff/configured mypy and
independent review. No Full, live/provider calls, push, hosted checks or deployment
are implied by this proposal. Human creative-quality assessment, actual browser v5
journeys and production store/live qualifications remain separate later packages.
