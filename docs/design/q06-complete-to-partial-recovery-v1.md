# Q06 Complete-To-Fresh-Partial Recovery

Design only against root `5b1c373`. No source edits, test execution, schema change,
V7, live access or authority change. TLS02's four passing cases remain preserved.
The referenced gap note is an evidence artifact, not a repository design file:
`/workspace/inlet-evidence/20261011/owner-planning-browser/q06-next-technical-gap.md`.

## Actual Existing Behavior And Gap

`acquired_owner_catalog` currently closes over a static MockHTTP payload:
A/B share budget2 with referenceCount2 (or3 for a partial-start fixture), C has
independent budget4/referenceCount1. Campaigns remain genuinely paginated; metadata
contains all three campaigns and their children. The two wrapper fixtures forward
only a static `partial` flag. Existing browser variants never change that evidence.

On Edit, saved owner entries already start historical/unready. `clearTargets()`
synchronously calls `invalidateChoices()`, which also marks any newly included
live entry unready without deleting it. Target refresh deliberately bypasses owner
readiness only while validating the form to acquire replacement targets; it does
not submit or repair owner inputs. Target/scenario changes revoke option generations.
Unavailable discovery returns an empty owner option list but does not clear retained
entries. `readIntents()` refuses those entries until explicit removal. Therefore
an Edit→partial-refresh case alone must not claim it proved live-ready→unready:
the entry was already unready at editor opening.

## Smallest Coherent Added Variant

Add `complete_to_partial` to the existing browser journey, yielding only two new
nodes (SQLite and PostgreSQL); preserve existing positive/partial driver branches.
Reuse the complete positive creation/generation/export path and original session.
Do not add a second application fixture or repeat existing cohorts.

1. Through actual UI, acquire complete targets, discover A/B, include the5USD daily
   hypothesis in the100USD allocation/900USD reserve alternative, save and generate
   immutable V1. Export and record V1 document digest/canonical payload. The original
   lost-response recovery is not a new acceptance target here; keep its existing
   positive-only behavior rather than expanding unrelated failure injection.
2. Open Edit. Assert the saved row is historical/unready. Explicitly remove it,
   read complete targets again, rebuild the alternative, rediscover and explicitly
   include a current complete owner hypothesis. Assert the visible Included Review
   state. This one extra complete read/discovery is necessary to establish a truly
   ready unsaved entry before testing invalidation; no intermediate input save.
3. Invoke a fixture-only one-way response-control checkpoint while the browser is
   idle. It changes the next actual Google MockHTTP budget response, not any owned
   catalog, receipt, stored proof, source generation, privacy revision or clock.
4. Click Read Targets, rebuild the alternative from the new catalog, then Discover.
   Observe a different catalog commitment with the same real account/generation and
   A/B owner relationship: native referenceCount3 but only two affected campaigns;
   metadata remains complete. Assert actual unavailable discovery, its fixed reason
   and recovery text, and no enabled inclusion control. The old included entry stays
   visible/unready and retains its original requested amount/selection commitments.
5. Check the existing explicit replacement-target acknowledgment before attempting
   Save, so neither missing acknowledgment nor incomplete alternative explains the
   refusal. Assert the owner-specific unready error, editor retained, zero `/inputs`
   POSTs and no new input/operation receipt/financial rows. A session GET is allowed.
6. Explicitly click Remove This Review, then Save with the unchanged revision CAS.
   Assert one successful `/inputs` POST containing explicit `google_daily_budget_intents:[]`,
   never omission or a silently replaced choice. Stored input revision increments
   exactly once; V1 remains the only generated version. No second generation needed.
7. Read V1/history/export again and compare its immutable document/canonical JSON
   and digest to the original. Freshness/reason envelope fields may truthfully change
   after input/source observations; do not require byte equality of such envelopes
   or claim the retained V1 evidence is current. Assert original complete membership
   and5USD hypothesis are still visible in the saved artifact, distinct from V2 inputs.

## Test-Only Response-Control Boundary

Add optional keyword-only `response_control: OwnerCatalogResponseControl | None = None`
to `acquired_owner_catalog`, `ready_inputs`, and `configured_owner_review` without
changing default flags, return tuples or public application interfaces. Controller
lives in the fixture module and has one bounded method `make_partial()` and a locked
read-only state; it supports only complete→partial, once. Combining an injected
controller with `partial=True` should explicitly refuse, avoiding ambiguous setup.

Inside the existing MockTransport wire function only, copy the campaign-budget
response rows for each request and apply the controller state to the exact shared
budget2 row's referenceCount (2→3). Leave independent budget4 and all campaign/
metadata/pagination payloads unchanged. Record a bounded test checkpoint/counter
showing the subsequent native budget response actually used3. The switch happens
between completed acquisitions, never mid-page-loop. No arbitrary row/proof editor.

Expose one fixture-only POST checkpoint in the existing TLS harness, available only
for this journey. Require the exact original session cookie, matching same-origin
Origin and CSRF token, a bounded fixed/empty body, and idle one-time state. Return
only `{ok:true}`; never return a prepared customer intent or proof. It performs no
DB write, provider acquisition or application service call. Do not add a production
route or observer taxonomy solely for this test checkpoint. Keep actual provider
call assertions: explicit target reads may add calls; discovery/save/history/export
must add none. Keep original session state/lifetime equality and no session POST.

## Ownership And Evidence

Browser lane owns the existing TLS Python/JS files and the narrow optional fixture
controller/join. Portal production files need no change based on this source review.
If the new transition exposes a real product failure, preserve its first failure
and report it before proposing a scoped repair; never weaken the stale-input guard.

Persist the two actual catalog/discovery snapshots, the pre-transition immutable V1
artifact/digest and post-transition historical artifact/digest separately from the
fixed route observer log. Use exact source/head/fixture hashes and fresh manifests,
sole runner, stop-on-first-failure, original exit/XML and resource floors. Requested
next node order: SQLite complete_to_partial, then PostgreSQL only after that result
and parent authorization. No tests are authorized by this document itself.

This proves safe customer recovery from changed native membership evidence. It does
not qualify daily-setting compatibility with the period ceiling, authorize native
edits, establish remaining spend, or satisfy the separate human usefulness gates.

## Independent Review Precision

Approved source contract before implementation. At the native-response transition,
capture the exact planning snapshot. Before allowing the later explicit-removal
input POST, verify that the rejected Save produced zero input POSTs and left that
snapshot unchanged, in addition to the owner-specific UI error. This test-only
read-only checkpoint substantiates intermediate no-effects; final counts alone do
not. Require the controller's counter to show that a real subsequent shared-budget
response used referenceCount3. No fixture may mutate stored proof or receipt rows.

## Execution Sequencing Amendment

Root approved one two-node sequential qualification, replacing the manual
inter-phase authorization sentence above. PostgreSQL may start automatically only
after SQLite exits zero and its XML records exactly the intended single passing
case with no failures, errors or skips. Source/head/WIP, resource floors, sole
pytest and fresh output checks run before each case. Any failure stops the sequence
and preserves the unrun remainder; no retries. This changes internal sequencing
only, not scope or customer authority. The exact manifest still requires review
and authorization before either case runs.
