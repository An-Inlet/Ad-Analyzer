# Candidate To Exact Review Orchestration

Status: implemented offline bridge, based on PR194
1aed8810b5fe040aec0ebfc0adfde90e113cc188. Scope is original-session-bound,
non-emitting automatic decision/review preparation, plus a runnable offline
assembly which uses the existing explicit customer approval boundary.

## What Exists And What Does Not

Existing code supports current owned catalogs, exact native-owner selection,
versioned candidate work, bounded candidate decisions, exact manual initial/repeat
optimization review, customer approval, durable claim, actual Google/Meta/TikTok
HTTP adapters, unknown reconciliation, shared reservations and terminal settlement.
The selected candidate does not currently feed an execution review. There is no
single runnable composition of these stages and no durable candidate-to-review
provenance or downstream candidate-retraction guard. These are ordinary missing
implementation, not missing credentials.

`optimization.create_run` and `locked_run` explicitly require
`ProviderExecutionApproval`. That record represents exact customer approval.
Calling `approve_optimization` inside a worker would forge the human action and
must not be used to disguise automatic execution. Existing mandate policy
expresses allowed purpose/target set/caps, but its present executor has no separate
mandate-derived automatic decision admission/audit path.

Genuine mature directional feedback, configured numeric decision policy, native
bounded exposure and original terminal/transition proof remain unqualified or
unimplemented. Those are distinct from the orchestration code. An offline
contract scenario can exercise the real HTTP serialization and coordinator with
explicitly labelled injected evidence; it cannot qualify production sources.

## Narrow Next Package: Automatic Review Preparation

A server-only bridge consumes one current owned CandidateResult reference, not
an action/evidence dictionary from a browser. It automatically prepares the exact
initial or repeat review under the original session. It never approves the review,
creates a run, claims work, dispatches or releases a reservation.

Input:
`CandidateReviewIntent(result_id, expected_decision_digest)`.
Workspace and original principal come from the authenticated context. Runtime
bindings and source proof readers remain server-only. No production factory is
installed by this package.

`prepare_candidate_review(db, principal, wid, intent, runtime)`:

1. Reconstruct/revalidate the original job session (not merely another owner with
   a new session), candidate result/digests, v2 selection provenance, current
   goal/mandate/policy/source/privacy/receipt lineage and expiry. Only `suggested`
   with a typed exact action can proceed. Re-evaluate cumulative positive/action
   allowance; never treat the candidate as financial qualification.
2. Resolve the current held native-owner reservation from DB, under existing
   workspace/ledger ordering. No caller-chosen predecessor. No hold means initial
   review; exactly one same-ledger eligible held owner means repeat review using
   the existing complete ancestry/closure/transition protocol. Unknown, unrelated,
   cross-period, mixed-currency or otherwise unsupported predecessors block.
3. Execute existing server financial qualification and fresh native read ports.
   Bind final plan's before-state digest, action, account/target/owner, full target
   set and mandate exactly to the candidate. A changed native state is not silently
   reinterpreted: it requires new candidate generation.
4. Revalidate original session and all candidate dependencies after I/O/locks,
   then persist the review and minimal provenance atomically. An internally
   committed review must not escape without the required provenance guard.
5. Return `review_required` with the exact review and plan digests, or a bounded
   blocked reason. No customer approval record is manufactured.

## Durable Provenance Boundary

An explicit scoped link table avoids changing every existing reviewed plan
hash: `optimization_candidate_reviews`, unique `(workspace_id, candidate_digest,
review_digest)` and unique `(review_id, workspace_id)`. Bind exact review FK,
original actor, original session digest (internal only), environment, candidate
result ID and original input commitment as non-authorizing references, candidate/input/selection-manifest/
policy/evidence/source commitments, review/plan digest, created_at. Current/retracted state is derived from the nullable candidate FK,
not a separate mutable state field. Store only bounded IDs/digests, no raw measurement or names.

Candidate deletion must retract the link and block all *future* approval/run/claim/
emission that relies on this review. It must not delete the immutable financial
review/request/receipt, undo observed effects, change a fence or release a hold.
A separate nullable `(candidate_result_id, candidate_workspace_id)` composite FK
with `ON DELETE SET NULL`, alongside nonnullable owning `workspace_id` and a check
requiring the optional candidate workspace to match it, avoids nulling the owning
workspace during deletion. Current link checks can make
missing candidate state authoritative invalidation without rewriting history.
Receipt and commerce/privacy hooks already erase candidates; closure must also
explicitly retract links. Historical reconcile/settlement reads retain minimal
review/request lineage and do not need the erased candidate body. Export and
lifecycle classification must be explicit; session digest stays internal.

The normal manual review path remains byte-for-byte compatible. A bounded helper
used by optimization checked-review/locked-run validates link-based reviews with
the original session and current candidate; reviews without this provenance retain
manual semantics. The link and review must be inserted in one transaction, so
there is no temporary unguarded review. Refactor shared plan-building/persistence
as needed instead of adding a post-commit linking workaround. Migration0068 follows0062; final integration merge is owned by the parent.

## Runnable Offline Assembly

Implement an explicit offline runner and integration fixture which binds:
current customer identity/session → confirmed goal and consented existing-campaign
mandate → actual mocked provider catalog → selected v2 candidate job → registered
controlled contract evidence and explicit numeric policy → immutable candidate
result → bridge-prepared exact review. Default execution stops at `review_required`.

A separate scripted **customer interaction in the test harness**, not the worker,
then invokes the existing exact customer approval API and step intent, exercising
actual persistent claim → real adapter through MockTransport → independent
readback → receipt projection → unknown/reconciliation → qualified contract
settlement. For a repeat case, retain the original hold until the existing
complete original-request closure/transition reader proves the controlled
scenario, then transfer atomically without resetting cumulative accounting.

This is an executable offline journey, not another unused runtime port. The
runner must refuse non-loopback/mock transport or live environment and never
load provider secrets. Production bridge functions themselves should remain
ordinary provider-independent code, not permanently fixture-only APIs.

Acceptance: all three providers, exact candidate/plan binding, original session
logout/expiry/role loss during qualification/lock waits, source correction/privacy/
receipt supersession after review and after claim, atomic persistence failure,
foreign result/predecessor, partial/unknown repeat history, duplicate review/run,
late same-fence evidence and unchanged ledger/account-set/currency constraints.
Assert worker created zero approvals and zero attempts before explicit harness
customer action. Validate export and historical settlement after candidate erasure.

## Later Automatic Execution Is A Separate Code Package

Within an approved mandate, session-bound automatic existing-campaign execution
is compatible with the owner's stated product scope; it does not inherently need
a new logout-independent delegation. Its missing code is a distinct admission
record tagged `mandate_automatic_decision`, current registered decision-policy
version/action permissions, exact candidate/review/mandate/session binding and an
explicit executor authority union. It must never reuse a human-approval record or
extend to new campaigns/creative. Root can freeze that contract separately once
the provenance bridge exists. No emitting implementation is proposed in this
package while native financial qualification remains unavailable.

The consequential owner decision is **authority surviving logout/session expiry**.
Minimal recommendation: do not enable it initially. Keep session-bound automation;
later offer an explicit owner-consented, expiring and revocable existing-campaign
worker grant with exact scope/action/currency/mandate limits. Existing approvals
must never be reinterpreted as that grant. This decision does not block candidate
assembly, review preparation, testing, or building a disabled grant validator.

Production release additionally needs actual financial/terminal sources, genuine
mature learning and approved numeric policies, periodic fair orchestration,
attention/recovery surfaces and full live qualification. None are described as
credentials-only and no draft percentage can expand the total spending limit.

## Implemented Boundary And Runnable Composition

`review_contracts.py` freezes CandidateReviewIntent, CandidateReviewPrepared,
CandidateReviewGuard and CandidateReviewWriter. `review_bridge.py` consumes only
a current selected candidate and server-resolves any held predecessor. It composes
the existing initial/repeat coordinators without calling approval, run, claim or
transport mutation methods. Runtime defaults remain None.

Migration0068 follows0062. `optimization_candidate_reviews` stores protected
minimal commitments; a separate nullable candidate workspace/result composite FK
is SET NULL on erasure. A check disallows half-null references. The nonnullable
owning workspace stays intact. The existing review gains a default-false deferred
`candidate_provenance_required` scalar marker, so a missing link cannot downgrade
to historical manual semantics. Existing review JSON/digests remain unchanged.
Downgrade refuses any marked review or provenance link. The marker is deferred
with eager default loading disabled to keep explicitly historical producer
fixtures usable; their new forward guard is test-only stubbed when0068 is absent.
There is no runtime missing-table fallback.

The writer executes after review flush but before commit, validates exact candidate
state/action/mandate and remaining cumulative allowance, inserts provenance and
runs its fresh guard. Any failure rolls back both. Read validation uses
`read_result(..., erase_invalid=False)` so source invalidation cannot accidentally
commit a half-built financial review. Normal candidate reads retain their prior
transactional erasure behavior.

Forward guards check original-session identity, candidate/source/privacy/policy
currency, immutable commitments and expiry at review/approval/run/claim, retained
reservation transfer and final emission boundaries. Financial qualification time
is resampled after potentially blocking candidate guards. Candidate deletion
invalidates the nullable FK; workspace closure also removes candidate jobs.
Historical evidence_lock/reconciliation/settlement deliberately do not require a
surviving candidate. No original request/fence or financial history is erased.

Run the concrete offline assembly with:

```
pytest -o addopts='' -q tests/test_candidate_review_bridge.py
```

The parametrized fixture uses actual Google/Meta/TikTok transports with
`httpx.MockTransport`, real owned catalogs, current sessions, selected v2 jobs,
explicit contract-scenario evidence and persistent review/approval/claim/receipt
records. The worker stops at `review_required`; a visibly separate harness
customer action supplies exact approval before dispatch. The same suite exercises
controlled unknown acknowledgement and later same-fence observation without replay,
retained-owner repeat transfer, candidate erasure and qualified contract settlement.
It requires no provider credentials and supplies no native production proof.
Set the documented disposable PostgreSQL test variables to run both databases;
otherwise PostgreSQL cases skip. No live factory or scheduled dispatch is enabled.
