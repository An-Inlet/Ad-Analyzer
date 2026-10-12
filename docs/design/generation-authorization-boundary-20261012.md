# Generation Authorization Boundary Review — 2026-10-12

Status: architectural assessment; no authority semantics changed. Feature expansion
is paused. The repeatable five-second generation risk remains open under
INLET-REL-20261012-01. The HTTP packet's original55passes/1failure/2unrun and original
memory interruption remain immutable; independent remaining tests are separate evidence.

## Actual Contract And Existing Two Stages

`customers/access.py:require_customer` checks the presented session and identity
provider on every request. `require_customer_mutation` checks HTTPS/origin/CSRF.
`planning_documents/authority.py:refresh` checks issuer and calls
`provider.check_active(subject, authenticated_at)` outside the SQL transaction,
then creates an IdentityFact bound to original user/issuer/subject/session/auth-time.
This is a real provider revalidation, not a timestamp reset. `authority.lock` calls
`guard_customer_mutation`, locking workspace, user, session, membership in canonical
order and refreshing rows; original identity equality, active user/session, owner
membership and five-second fact age remain mandatory. `authority.final` checks the
same original identity/session, revocation, absolute session expiry and fact age.

`PlanningDocumentService._generate` already uses two stages: authorized ticket and
collection, then composition and `prepare_generation_checks` BEFORE its final
provider refresh. Collection authorization cannot grant publication. The private
prepared token seals only pure graph checks; it is one-use/root-transaction-bound,
not current-source authority. `repository.save_generation` still rereads plan/head,
inputs/parent, paid entitlement, confirmed goal, accounts and privacy; reconstructs
selected reporting/traffic twice around creative-media checks; validates original
owner receipts and captures retained current witnesses; applies CAS, inserts version,
dependencies and request receipt; flushes and checks evidence expiry and authority.
All writes roll back on exception. No provider IO is allowed under final SQL locks.

Consequently, merely adding another refresh at the start repeats an existing boundary.
Refreshing after SQL reads would transfer old source conclusions into new authority;
refreshing under locks violates the no-provider-IO contract. Neither is an accepted fix.
Also, service currently constructs VersionResult AFTER repository post_flush final and
BEFORE transaction exit. That deterministic validation is outside the last checked
interval. A redesigned final acceptance guard must follow response preparation as
well; do not describe the existing post_flush check as adjacent to commit.

## Proposed Architectural Boundary

1. Acquire real read/preparation authority; capture a complete, bounded owned evidence
   graph and dependency inventory. Release its SQL transaction. Preparation must not
   publish or extend original evidence TTLs. Copy and validate original candidate,
   complete ticket (including private session pins), evidence and byte representation;
   construct canonical stored bytes, dependency payloads and response outside the
   publication-authority window. Seal immutable values, reject unsupported graphs and
   never expose a public `already_validated` switch.
2. Revalidate the ORIGINAL provider identity outside SQL. Acquire canonical local
   workspace/user/session/membership locks and refresh original identity, revocation,
   expiry, role and ownership. If lock waiting consumes five seconds, refuse; do not
   renew the fact or retry automatically. Recheck paid/goal/consent/privacy/account
   currentness under locks. Preparation fact/time never substitutes for this snapshot.
3. Compare the complete current dependency inventory to preparation under the same
   publication transaction. Include full contents OR trustworthy writer-maintained
   revisions, exact query membership/absence, source generation, private grant/source
   rotation, scope, original receipts, selected heads/capture/completion/manifest,
   traffic sidecars and gaps, campaign maps/range jobs, catalog links, commerce/store/
   goal progress and media metadata. Recheck changing clock predicates separately.
   Preserve two media-bracketing source passes unless a reviewed lock/revision proof
   makes every intervening mutation impossible. A hash alone is not an ownership check.
4. Bind original plan/input/version and prepared bytes to CAS. Insert version,
   dependencies and receipt atomically, validate prepared graph identity after every
   permitted callback/flush, then check evidence and original snapshot expiry after
   response preparation and immediately before transaction commit is invoked. No work
   that can change acceptance may follow this guard. Inventory ORM before_commit,
   transaction and flush callbacks as well; their work must be prohibited, covered by
   final revalidation, or included in the proven acceptance boundary. A commit that blocks cannot be
   given a literal wall-clock completion guarantee by Python checks alone; if that is
   required, database-enforced deadline/lock semantics need explicit separate design.

## Why A Shortcut Is Incompatible Today

Current source reconstruction validates complete query results and their absences;
`selected_plan_local.recheck_selected_sources` reconstructs raw selected graphs,
`selected_paired_local` compares traffic pins/gaps, and retained owner capture reloads
original receipts on both sides of creative retained capture. These provide stronger
semantics than comparing one workspace/privacy revision. Privacy epoch is not a
proven universal mutation epoch for all these dependencies. The current prepared
checks explicitly prohibit carrying SQL currentness forward. No closed all-writer
revision/lock inventory has yet been established. SQLAlchemy root-transaction identity
alone also does not prove SQLite physical snapshot/write-lock semantics.

Therefore moving these reads before fresh authorization and keeping only existing
small identifiers/digests in the final transaction is NOT compatible with today's
contract. This is a missing architectural proof, not a credential or owner-permission
blocker. Build the dependency/writer inventory before such implementation; do not
claim a passing retry proves reliability or that another micro-optimization fixes it.

## Bounded Alternative And Next Proof

Keep complete current rereads while establishing the boundary. Capture fixed-label
failure-path timings (including final_sources, retained capture, storage, nested lock
and final authority ages) on one separately frozen diagnostic invocation. No sensitive
payloads/SQL text, no clock changes and no acceptance credit for diagnostic success.
Use the evidence to choose one bounded dependency family for an explicit raw-row
snapshot/validation split, with full query membership plus writer fencing and current
reconstruction parity. The final transaction still performs every current read; only
pure parsing/projection of identical sealed raw data moves before fresh authority.
If measuring shows mandatory current IO itself exceeds the window, stop local speedup
work and complete a whole dependency-revision/read-set design rather than weakening
freshness. Batch within a pass only if it preserves exact locks/membership/failures;
no cross-pass currentness cache. No automatic retries on expired authorization.

## Required Security And Reliability Qualification

- Provider revocation during preparation, changed issuer/subject/auth-time, rotated or
  revoked session and owner membership removal while final locks are waiting.
- Consent/entitlement/account ownership/source generation/credential revision/privacy
  erasure changes before fresh auth and after lock acquisition; no stale prepared use.
- Insert/delete/query-membership changes, selected/traffic/commerce gaps and media
  changes on BOTH sides of existing callbacks; response/candidate/byte mutation.
- Same-key replay and different-key contention with a real winner/loser; input/version
  head changes; SQLAlchemy AND physical SQLite/PostgreSQL transaction guarantees.
- Real five-second waiter/pre-CAS/post-insert/response-preparation expiry, evidence TTL
  expiry, rollback of version/head/dependencies/receipt and zero durable publication.
- Byte-identical legacy storage/export, original error precedence, single-use token
  cleanup, no nested/foreign transaction acceptance or provider IO under locks.

Independent review agrees with the two-stage direction and rejects shortcut refreshes;
implementation approval depends on the complete inventory and exact finite test plan.
No policy change, ad authority, deployment or live-service access is implied.


## Concrete Membership Dependency Found By Independent Review

`selected_traffic_reader._traffic_for_selected` selects up to two RangeReceiptRow
request IDs by workspace/account/completion. Zero yields a known gap, one reconstructs
traffic provenance, two refuse. `range_receipts.store_range_receipt` inserts under
workspace/account locks. The range receipt triggers advance privacy on DELETE, not
INSERT, and completion ID is not unique. Existing full rereads detect membership;
privacy epoch plus previously seen rows cannot detect a receipt inserted between
preparation and final lock acquisition. Normal writer locking helps once publication
has acquired the lock; it does not eliminate the need to compare the intervening state.
`manifest()` also joins DailyMetric with Campaign: changes to campaign account/platform
membership affect returned metric sets. A metrics-only snapshot is incomplete.
These are requirements for the proposed boundary, not current-validation vulnerabilities
or explanations of the observed authorization expiry.

The next architecture package is a dependency inventory plus both-database contract
tests, with NO optimization: enumerate queries, absences/cardinality, transitive job/
completion/presence/sidecar dependencies; map all writers/triggers/cascades, lock order
and revision changes; test insertion/deletion/membership mutations; explicitly mark
unproven coverage. Preserve production rereads until the inventory closes. This replaces
isolated speedup work and feature expansion. No owner policy decision is needed yet.

## Diagnostic And Independent Remaining Cases

The two independent legacy PostgreSQL API/browser cases passed separately in
`q13-http-independent-api02` (57.307467s process) and
`q13-http-independent-browser02` (64.380726s). Each verified unchanged 1,909 code/test
hashes, valid XML, no interruption or surviving children. Their exact manifests and
retained artifacts are in qualified-summary.json. The original HTTP packet remains
55pass/1fail/2unrun historically; combined independent coverage is57passes plus the
unresolved failed case. Do not erase the failure or award a completed-package pass.
An earlier independent preparation stopped before tests because documentation diff
metadata was stale; successor manifests bind the corrected metadata without code edits.

One reviewed external failure-safe observer ran on the failed browser workflow in
`generation-boundary-diagnostic01`. It recorded365frames, no truncation/observer error/
restoration failure, original pytest exit0 and unchanged source. Generation took
9.066308s, pure preparation0.730648s, final save2.568319s; within save, final_sources
1.377696s, retained capture0.950314s and storage serialization0.082131s. Maximum sampled
final-authority age was2.568705s. These are nested/nonadditive wall intervals; age brackets
are not original predicate samples. Eleven refresh frames include reader authorities;
they do not indicate renewal within final save. No expiry occurred in this diagnostic.

A passing diagnostic does NOT identify the earlier expiry's phase/cause, prove capacity,
resolve INLET-REL-20261012-01 or qualify V6/V7. Failure-path timings were installed before
the run, but cannot retroactively recover the original failing invocation. No second
diagnostic or unchanged acceptance retry follows. The architectural inventory remains
required regardless of this pass. No product source, authority rule or time limit changed.
