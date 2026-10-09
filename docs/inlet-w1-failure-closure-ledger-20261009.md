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
