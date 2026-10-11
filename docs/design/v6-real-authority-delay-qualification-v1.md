# Actual V6 real-clock authority rollback qualification

Status: source-only proposal from root138daab; no implementation or execution.
Owner: google_runtime. Proposed ownership is one new test file plus package ledger;
no existing helper, production, policy, default, deadline or observer changes.

## Existing coverage and precise gap

`tests/test_creative_runtime_authority_delay.py` exercises actual V5 composition,
then calls the original repository retained capture once and sleeps six real
seconds before returning. It proves `planning_authority_expired` before CAS and
no saved generation. It does not use the genuine V6 owner packet.

`tests/test_owner_review_runtime_api.py::test_owner_generation_original_receipt_and_atomic_rollback`
uses actual V6. Its `post-flush` fault calls real Session.flush, then replaces
repository.database_utc_now with candidate.valid_until. Its exact refusal is
`generation evidence expired`; this is evidence-expiry rollback, not expiration
of the original five-second IdentityFact. The other faults exercise original
session and receipt binding. Neither is a real authority delay. Source search
found no existing V6 six-second case at either requested boundary.

At repository.save_generation, the relevant order is: fresh source callback;
real retained capture; authority.final; evidence-time check; CAS; storage pair;
PlanVersion insert and first flush; dependency/request inserts and second flush;
evidence-time check; authority.final. Service owns the transaction and performs
its existing single final refresh before entering repository.save_generation.
All of this order must remain unchanged.

## Minimal two-case package: final publication flush only

Parent narrowed the first package to the uncovered post-flush authority boundary;
no new pre-CAS case or old V5 delay rerun is proposed. New file
`tests/test_owner_review_runtime_authority_delay.py` contains one test:

1. `test_v6_real_delay_after_final_flush_rolls_back[sqlite]`
2. `test_v6_real_delay_after_final_flush_rolls_back[postgres]`

Exact collected IDs are frozen before execution. Each invokes unchanged
`configured_owner_review`, actual HTTP input creation and one actual HTTP generate
with the original session and explicit genuine V6 policy/owner hypothesis. No
seeded plan/version/proof, fake ticket, repeated request or retry. Capture the
complete six-table planning snapshot after input creation and before generation.
Reuse financial_counts with its explicit zero-effect limitation.

The Session.flush wrapper recognizes the final publication flush from a pending
PlanRequestRow for this exact workspace/plan/operation generate/version1 AND
pending PlanDependencyRows for that same version. It invokes original flush once
before any delay. Using no_autoflush on the same transaction, assert persisted
version1, head1, nonempty dependencies including local_reporting_v3 and
local_creative_basis_v1, and the exact generate receipt. This distinguishes the
second/final flush from the earlier version-only insert. Require a strict genuine
V6 stored PlanVersion with owner proof, not a policy label alone. Record one reach
marker and sleep six real seconds once. No delay for another flush or plan.

The repository next runs its unchanged evidence-time check then authority.final
(current source line669). Require its exact authority-expired response. A minimal
original-once authority.final wrapper may record a Boolean that it was entered
AFTER the final-publication delay and rethrow the same original exception; no
arguments, principal/fact references, timestamps or secrets are retained. Before
the marker every call simply delegates. One marked invocation must raise exactly
HTTP409/planning_authority_expired. This proves the intended original final guard,
not an earlier unrelated refusal. The wrapper never changes or catches-successfully
the original result, computes no alternate predicate and does not refresh facts.

Neither test patches authority.refresh, IdentityFact, monotonic/time,
database_utc_now, provider callbacks, session expiry, or any evidence validity.
The one fact handed to save_generation is the unchanged fact created by the
existing service refresh; no replacement/renewal operation is introduced.
No profiler/general observer is attached. The original outer transaction must
roll back the already flushed CAS/version/dependencies/generate receipt.

## Exact outcomes and rollback evidence

Require HTTP409 and detail exactly `planning_authority_expired`, one deliberate
sleep/reach and the marked original final authority refusal, genuine V6 owner packet at the seam, and exact before/after planning
snapshot equality (head, input, versions, dependencies, events, request receipts).
Also explicitly assert head(input1,version0), no PlanVersion/PlanDependency and no
generate receipt. Existing input and original catalog links remain unchanged.
Add exact scoped snapshots of CatalogReceiptRow/CatalogReceiptSelectionRow/
InputCatalogReceiptRow and selected/range/presence rows so full retained source
and original admission graph preservation is explicit, not implied by plan rows.
All six financial counts remain their initial zero values; do not claim nonempty
financial liability preservation. Provider/native call counts are recorded after
fixture acquisition and must stay unchanged during generation; local owned reads
remain real. No extra HTTP current read is required after the refusal.

Failure at an earlier guard, evidence expiration, wrong detail, missed hook,
extra sleep, altered graph, or unexpected provider call stops the cohort and is
preserved with unrun nodes. No test catches and retries such an outcome.

## Qualification and limits

After source review and whole Ruff/configured no-path mypy, collect the exact two
nodes and prepare source/diff/base hashes, fresh per-node output paths, resource
floors and sanitized local both-DB environment. Parent authorizes execution only
then, separate processes in the above fixed order, PostgreSQL only after exact SQLite pass, stopping on first
failure. Preserve original exit before XML interpretation, log/XML and source
hashes; no old V5 or full V6 suite rerun is needed for this new-test-only package.

These are deliberate negative acceptance cases demonstrating enforced authority
and atomic rollback at the V6 final-publication boundary. A pass is not performance margin,
ordinary-generation reliability, or historical R01/R02/R03 cause/closure evidence.
A naturally earlier failure remains useful evidence but does not qualify the
intended delayed boundary. No retention or public API contract changes are involved.

Source-only narrowing: parent prioritizes final publication flush over a duplicate
pre-CAS case. The original R03 predicate remains unknown; later diagnosed instances
have measured fact-age expiration. This new test does not reclassify those incidents.
