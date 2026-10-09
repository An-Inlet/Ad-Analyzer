# Genuine Producer Source Lifetime Proposal

Approved audit of root74ffc9d. The bounded implementation is recorded in
`docs/inlet-producer-source-lifetime-20261009.md`. Aggregate execution, retrospective
deletion and changes to generic subprocess runners remain outside this scope.

## Problem And Evidence

The worker12 bounded run completed87 cases and errored11 during setup when the
32GiB overlay exhausted byte capacity (83% inode usage). Its first failing stack
was immutable source extraction; subsequent temporary directory allocations failed.
The same source is currently extracted and retained per producer invocation.
After authorized inventory-first removal of29 completed copies, only the12
worker cases were retried and passed. Original failure XML and every sibling
ID/log/database artifact remain. See candidate-worker12/source-cleanup-inventory.json
and the worker12 regression ledger. This is not evidence that all future aggregate
storage requirements are solved; SQLite/media/browser outputs still need capacity.

## Exhaustive Current Call-Site Inventory

The audit searched all tests/scripts extract, extract_budget and run_bounded calls.
These are the eligible genuine-producer sites; profile keys are closed constants.
All paths below are relative to the caller's unique artifact directory.

| Profile(s) | Helper And Source Leaf | Fixed Driver | Retained Non-Source Outputs |
| --- | --- | --- | --- |
| review, initial_rule, native_diagnostic | tests/retired_producer_fixture.py:_retained_fixture; historical-source | tests/fixtures/retired_execution/seed_driver.py | producer-ids.json, producer.log, current.sqlite and original path-rooted media; schema belongs to parent |
| commerce_publication_0053 | same helper:retained_commerce_publication_fixture; historical-source | same seed_driver.py, closed mode | producer-ids.json, producer.log |
| budget_preparation_0079, candidate_result_0062, replacement_0058 | tests/retired_migration_producer.py:_seed; historical-source | migration_seed_driver.py | producer-ids.json, producer.log and path-rooted source media |
| candidate_read | tests/candidate_read_retained_fixture.py; source | candidate_read_seed_driver.py | ids.json, producer.log, current.sqlite and path-rooted media |
| campaign_review | tests/campaign_review_retained_fixture.py; source | campaign_review_seed_driver.py | ids.json, producer.log, current.sqlite; current parent owns later media work |
| configured_draft | tests/configured_draft_retained_fixture.py; source | configured_draft_seed_driver.py | ids.json, producer.log, current.sqlite, media directory outside source; literal2155 |
| reported_original | tests/reported_original_fixture.py; source | reported_original_seed_driver.py | ids.json, producer.log; SQLite is caller tmp_path/current.sqlite outside source; path-rooted media |
| candidate_receipt | tests/candidate_receipt_fixture.py; source | candidate_receipt_seed_driver.py | ids.json, producer.log, current.sqlite and path-rooted media |
| candidate_dual | tests/candidate_worker_fixture.py; source | candidate_worker_seed_driver.py | ids.json, producer.log, current.sqlite, first/second media directories |
| reported_restore | tests/reported_restore_retained_fixture.py; source | reported_restore_seed_driver.py | ids.json, producer.log, source media; native archive/fingerprint remains current parent-owned |
| social_configuration | tests/social_migration_retained_fixture.py; source | social_migration_seed_driver.py | prepared.json, continue.json, confirmed.json, producer.log, path-rooted LocalMediaStore |
| restore_fixture | scripts/inlet_restore_historical.py:_seed, fixture mode only; historical-source | scripts/inlet_restore_seed_child.py | seed-ids.json, producer.log; SQLite belongs to enclosing UUID fixture directory |

Driver entries without prefix in the table are under tests/fixtures/retired_execution.
Drivers consistently pass output.parent/artifacts (or its first/second children)
to original fixtures that create LocalMediaStore, not the source working directory.
Original review setup has no path-based media creation; original restore script
seeds typed media metadata only and already disclaims object recovery. Unique
outputs and current DB schemas must never be removed by the proposed utility.

### Explicit Exclusions

- tests/retired_execution_harness.py:qualify performs collection then execution
  in one source tree for original142/UI19/forward88/native10/budget34 historical batches (293 nodes).
  Leave it, manifests, plugins and all its artifacts unchanged. In particular, do
  not delete between its two run_bounded calls. Five fixed copies are not the
  per-case growth addressed here.
- tests/retired_snapshot.py:run_bounded/extract and tests/retired_budget_snapshot.py
  stay generic and unchanged. Their callers outside the allowlist gain no deletion.
- scripts restore native mode already owns a TemporaryDirectory in run_drill.
  Keep its existing lifetime/public CLI unchanged; do not introduce current-test
  imports into this tool. The eligible fixture mode is explicitly separate.
- Direct extractor boundary tests do not gain automatic deletion.
- Any future/new helper or profile needs explicit allowlist review, even if it
  happens to use the same runner or source leaf name.
- Original W1 and prior completed evidence directories/worktrees are never scanned
  or retrospectively cleaned. No cleanup CLI, arbitrary glob, ancestor deletion,
  cache daemon, permission change or source-sharing cache is introduced.

## Minimal Private Interface

One scripts-owned dependency-light utility (no app/database/test imports), proposed
`scripts/inlet_producer_source_lifetime.py`, supplies a closed Profile enum and an
exclusive `SourceLifetime.open(profile, artifact_directory)` lease. The registry
fixes source leaf, literal PIN, expected app/tests/scripts trees, fixed driver path,
helper path and allowed extractor archive leaf. No caller-supplied PIN/driver or
source path. The scripts fixture caller uses only restore_fixture. Existing
extractors and launch commands keep their original behavior and source checks.

Lease starts before extraction, exclusively owns a previously absent source leaf,
refuses symlink/artifact-root aliasing, and writes a sibling atomic provenance file.
It never adopts an existing source directory. Successful extraction is registered
before launch with an immutable file inventory; source/archive ownership identity
(device/inode and canonical path) is retained. Child output paths must be disjoint
from that source. Extraction failure permits only the lease's own partial immutable
source/archive to be considered, after confirming no child was launched.

Private operations are `extracted()`, `child_started()`, `after_reaped(outcome)` and
`close()`. They are a trusted repository call-site protocol, not a public API for
arbitrary process ownership. `close()` without a successful after_reaped transition
must retain the source and record retained_unconfirmed; it cannot infer completion
from an output file, elapsed time or an unchecked caller boolean.

For synchronous run_bounded/_run sites, after_reaped is invoked only when the
existing runner returns normally: its return value reports success/nonzero and
its existing finally has completed. Any runner exception conservatively retains
the source, including a timeout whose reap cannot be independently observed by
this wrapper. Do not add an observer callback, change generic runner signatures,
or blindly mark completion in a finally. This deliberate retention limit is
recorded in provenance; success and ordinary nonzero-return cleanup remove normal
per-case growth without assuming a failed final reap succeeded.

Social remains different: retain the source throughout phase-one ready, parent
actual0059 DDL and phase-two confirmation. Only after the whole process exits, or
stop_child returns having reaped it, may the context's outer finally mark completion.
Never delete during its phase-one pause. Preserve every handshake file and media
object. Its parent actual schema cleanup remains independently tested.

## Provenance And Content Safety

Before deletion, atomically persist a bounded sibling JSON record containing:
profile, source/helper/driver relative paths, exact driver SHA256, literal PIN,
Git root tree and app/tests/scripts tree IDs, extractor identity, source inventory
count/bytes/digest, source canonical path/identity, completion category (success or nonzero_reaped when a child was reaped;
otherwise no completion field, with retained_unconfirmed state for an unconfirmed child),
and intended cleanup decision. No DB URL/token/row/provider payload belongs here.
After deletion record the outcome. If provenance cannot be written, retain source
and surface the bounded cleanup failure without masking an existing primary error.

Compare source contents to its baseline before removing it. Immutable tracked
files must still match exactly. The only disposable additions allowed initially
are ordinary Python __pycache__ .pyc files derived from corresponding tracked .py
files; no arbitrary cache or output extension exception. A sampled actual dual
producer tree had495 extra files, all such Python bytecode. Unknown/new files,
modified tracked bytes, unexpected symlinks, output paths within source or changed
source identity cause retention, not deletion. Keep the unexpected content and
record relative paths/hashes for investigation. Do not silently move or discard
unique outputs. Tests must demonstrate this guard independently of source names.

Only the exact owned source directory and exact owned incomplete extractor archive
leaf may be removed. All sibling IDs/logs/JSON/XML/SQLite/media/provenance stay
byte-identical. A partial archive is reproducible source, but can be removed only
with inventory/hash recorded and no launched child. If disk exhaustion prevents
that record, fail closed and use separately reviewed manual reclamation.

## Bounded Acceptance Before Integration

1. Pure filesystem/process boundary tests: unrelated source-like directories,
   existing/symlink source, unexpected file and tracked modification retain data;
   sibling sentinel bytes survive; provenance write failure retains source;
   successful/nonzero child is reaped before deletion; synchronous runner exceptions
   retain source; active/unconfirmed child
   retains source; extraction failure cleanup owns only its exact partial output.
2. Actual dual candidate bothDB proves IDs and current readers still work after
   source disappearance. Exact pinned tree/driver metadata remains available.
3. Actual social migration plus forced second-phase deadline prove source exists
   during ready/DDL, disappears only after reap, and original current DDL/schema
   cleanup remains intact. Never patch the original provider/authority behavior.
4. Actual budget PostgreSQL verifies the distinct literal745acee pin; other normal
   profiles use literal2155. Preserve independently frozen source-tree hashes.
5. Actual script restore fixture SQLite/PG and unchanged native CLI guard tests
   ensure no test-module dependency leaks into scripts and native lifetime stays
   unchanged. No new Full or historical142 rerun for this filesystem change.
6. Lightweight registered-callsite coverage/static assertions check every allowlist
   row is wired and every excluded extraction remains unchanged; representative
   current native/reporting outputs retain their original assertions. Whole Ruff,
   bare mypy/diff and independent review precede any aggregate freeze.

Capacity reporting must distinguish extracted-source peak reduction from remaining
unique media/SQLite/browser evidence. Check available space before the eventual
aggregate; this proposal neither deletes old evidence nor promises the whole
suite fits without measuring those other artifacts.
