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
