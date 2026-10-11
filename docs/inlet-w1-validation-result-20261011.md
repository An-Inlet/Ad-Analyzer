# W1 Local Validation Result — 2026-10-11

Exhaustive local partitioned validation **passed** at 01:39:43 UTC on frozen
source `9d7aa2e1193ec627b33088764210f94e49cf504d`. This qualifies the local
isolated test execution, not hosted CI, a single-process aggregate or a live product.

| Population | Passed | Skipped | Failed / Errors | Total |
| --- | ---: | ---: | ---: | ---: |
| Canonical parent cases | 7,011 | 83 | 0 / 0 | 7,094 |
| Historical children (separate) | 404 | 3 | 0 / 0 | 407 |

All 52 partitions form the exact disjoint canonical parent union. All 83 parent
skip identities and reasons exactly match the original aggregate; no skips were
added or changed. The 19 historical batches match their frozen manifests and pin
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`; children are not added to parent totals.
All 52 supplemental archives and database dumps were hash-verified, including
106,696 archived members (123,271,667 compressed bytes). Both frozen checkouts
remain clean, and the original failed aggregate XML hash remains unchanged.

## Checks Actually Run

All 15 frozen preflight command groups exited zero: npm graph, auth build,
byte-identical auth bundle, browser H264/AAC decoding, Ruff, mypy (1,278 files),
branch diff, PostgreSQL (3 passed), migration upgrade/downgrade/base/upgrade through
0090, orchestration (43 passed), read-only (75 passed), security (99 passed),
privacy (14 passed), focused (43 passed), and aggregate bootstrap. These counts
overlap and must not be added as unique coverage. Final reconciliation and
qualification scripts each exited zero. This final documentation update requires
only `git diff --check`; no tests were restarted.

Environment: Python 3.12.14, Node 24.19.0, npm 11.9.0, PostgreSQL 16.15.
Offline dependencies were reused; CI uses Node 22. Local execution does not prove
hosted capacity under the unchanged 90-minute pytest / 120-minute job limits.

## Resource And Attempt History

Qualified execution took 4h54m37s wall time, including retention and repair;
supervised pytest processes totaled 4h33m22s. Minimum sampled memory headroom was
3,329,323,008 bytes (3.10 GiB), with no OOM events. Minimum workspace/scratch free
space was 1.40/5.51 GiB. The 512 MiB memory, 1 GiB durable and 2 GiB scratch
reserves were unchanged. Fresh processes and dedicated disposable databases
bounded cumulative usage. Only manifest-listed regenerable mypy caches were
removed; original evidence and original databases were preserved. Earlier total-only
memory samples do not establish a per-test leak. Observed Chromium zombies had
zero RSS; they do not establish an active browser memory leak.

The original failed aggregate remains preserved. The corrected single-process
attempt remains **interrupted**, with 1,554 passed, 26 skipped and 5,514 unreported;
it is not a pass. Attempt A then stopped on a missing Docker PostgreSQL-tools
environment setting; its two failures remain preserved. After a focused prerequisite
check, B ran fresh and completed 14 qualified partitions. B stopped while archiving
two intentional FIFO test fixtures after passing partition 13. A separately checked
archive helper preserved FIFO metadata without reading FIFOs (13 selfchecks passed),
and retained that partition without rerunning its tests. C reverified those 14
completed partitions and executed only the remaining 38. Failed logs and the
initial archive selfcheck fixture failure are retained. No completed qualified
partition was duplicated, and no product code or assertions changed in this work.

## Evidence And Next Work

Authoritative local evidence directory:
`/workspace/inlet-evidence/20261010/w1-partitioned-9d7aa2e-c/`.
Start with `qualification.json`, `reconciled-result.json`, `combined-parent.xml`,
`skip-comparison.json`, `plan.json` and `environment-versions.json`.
Preflight evidence is in sibling `w1-corrected-9d7aa2e/preflight-results.json`.
Earlier attempts and their immutable failures remain in their sibling directories.
No validation process remains active.

Tracking branch: `codex/inlet-w1-followup`; its documentation commits are separate
from the frozen tested source. Remote pushes and hosted retries remain held.
No merge, deployment, live provider/model call, credential change, purchase or
advertising mutation occurred. Q01–Q16 remain partial and all six human
usefulness/release gates remain unmet. Public website work remains paused.
Next engineering package: review the saved Google/TikTok selected-event proposals
and define a shared selection/provenance/currentness interface before implementation.
This result does not establish that Inlet is purchasable or production-ready.
