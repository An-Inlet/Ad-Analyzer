# Frozen W1 Failure Closure Ledger

Cutoff: successor `d85db66`. This is docs-only reconciliation of the one terminal
aggregate, not a rerun or a claim that the successor is green.

## Immutable Baseline

Frozen `6a3b0f16f9ebc9c0a80dbab60140c0b8f9324f46` finished 9 October at
02:14:44 UTC, exit 1: **6,581 top-level cases, 5,168 passed, 1,330 failed,
83 skipped, zero errors**. The three historical wrapper cases separately exercised
249 children (246 passed, three expected skips); do not add child counts to parent
counts. Pytest duration was 8,597.96s; launcher wall duration was 8,760.129814s.

Aggregate evidence: `/workspace/inlet-evidence/20261008/w1-aggregate/aggregate.xml`,
SHA256 `e3263f5e2bca0d484b4657d6672a32dfdc44539ee1cbed8257bf1a7187488037`.
Terminal launcher/result, summaries and raw log remain alongside it.

The exhaustive external classification in
`/workspace/inlet-evidence/20261009/w1-failure-classification/` retains all
1,330 failures, 105 modules and 17 exact signature clusters. Its `failed-nodes.json`,
`signatures.json`, `guard-entry-groups.json`, `modules.json`, `summary.json` and
`classify.py` remain unchanged. Classification is not a production-defect finding:
setup failures can mask current behavior and further defects.

## Direct Successor Coverage By Frozen Identity

A separate `successor-coverage-142.json` in that classification directory joins
original failed XML classname/name pairs to actual passing successor JUnit records.
It preserves each original traceback hash/category and all 1,330 rows. Frozen node
strings are matched one-to-one to the genuine collect-only stdout (see limitation
below); no parameter or class name is reconstructed by splitting dotted XML names.
These keys are evidence lookup identifiers, not execution-selection authority.

| Reviewed repair | Frozen failures with direct passing successor evidence | Exact evidence |
| --- | ---: | --- |
| Account diagnostics source-only fixture, `0ecd0d7` | 66 | `20261008/diagnostic-read-fixture/qualified.xml`; full module 66 passed, 77.80s |
| Authentic historical mandate setup with current native readers, `a0bc585` | 72 | `20261009/native-diagnostic-investigation/module.xml`; full module 78 passed, 499.84s |
| Current portal copy and explicit route inventory | 4 | `20261009/w1-current-shell-contract/focused.xml`; full two-module cohort 20 passed, 20.578s |

All artifact paths in the table are relative to `/workspace/inlet-evidence/`.
The coverage overlay records exact artifact paths and SHA256 values. It verifies
that no frozen failed identity matches more than one of these successor cohorts.
**66 + 72 + 4 = 142 directly covered frozen failures; 1,330 − 142 = 1,188 remain
without this direct successor evidence.** Do not sum 66 + 78 + 20 as failure closure:
those cohorts include originally passing or additional assertions. The original
aggregate continues to have all 1,330 failures.

## Remaining Classification, Not Inferred Disposition

| Classification still without direct coverage | Nodes |
| --- | ---: |
| Shared legacy approval seed blocks intended assertions | 1,109 |
| Old-schema privacy/trigger fixture mismatch | 6 |
| Removed control or retained DOM contract | 9 |
| Retired pilot execution bridge expectation | 4 |
| Direct retained execution or validation path denied | 29 |
| Native planning fixture requests execution consent | 10 |
| Current restore fixture blocked | 21 |
| **Total** | **1,188** |

The 1,307 terminal advertising-boundary exceptions include setup-only and direct
execution failures; that count is not a classification of every test body as
retired. Each bounded repair must preserve current read/privacy/session assertions
or authentic retained execution coverage as appropriate. Do not globally enable
writes, remove guards, or skip modules based on shared fixture ancestry. Migration,
DOM, pilot and downstream masked behavior require their own concrete traces and
reviewed acceptance. Comprehensive quality cases and six human expert gates remain
unfulfilled; no Full or release qualification is credited here.

## Offline Partition Evidence Status

The original aggregate is terminal; no test suite was restarted. Two authorized
collect-only attempts used only the successor scripts directory on PYTHONPATH and
left frozen source clean. First exited 4 before collection because installed pytest
normalizes tracked `--strict-markers`; reviewed repair `7b15289` addressed this.
Its 56 focused tests, whole Ruff/mypy and independent review passed.

Second attempt collected 6,581 stdout node lines, but the manifest hook exited 4
on its reviewed 16KiB per-node bound. Two original campaign-media parameter IDs are
8,388,678 and 8,388,680 bytes; one Omnisend parameter ID is 17,085 bytes. There are
no duplicate XML identities among those 6,581 stdout lines. This does not make the
failed attempt a successful manifest. Raw `partition-collection.log/exit` and
`partition-collection-second.log/exit` are preserved in the aggregate directory.
No collection manifest, timing envelope or N3 candidate was fabricated. Oversized
identity representation/bounds require a reviewed follow-up before another attempt.
No workflow, shard execution, CI cap, database or application behavior changed.

The failure coverage overlay uses the exact observed stdout node lines only as
lookup corroboration and explicitly records exit 4. It is not the partition tool's
accepted provenance output. The CI 90-minute step/120-minute job gap remains open;
failed-path timings cannot predict fully passing runtime or resource costs.

## Reviewed Successor Update — 9 October

At integration `099e9a5`, three further independently reviewed packages have exact
passing successor XML matches against frozen failed identities:

| Package | Newly covered frozen failures | Actual focused result |
| --- | ---: | --- |
| SQLite presence dependency around original migration, `57af351` | 1 | Full module 3 passed, 1 existing PostgreSQL-only SQLite skip, 5.253s |
| Current TikTok source-only discovery, `ae470f1` | 72 | Both databases 72 passed, zero skips, 59.450s; separate pure compatibility 71 passed |
| Explicit per-function retained MockHTTP engines, `20a44eb` | 29 | 29 retained cases plus 86 unchanged current boundaries: 115 passed, zero skips, 3.637s |

`successor-coverage-244.json` alongside the original classification extends the
142-node overlay without changing it. It matches actual XML classname/name pairs,
retains all original trace hashes, checks no overlap, and hashes all three added
raw XML files. **244 original failures now have direct reviewed passing evidence;
1,086 remain without direct coverage.** Full module counts include originally
passing cases and are not added as failure closure. Original W1 is still failed.

Root independently reviewed SQLite and TikTok; `initial_start` independently
reviewed the transport classification and AST equality. SQLite review restored
the exact PostgreSQL intermediate full-column assertion and added all four
restored trigger checks. Transport edits are only sixteen decorators across eight
pure engine functions, with all original bodies/parameters/assertions unchanged.
Current durable/customer cases in their mixed modules remain separate.

The compact V2 evidence tool passed70 focused regressions and independent review.
Third genuine frozen collection succeeded with6,581 nodes and unchanged clean6a;
N3/N2 offline candidates prove disjoint/exhaustive membership and retain original
exit1 outcomes. See `inlet-w1-partition-actual-evidence-20261009.md` for exact
commands/hashes. No tests, shards or hosted workflows executed for those candidates;
capacity/pass qualification remain false. Earlier failed collection attempts stay
preserved. The initial142 overlay's lookup provenance remains accurately exit4;
the later successful collection is a separate artifact, not a rewritten history.

Next bounded work: genuine pinned commerce producer at actual sibling0051/0053
heads; reviewed source-only Meta budget reads and actual planning-consent setup;
per-function classification of remaining legacy-seed families. No aggregate rerun
is justified while these known setup failures remain. Earlier138 repaired account
and native-read cases will be reconsidered at the corrected integration if shared
fixture changes affect them. No global seed patch, blanket skip or guard relaxation.

Integrated successor whole Ruff, bare mypy (1128 source files), standalone
collection-plugin mypy (1 source file), and diff checks passed at `099e9a5`.
No integrated pytest aggregate was rerun. The package XML results above were
executed on their recorded source branches; independent source review found no
cross-package edit conflict. This distinction remains a limitation until the
bounded corrected integration is qualified after regression closure.

### Additional Current Read And Migration Repairs

At `2847724`, independently reviewed commerce `e4749fd`, Meta reads `dfe337a`,
and owned credential contexts `6f26d48` add1+8+32 exact frozen failed identities.
External `successor-coverage-285.json` preserves previous overlays and records
all raw successor XML hashes. **285 covered; 1,045 remain.**

Commerce:5 passed/no skips61.351s including four existing shared producer/lifecycle
cases; only one frozen commerce failure credited. Parent real0051/0053 sibling
head set, current downgrade/refusal/retention assertions preserved; child runs
verified historical producer. Initial incorrect singleton-head probe retained.
Meta:8 passed/no skips13.075s; actual source/goal/history, original45m budget,
GET/closure/revocation/generation/goal checks retained. Source-only setup observes
already-fresh commerce and seeds the same native mock budget without prior writes.
Credential module:41 passed/no skips26.158s =32 repaired+9 existing pure cases;
original vault/session/billing/source/expiry/cleanup assertions unchanged. Root
reviewed commerce/Meta; rule_review independently reviewed credential fixture.
Whole package Ruff/mypy/diff passed; aggregate was not rerun.

Active:147 explicitly classified retained-engine cases;41 separately classified
accounting/dispatch cases; three further migration profiles; current native-preview
API plus authentic retained V1 route coverage. Migration producer at0079 exposed
missing newer0085 privacy tables even under2155; a closed earlier authentic source
is being qualified, without no-op hooks or schema fabrication. Native preview
requires a separately documented V1/V2 routing split rather than claiming the old
runtime predicate still runs through current API. No passing evidence credited
for these active packages yet.

### Review Closure At 5aba7e0

Exact overlay `successor-coverage-496.json` now covers496 original identities;
834 remain. **486 are direct current-successor passes;10 are explicitly authentic
pinned V1 passes with separately qualified current V2 API equivalence.** The latter
are not mislabeled current passes of unchanged V1 routing. Overlay records both
raw XML hashes and the changed environment/profile predicate limitation.

Since285: retained-engine147 (`41d1e80`,233pass1existing skip399.472s), retained
accounting/dispatch41 (`da2c8cd`,130pass4existing skips76.955s), migration3 (`80c6969`,
9pass77.578s including one previously credited commerce case), current media10
(`1c0a8aa`,14pass12.643s), native planning10 (`33bb66e`, authentic pinned10pass21.19s
plus current10+consent16=26pass91.583s). All independently reviewed; exact original
XML identity intersections, not cohort totals, determine closure. Earlier overlays
remain unchanged. Initial import-cycle, old-pin privacy and closed-count failures
remain recorded in their package ledgers.

Successor historical collection now has four wrappers/259 child nodes. The three
original manifests remain byte-identical. Original frozen W1 and its three-wrapper/
249-child candidate are still bound to original source/tool and were not rewritten.
Final partition+mapping71pass5.920s qualified the additive successor contract.

Integrated whole Ruff, bare mypy1134, standalone plugin mypy1, and diff checks passed
at5aba7e0. No current aggregate or original three historical batches were rerun.
Next:42 current TikTok linked reads;95 narrowly classified retained-engine cases;
remaining21 campaign review with genuine source records; default synthetic restore
CLI repair with current verification (not a test-only replacement hiding broken
CLI); separately designed configured API historical/current split. No product
expansion or owner action is needed for these routine regression repairs.

### Linked Read Closure

Reviewed8c027bf→854c2c5 adds42 original TikTok linked-read identities. Correct
isolated cohort47pass/no skips59.421s includes5 existing pure cases. Only explicit
planning markers and zero-authority fixture imports/decorators changed; source-only
setup was already reviewed. Overlay538 records exact XML matches/hash:528 current
passes plus10 authentic historical/current-equivalence cases;792 remain.

An initial wrong-checkout focused invocation was interrupted after25 passes (exit2)
and is NONqualification. Its exact test-only additions were restored from root;
correct isolated worktree was then qualified. The interrupted log/XML are retained.
No aggregate database or production files changed. Root independently reviewed the
final source and correct47-case result before integration.

### Retained Engine And Current Campaign Reviews

Root independently reviewed and integrated `1ec0e03`→`9314596` and
`4dec962`→`3df12ee`. The first preserves every original statement in17 functions
while explicitly qualifying95 retained-engine identities;181pass7existing SQLite
row-lock skips includes86 overlapping current-boundary passes. The second uses
genuine scalar-only source records then current offline campaign reviews:
41pass1existing skip includes21 new original failures and10 already credited
media cases. Final affected both-DB Google/Meta checks4pass after review tightening.
Whole Ruff/mypy/diff passed in each isolated package before commit.

Immutable exact overlay `successor-coverage-654.json` records644 direct successor
passes plus10 explicit historical/current-equivalence cases;676 remain. The
campaign overlap is counted once. Original failed aggregate and prior overlays
remain unchanged. Current candidate-reader29 qualification and actual default
restore CLI closure continue; separately reviewed configured API split proceeds
with genuine current owned reads and a new34-node historical supplement. No
aggregate rerun, hosted retry, provider write or deployment occurred.

### Actual Default Restore CLI

Independently reviewed `cd5682a`→`8f1937a` repairs the actual default synthetic
restore producer, not a patched test-only native path. Current verification retains
original rows/receipts/holds/privacy/financial integrity while three forward checks
now require immutable planning-write denial and unchanged counts. Native local
PostgreSQL dump/restore, cleanup, actual main and strict bootstrap guards qualified.
Initial combined34pass1fail9errors remains unsuccessful; corrected18 ordinary
bothDB plus guard19pass141.936s and final realCLI+strictguard2pass96.550s close it.
Whole final Ruff/mypy1133/diff passed. Exact overlay675 unions successful original
identities across those raw XMLs:21 added,655 remaining. It does not claim the
initial command passed, historical unknown-specific routing unchanged, or cloud DR.

### Current Candidate And Report Request Foundation

Reviewed `8a43e87`→`d63f9ba` and `d667326`→`5d0a90d` add29+16 original
failures. Both use closed genuine pinned source producers, strict scalar output,
validated disposable loopback schemas and current real consumers. Candidate:
115pass3existing skips289.392s includes86 overlapping current-boundary passes;
final all-provider/bothDB6pass69.624s after stronger URL/freshness guards. Reported:
27pass182.348s includes11 existing compatibility cases; final service/API bothDB
4pass28.539s after guards. Original source60day session preserved; no TTL expansion.
Actual original reported mock POSTcount1 is measured, and every persisted provider/
financial row remains unchanged across current requests. No fabricated prior posts.

Exact overlay720 =710 direct successor passes+10 explicit historical/current
API-equivalence cases;610 remain. Root and independent source reviews closed before
integration. Whole Ruff/mypy/diff passed each final package; combined checks running
at5d0a90d. Next root56 current single-owner/no-receipt candidate consumers reuse the
same reviewed source, excluding receipt/two-owner cases. Configured API34 historical/
current read split, social two-phase migration and populated reported restore, and
current acquisition/retry adapter continue under separately reviewed interfaces.

### Current Candidate Evidence And Remaining Restore Graphs

Reviewed9898978→f833fad adds56 exact original failures via12 current consumer
functions using the unchanged candidate source interface.142pass0skip394.491s
includes86 overlapping planning-boundary passes; AST confirms original assertions,
parameters and global fixture unchanged. Whole Ruff/mypy1137/diff passed.
Reviewed78e9c07→dcf18a6 adds2 exact failures: actual social0057→0059 migration
with a closed two-phase original producer, and actual native reported graph restore
with current dependency/privacy/export verification. Both whole affected modules
plus4 boundary cases7pass2unchanged SQLite native skips121.489s; forced-deadline
schema cleanup1pass11.492s. Whole Ruff/mypy1146/diff passed. Original protected
Meta restore remains unchanged. These are current DDL/read verification, not
retained-only test markers or missing-table stubs.

Exact overlay778 has768 direct successor passes+10 historical/current-equivalence;
552 remain. Combined Ruff/mypy1142/diff previously passed at5d0a90d. A guessed
optional standalone-plugin command targeted a nonexistent tools path and failed
before checking anything; no standalone plugin pass is claimed from that command.
Current next packages: worker ownership12, exact receipt reconciliation2, reported
acquisition/retry28, and configured API historical/current34 split with strict
causal status/detail assertions. Full aggregate remains the frozen failed run.

### Workspace Capacity Incident

A disconnect notification was checked against live executor commands, clean source
heads and the continuing pytest process; no execution interruption was found.
Subsequent actual disk exhaustion caused worker12 fixture extraction OSError28.
Its87pass/11setup-error observation is preserved;86 unchanged boundary passes are
not rerun. Only12 affected workers rerun after capacity recovery.

Root inventoried and removed98 completed reproducible PIN2155 extraction copies,
1,681,020,400 logical bytes. A worker separately inventoried29 of its own completed
copies (445,647,134 bytes). No active source, worktree, commit, raw log, XML, fixture
ID, media or database artifact was removed. Free space recovered2.6GiB. Inventory
and independent post-cleanup XML/PIN/IDs/SQLite integrity checks are retained as
root-source-cleanup-20261009.json and root-source-cleanup-integrity-20261009.json.
Original aggregate SHA remains unchanged. This is temporary-fixture reclamation,
not an aggregate reset, broader cleanup or evidence replacement.

### Current Report Acquisition And Exact Receipt Reconciliation

Reviewed123cf9b→da2dc99 adds28 current acquisition/retry identities.55pass331.282s
includes27 compatibility cases; final affected10bothDBpass70.523s after explicit
nonnull timestamps/control-key assertions. Original rolling/fixed chronology,
checkpoints, owned source/session, GET-only report responses and retries remain;
no TTL expansion, job/capsule seeding or global acquisition fixture change.
Reviewed93b0bf1→1c01091 adds2 current receipt-invalidation cases:88pass27.106s
includes86 default boundaries; final2pass16.022s after explicit Google action type.
Exactly one validated same-attempt unknown receipt may append and known run/step
state change; all original financial/provider rows otherwise remain identical.
Whole Ruff/mypy/diff passed each isolated final package (1139/1151 files).

Exact overlay808 =798 direct successor passes+10 explicit historical/current
API-equivalence,522 remaining. No new full-green or live verification claim.

### Subsequent Current Reads, API Split, And Session Regressions

Root independently reviewed and integrated the packages through `3fb6474`.
Exact immutable evidence `successor-coverage-884.json` records **884 original
failures covered: 840 direct successor passes and 44 explicit historical/current
comparison cases; 446 remain**. This is targeted evidence, not a passing aggregate.
Prior overlays and the original failed W1 aggregate remain unchanged.

Since the previous 808-case entry:
- Candidate worker twelve: `722338e` → `3dde85a`. Initial cohort had 87 passes
  and eleven disk-full setup errors; those failures are preserved. Affected twelve
  passed after safe capacity recovery (88.562 seconds); 86 current boundaries
  already passed in the original cohort. Original assertions and worker behavior
  remain, with genuine dual-account source records and no child candidate jobs.
- Configured API split: chain `e0db3f3` through `257d0b2`, integrated through
  `7426af5`. All 34 original historical API identities pass at the explicit pin
  (164.064 seconds). Separately, 42 current owned-read/denial cases plus 86 current
  boundaries passed (128 total, 294.088 seconds). Supplement twelve passed;
  exact-detail tightening initially had two failures, corrected affected two pass;
  URL guard and both-database positive checks six passed. Historical API execution
  success is never represented as current planning capability.
- Fifth historical manifest tooling: `77946fe` → `74ffc9d`; 72 focused passes,
  whole Ruff/mypy and standalone collection-plugin mypy passed. Successor manifests
  now contain five batches/293 children; original three/249 evidence is unchanged.
- Reported comparison/archive: `bc5de9f` → `249be1b`; twenty passed, including ten
  original failures, in 128.622 seconds. Actual current Meta GET timeout and receipt
  reconciliation plus real owned archive construction remain. Optional expected
  unknown receipt delta is one-shot and exact; default entire graph equality stays.
- Session authorizer: `19b251e` → `3fb6474`; 106 passed (twenty original identities
  plus 86 overlapping current boundaries), 33.710 seconds. Five individually
  reviewed retained-engine functions gain only existing markers/fixtures; complete
  original module AST remains unchanged after stripping those ten decorators.

Each source package ran Ruff, bare mypy and diff checks before commit. Session
qualification checked 1161 source files; this is its isolated base, not a claim
that all combined integration tests have passed. Package ledgers contain precise
artifact paths and failed attempts.

Disk exhaustion was resolved by deleting only inventoried completed duplicate pinned
source extraction directories; unique databases, logs, XML, manifests, worktrees
and original aggregate evidence remain. Integrity hashes were verified. A bounded
source-lifetime utility is in progress to prevent those reproductions accumulating.
No aggregate rerun, hosted retry, remote push, merge, deployment or provider write.
Next: source lifetime qualification, current runtime API thirty-case package, and
explicitly designed reported preview/revision regression split. All readiness and
human review gates remain open.
