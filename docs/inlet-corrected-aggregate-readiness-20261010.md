# Corrected Aggregate Readiness — Read-Only Review

Reviewed source: `38f6580` (10 October 2026), not a final candidate. This document
is an execution proposal, not authorization to launch or an aggregate result.
No collection, tests, DB creation/reset, cache deletion, hosted action or network
installation occurred during this review. The source ledger still reports20 open
original failures; concurrent packages and registry additions remain pending.

## Evidence And Current Capacity

Original frozen source `6a3b0f16f9ebc9c0a80dbab60140c0b8f9324f46` remains unchanged.
`/workspace/inlet-evidence/20261008/w1-aggregate/aggregate.result.json` records the
single run,23:48:43.958618 October8 to02:14:44.088432 October9, exit1. Its6,581 parent
cases were5,168passed/1,330failed/83skipped; nested249 children were246passed/3expected
SQLite skips. Those counts are hierarchical, never additive. Launcher8760.129814s
is146.0minutes; pytest8597.96s is143.3minutes. The previous three historical wrappers
consumed approximately38minutes including overhead. Newly repaired setup failures
now reach additional work; more historical batches exist. Neither the failed-path
timing nor focused overlapping runs predicts the next full passing duration.

Authoritative original XML SHA256:
`e3263f5e2bca0d484b4657d6672a32dfdc44539ee1cbed8257bf1a7187488037`.
Original log37MiB, XML21MiB, whole retained aggregate directory1.9GiB; frozen
checkout244MiB. Preserve all original files, DBs and source.

Read-only snapshot (values are transient; remeasure before launch):

- `/workspace` overlay32GiB, about695MiB available: insufficient for another
  comparable1.9GiB evidence packet plus new DBs/source and growth.
- `/tmp` tmpfs8.8GiB, about6.9GiB available. It shares the16GiB memory limit,
  has no swap, and was wiped by the prior environment restart. It is scratch,
  not durable evidence or a substitute for workspace capacity.
- Cgroup CPU quota4cores; memory ceiling16GiB; host snapshot roughly13GiB available.
  Original late47minute sample averaged1.058cores with negligible throttling, but
  was shared and partial: it proves no performance cause or future runtime bound.
- `inlet-b01-postgres` is running and `pg_isready` succeeds; data resides in its
  existing Docker volume. Original aggregate DB size90,014,223bytes; gates49,553,935;
  migration18,579,983. Current integrationDB127,704,087bytes. No DB was changed.
- IntegrationDB contains `public` and an owned `inlet_test_*` schema; original
  aggregateDB contains `public`. Presence/absence does not authorize cleanup.
  A point-in-time pg_stat_activity query showed no inlet database sessions; this
  is not a lasting exclusivity guarantee.
- Python3.12.14, Node24.19.0, Chromium/ffmpeg/ffprobe available. CI specifies Node22.
  `pwsh` is not on current PATH; prove its actual supported location or classify
  native-PowerShell prerequisite before claiming parity.
- Current checkout has no `browser/auth/node_modules`; original frozen checkout
  retains its dependency graph. Both lockfiles SHA256 are
  `1b1689943dd480da737d618b8a5681f8c81279d61805184a166458b794c15d22`.
  Offline reproduction may reuse/copy that exact installed graph into the NEW
  checkout after integrity inventory. Never rebuild into original frozen source.

Recommended local launch capacity gate: at least4GiB durable free for evidence,
plus1GiB separate safety reserve on the backing storage holding new DB/source.
This is a conservative operational reservation based on the1.9GiB prior packet,
not an established maximum. Require measured headroom for tmpfs+tests+Postgres too;
do not allocate all6.9GiB tmpfs. Monitor capacity and memory throughout, record any
resource stop as interrupted rather than passed. A larger local durable volume is
the safest option. Alternatively, parent may approve inventory/hash-preserving
moves of inactive reproducible caches to scratch, or a verified durable archive of
inactive material. No unique logs, DBs, source, failed artifacts or original W1
material may be discarded. No cleanup is proposed for immediate execution here.

## Source And Isolation Gates Before Any Launch

1. Close/review the20 pending failures and any new failures; freeze one clean exact
   successor. Record registry/manifests/partition literal union together;38f6580's
   reviewed15/387 is already pending additions, not the final required count.
2. Root explicitly schedules one corrected aggregate after capacity/prerequisite
   gates. Create a fresh detached worktree at that exact SHA, never reuse or modify
   `/workspace/inlet-w1-validation-final`. Capture clean status and tool versions.
3. Allocate THREE fresh task-owned databases: aggregate, migrations, and small CI
   gates. Names must be unique, absent beforehand, end `_ci`, use the existing local
   test container and be recorded in a durable ownership manifest. Never use
   `inlet_oct07_next_integration_ci` or any old W1 DB.
   `tests/test_phase7_postgres_transactions.py:36` drops/recreates public; a merely
   separate schema in a shared database is insufficient. Migration reset is allowed
   only for the newly allocated migrationDB when this future plan is authorized.
4. Quiesce unrelated heavy test/profiling lanes; record unavoidable co-tenants.
   Default full run stays serial. Partition candidates from failed6a3 cannot be
   silently reused for corrected source, and do not establish parallel capacity.

## Exact Future Command Templates (NOT EXECUTED)

After root selects the final40hex `FREEZE`, unique `RUN_ID`, capacity-safe durable
`EVIDENCE`, new `CHECKOUT`, and verifies the three absent database names, record all
values in a manifest. Use task-specific variables, never repurpose HOME. Examples
below are templates requiring those reviewed values, not a launch script.

```bash
export PATH=/workspace/inlet-venv/bin:$PATH
export AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true
export AD_ANALYZER_PROJECT_PHASE=pre-controlled-writes
export MYPY_CACHE_DIR=/tmp/inlet-corrected-${RUN_ID}-mypy
export PYTHONPYCACHEPREFIX=/tmp/inlet-corrected-${RUN_ID}-pycache
# cwd = the new frozen CHECKOUT
# Database names: inlet_corrected_${RUN_ID}_{aggregate,migrations,gates}_ci
# Future allocation, only after absence+ownership/capacity review:
docker exec inlet-b01-postgres createdb -U postgres "$AGGREGATE_DB"
docker exec inlet-b01-postgres createdb -U postgres "$MIGRATION_DB"
docker exec inlet-b01-postgres createdb -U postgres "$GATES_DB"
export AGGREGATE_URL="postgresql+psycopg://postgres@127.0.0.1:55432/$AGGREGATE_DB"
export MIGRATION_URL="postgresql+psycopg://postgres@127.0.0.1:55432/$MIGRATION_DB"
export GATES_URL="postgresql+psycopg://postgres@127.0.0.1:55432/$GATES_DB"
git rev-parse HEAD
git status --porcelain=v1
python --version
node --version
chromium --version
ffmpeg -version
ffprobe -version
npm ls --prefix browser/auth --all
npm run --prefix browser/auth build
git diff --exit-code -- app/portal/static/firebase-auth.mjs
python scripts/check_browser_media.py --github-env "$EVIDENCE/browser-media.env"
ruff check .
mypy
git diff --check "$DIFF_BASE...HEAD"
AD_ANALYZER_TEST_POSTGRES_URL="$GATES_URL" DATABASE_URL="$GATES_URL" ./scripts/validate.sh PostgreSQL
AD_ANALYZER_TEST_POSTGRES_URL="$MIGRATION_URL" DATABASE_URL="$MIGRATION_URL" ./scripts/validate.sh Migrations
AD_ANALYZER_TEST_POSTGRES_URL="$GATES_URL" DATABASE_URL="$GATES_URL" python -m pytest tests/test_validation_orchestration.py tests/test_validation_diagnostics.py
AD_ANALYZER_TEST_POSTGRES_URL="$GATES_URL" DATABASE_URL="$GATES_URL" ./scripts/validate.sh ReadOnly
AD_ANALYZER_TEST_POSTGRES_URL="$GATES_URL" DATABASE_URL="$GATES_URL" ./scripts/validate.sh Security
AD_ANALYZER_TEST_POSTGRES_URL="$GATES_URL" DATABASE_URL="$GATES_URL" ./scripts/validate.sh Privacy
AD_ANALYZER_TEST_POSTGRES_URL="$GATES_URL" DATABASE_URL="$GATES_URL" ./scripts/validate.sh Focused
AD_ANALYZER_TEST_POSTGRES_URL="$AGGREGATE_URL" DATABASE_URL="$AGGREGATE_URL" alembic upgrade head
AD_ANALYZER_TEST_POSTGRES_URL="$AGGREGATE_URL" DATABASE_URL="$AGGREGATE_URL" python -m pytest -ra --basetemp "$EVIDENCE/pytest" --junitxml "$EVIDENCE/aggregate.xml"
```

Use an exclusive durable start marker and a recorded launcher that captures each
command's stdout/stderr/exit/start/end, SHA/status, approved nonsecret environment,
process IDs and browser-media settings. Load required values from the generated
browser-media.env using the same reviewed mechanism as prior preflight; do not
merely create then ignore it. Stop if any prerequisite fails. No `-k`, marker
exclusions, xfail/skip injection or stop-on-first-failure in the aggregate. No `Full`
wrapper as an additional run: its embedded pytest would duplicate the aggregate
and its reset could target the wrong DB. Required gates overlap; don't sum counts.

`npm ci` and dependency installation in CI need network and are not part of this
local authorization. If the verified installed graph cannot reproduce the bundle,
stop and report the prerequisite; do not silently fetch. Node22 parity and native
PowerShell must be resolved or explicitly disclosed. The media probe actually runs
Chromium decoding and belongs future preflight, not this read-only investigation.

Reserve a local observation window of at least3hours plus preflight/reporting, with
no claim that it will finish within that window. Do not add an unreviewed outer
kill timer or change existing nested1800s/16MiB bounds. CI remains90minute pytest /
120minute job: prior146minutes exceeds both, and corrected passing runtime is
unknown. A local pass would not prove hosted-timeout feasibility or release readiness.
No hosted rerun, timeout/budget increase or workflow restructuring is authorized.

On terminal exit, preserve complete JUnit/logs, nested manifests/results, fixture
IDs and failures, exact source/hash/status and resource/capacity samples. Retain
root and child outcomes separately. Copy scratch-only artifacts durably before
checkpoint and hash them; reboot loss of /tmp must be disclosed. Any repair occurs
on a successor; never rewrite this new run's frozen source or restart silently.

## Additional Read-Only Cache Inventory

`/workspace/inlet-evidence/20261010/corrected-aggregate-readiness/ignored-cache-inventory.json`
records46 non-symlink `.mypy_cache` directories, each Git-ignored and over1MiB,
1,897,615,368 logical bytes total. No mutation occurred. Process/cwd evidence is only
a snapshot and must be rechecked with lane owners before any approved move. In
particular exclude `inlet-fresh-planning-proposal` and `inlet-retained-reported-rule12`
while their lanes are pending. Completed own-lane candidates include
`inlet-reported-planning-durable`, `inlet-reported-planning-baseline`,
`inlet-reported-proof14`, `inlet-reported-composition`, `inlet-reported-acquisition`,
`inlet-reported-foundation`, and `inlet-reported-preview-consumers`, approximately
42MiB logical each; current typechecking uses explicit/tmp caches. Even moving the
entire1.90GB inventory would bring durable free capacity only around2.5GB, below
the proposed evidence-plus-reserve gate. Existing recovery manifests batch1–5 remain
untouched. Inventory is not approval to delete/move anything or a guarantee that
all cache directories remain inactive at execution time.

## Compression, Original Packet Breakdown And DB Growth

Further read-only inventory is saved as `original-packet-breakdown.json` and
`original-packet-extensions.json` beside the cache inventory. Original aggregate
occupies1.9GiB allocated; pytest subtree1.8GiB. Historical parent subdirectories
are353/70/25MiB. Many lifecycle/erasure cases each retain24MiB. Logical extension
classification (not proof of disposability): SQLite DBs362.9MB, Python sources348.7MB,
bytecode228.1MB, XML100.3MB, Markdown98.5MB, logs74.6MB, JSON33.2MB, JS31.2MB;
extensionless555.4MB includes material not safely classified as media or source.
Named media extensions total only0.43MB; treating the remainder as disposable media
would be wrong. Directory-name classifier found58.7MB under explicit source/original
names, but additional copied source plainly exists elsewhere. These classifications
overlap and are not additive. No source bytes or temporary databases were removed.

Lossless archive staging is technically plausible because much content is source,
bytecode/text and SQLite, but compression ratio/elapsed/memory were NOT measured.
A reviewed future operation could write a compressed tar on/tmp, generate a per-file
path/size/SHA256 inventory first, read every archive member back and compare its
streamed content and metadata inventory (without doubling extraction size), then
copy archive+inventory durably and verify archive SHA256 after copying. Retain all
unique original inputs; no deletion is authorized by archive creation. This does
not free existing workspace space and needs room for the compressed copy. For a
NEW run, scratch artifacts could be archived/copied by completed phase only if
that evidence policy is approved and durable copies verified before checkpoint;
/tmp-only ongoing evidence remains vulnerable to restart. Live DB/WAL files cannot
be treated as consistent archived snapshots while writers remain active. Keep
complete durable raw root log/XML even if supplementary artifacts are losslessly
compressed. Never infer a complete archive from successful tar exit alone.

Current71 inlet databases occupy4,381,230,649 bytes in the existing PostgreSQL volume;
none was dropped/reset. The old aggregate's terminal90MB DB is not its peak growth
bound, and WAL/container backing volume overhead is separate. Before launch measure
actual Docker volume backing free bytes/inodes and establish a reservation for the
three new DBs plus WAL and temporary files. Periodically sample those NEW database
sizes, filesystem space and cgroup memory; preserve monotonic timestamps. Do not
let public-schema teardown enter an old/shared DB. Root's later snapshot improved
workspace free to1.7GiB and reduced/tmp free to5.8GiB after its separate capacity
work; those are changing values, not a durable reservation or compression proof.

Final safety gate remains after all pending closure packages (root now reports18
remaining), final registry union and exact clean source are reviewed. No collection
or aggregate is authorized by this document. The reviewed38f6580 ledger's20-open
snapshot remains the source-specific statement above; later counts do not rewrite it.

## Root Prerequisite Follow-Up

At integration203be3f, exact original coverage is1326/1330 with four pending
(two-brand2/archive2); earlier counts above remain historical snapshots. Native
PowerShell is installed: `/workspace/inlet-tools/pwsh` sets the required workspace
XDG paths then invokes `/workspace/inlet-powershell/opt/microsoft/powershell/7/pwsh`.
Its `-NoProfile -Command '$PSVersionTable.PSVersion.ToString()'` probe returned7.6.6
with exit0. A preceding direct-binary probe failed on its read-only default home
cache; no validation test ran. Future command PATH must include `/workspace/inlet-tools`.
Evidence: corrected-aggregate-readiness/powershell-resolution.json.

Root moved only inactive ignored mypy caches intact to/tmp under recovery manifest
inactive-cache-move-6.json, leaving approximately1.7GiB workspace/5.8GiBtmp free.
This improves bounded repair headroom, not full-run capacity qualification.
## Authorized Representative Compression Measurement

Root authorized a bounded operational measurement after the read-only plan. No
aggregate/collection/test or original-file change occurred. Script and results are
retained in the readiness evidence directory: `compression-measure.py`,
`compression-sample-manifest.json`, `compression-sample-result.json`, and
`compression-durable-copy-and-powershell.json`.

Sample: original root log/XML/result plus whole historical child2 and lifecycle
`test_storage_owned_binding_era0` directories. Exactly4,804 members (4,481 regular
files and10 symlinks),98,873,386 logical input bytes produced11,129,154 compressed
bytes: **11.26%** compressed/input,5.114s compression and0.776s streamed verification
plus source reread. Output had a hard300MiB cap. Every member's path/type/content
SHA256/size/mode/UID/GID/mtime or symlink target was verified by streaming the
archive, with no extraction or following links. Original file hashes/mtimes were
rechecked unchanged. Archive copied durably and SHA256 verified again:
`3606f1f6b8ee18ab38f481c53f8b69b05464a7294e3bac7f767b8894ba82dfc8`.
Both original inputs and/tmp sample remain; nothing was deleted.

This demonstrates that lifecycle/source artifact structure can be retained at tar
level: exact relative paths, metadata, symlink relationships and raw manifest/log
bytes survive. Embedded absolute recorded paths remain unchanged provenance, not
new runnable paths. Audit extraction must separately validate links/path traversal
and restore only into an isolated tree; archived presence is not permission to
rerun old producer state. Preserve SourceLifetime manifests and any retained-failure
source; do not synthesize cleaned-source entries or selectively omit unique files.

Applying the measured ratio to the roughly1.848GB logical original packet gives
about208MB, below300MiB, but this is **only extrapolation**, not full-packet evidence.
The sample includes highly compressible root failures and is not statistically
representative. Full compressed size and future corrected-artifact size remain
unknown. No full-packet compression was attempted. A later explicit bounded full
compression can stop at300MiB without deleting inputs; cap exceedance is a capacity
finding, not permission to drop members.

## Practical Scratch-First Alternative For A Future Authorized Run

A NEW unique/tmp basetemp with durable root log/XML/start/terminal/provenance files
may avoid1.9GB raw artifact growth on workspace. At measured5.8GiB scratch free,
16GiB cgroup memory and1.7GiB durable free, this is plausible but not capacity-proven.
Reserve at least2GiB scratch/memory headroom and1GiB durable/DB backing reserve;
monitor NEW basetemp, memory, WAL and database growth rather than assuming the old
packet is an upper bound. No overlapping heavy lanes. After terminal, create a
lossless supplemental archive on/tmp, stream-verify all members against a complete
inventory, copy durably, and verify whole-archive hash. With1.7GiB durable free and
1GiB reserve, the copy budget is approximately0.7GiB before new DB/log growth;
recompute it from actual capacity, never silently exceed it. A300MiB bounded first
archive attempt fits that nominal budget; exceeding the cap requires reassessment,
not truncation, deletion or an unbounded retry. Keep raw root log/XML durable.

Important limitation: terminal-only supplemental archival loses unarchived/tmp
artifacts on restart, as this environment already demonstrated. Root must explicitly
accept that transient risk or require incremental verified archives of completed,
closed artifact subtrees into durable storage during the run. Do not archive
actively written SQLite/WAL or modify/delete live basetemp. Compression is additional
CPU/memory work; measure/record overlap if incremental copying is chosen. This plan
is a feasible lower-durable-space candidate, not authorization or a new full-run
success claim. Existing unique evidence stays untouched regardless of new-run result.

PowerShell prerequisite is now resolved: exact executable wrapper
`/workspace/inlet-tools/pwsh` delegates to
`/workspace/inlet-powershell/opt/microsoft/powershell/7/pwsh`; actual invocation
reported7.6.6. Add `/workspace/inlet-tools` before the venv/currentPATH in future
preflight so `shutil.which('pwsh')` resolves it. Wrapper/binary hashes and version
are retained durably; this supersedes the earlier PATH-only availability gap.
