# Offline Partition Evidence V1 — Private Interface

Proposal from `3b39199`; no workflow, harness, selection, shard execution or Full
change. Parent review precedes implementation. All outputs are review candidates,
never execution/deselection authority or a CI-duration/pass guarantee.

## Files And Interfaces

- `scripts/inlet_partition_collection.py`: uniquely named standalone opt-in pytest
  plugin, no automatic registration or imports from successor app/tests. Load only
  its scripts directory on PYTHONPATH, never the successor repository root, when
  later collecting a frozen checkout. Frozen6a collection must wait until the
  original aggregate is terminal.
  `--partition-manifest /absolute/outside-checkout/collection.json` is mandatory
  when loaded. `pytest_configure` rejects any invocation without `--collect-only`.
  Allow only the documented `-p inlet_partition_collection --collect-only
  --partition-manifest PATH` invocation (optional `-q`/`-qq`); reject nonempty
  PYTEST_ADDOPTS, override_ini, alternate configfile, noconftest/confcutdir and
  lastfailed. Require the active configuration inside the clean Git root and
  record its relative path/hash. Reject selection filters (`-k`, `-m`, `--deselect`, ignore paths/globs) and any
  positional collection scope except the configured full `testpaths`. Observe
  `pytest_deselected` and fail on any deselection; never modify items. A successful
  collection/session finish writes the manifest only after verifying full unique
  node IDs, clean tracked/untracked checkout and unchanged commit. Output must be
  outside the checkout. No tests/fixtures execute in this plugin's permitted mode.
- `tests/partition_evidence.py`: strict bounded input/value types, JUnit mapper,
  independent historical-manifest validation and deterministic proposal function.
  CLI `python -m tests.partition_evidence --collection PATH --timing PATH
  --junit PATH --shards N --output PATH`. It only reads files and writes candidate
  JSON; no subprocess pytest, workflow mutation or execution list side effect.

## Collection Manifest `inlet.partition-collection.v1`

Strict object: `schema_version`, full40hex `commit`, `pytest_version`,
`config_path`, `config_sha256`, `collection_scope` (configured testpaths), `items` in genuine collected order.
Each item: `node_id` (unique), `file` (relative `.py` path), `junit_classname`,
`junit_name`. Store the actual pytest JUnit name mapping via the installed pytest
`mangle_test_address` helper, including class names and intact parameter text
containing dots, brackets or `::`; never reconstruct a node from dotted classname.
Reject duplicate JUnit `(classname,name)` identities as ambiguous. Reject custom
JUnit prefixes at collection. Bound manifest to32MiB/20,000 nodes and individual
node IDs to16KiB; reject rather than truncate. Collection JSON serialization is
canonical for digest calculation; output is data, not a shell command.

## Timing Envelope `inlet.partition-timing.v1`

Strict object supplied with a TERMINAL existing report: `schema_version`, full
`commit`, `collection_sha256`, `junit_sha256`, integer `exit_code`0 or1. Both hashes
must match actual bounded inputs; commit must match collection. This binds the
operator-supplied timing provenance and prevents accidental mixed inputs, not a
cryptographic attestation that the run occurred. A running/incomplete report or
an old report without matching full collection cannot be upgraded into evidence.
Do not fabricate an envelope for the currently running W1.

Read JUnit at most64MiB, require complete parsed testsuites/testsuites children,
consistent declared testcase/failure/error/skip totals and exact one-to-one match
of every collected item using captured identities. Reject unknown/duplicate/
missing case, ambiguous mapping, malformed XML, or incompatible prefixed names.
Terminal failed/error/skipped cases remain explicitly labeled; never discard them.
Finite nonnegative Decimal testcase seconds (maximum1e9,32 significant digits,
no finer than nanoseconds) are optional: missing duration is
`unknown`, malformed/negative/nonfinite duration rejects. Exit0 cannot accompany
failure/error; exit1 requires failure/error. A failed testcase's measured time is
not an estimate for a successful path. No setup/call/teardown split is invented.

## Historical Separation And Candidate

Derive the three exact parent wrapper nodes from existing `BATCHES`:
`tests/test_retired_execution_snapshot.py::test_pinned_pre0086_execution_contracts[<batch>]`.
Require each exactly once and reject additional wrapper-like nodes. Independently
read each existing child manifest, enforce expected142/19/88 counts, unique IDs
within/across batches and total249, preserve unchanged pin and record SHA256s.
Do not confuse249 historical child cases with three parent wrapper cases.

`build_candidate(collection, timing, junit, *, shard_count, batches)` returns
`inlet.partition-candidate.v1`: evidence commit/digests; three separate historical
entries (wrapper, manifest digest/count); current file groups assigned toN shards;
per-node status/time and each shard's measured subtotal plus unknown/failed/skipped
counts; explicit `candidate_only=true`, `capacity_qualified=false`,
`pass_qualified=false`. Require1<=N<=32 and no empty shards.

Deterministic greedy file-level balancing: sum known seconds per current file,
sort descending subtotal then filename; assign each file to lowest known subtotal
shard with file-count then index tie-break (so zero-cost files do not create empty shards). Preserve original node order within each shard. Missing
or failed timings stay visible; subtotal is not total duration or successful-path
prediction. Never split a file, class, parameters or backend matrix across shards.
Finally assert pairwise disjoint candidate sets and their ordered-parent-set union
exactly equals the collected parent nodes. Every current node appears once and
only historical wrappers are removed from current groups. No gate is executed or
silently omitted; existing workflow remains unchanged.

## Bounded Qualification

Pure tests cover malformed/extra fields, all counts/digests/commit bindings,
missing/duplicate/unknown XML cases, failure/skip/unknown-time labels, class and
parameter JUnit mapping, conflicting wrapper and child manifests, deterministic
file balancing and exhaustive/disjoint union. Small subprocess plugin tests use a
throwaway tiny local Git repository and genuine pytest collect-only: ordered
parameter/class collection succeeds, attempted execution/filter/deselection fails
before any fixture/test sentinel executes. No repository-wide collection, DB,
browser, provider call, shard execution, Full or hosted retry. Whole Ruff, bare
mypy and diff checks required. Actual frozen aggregate timings remain unavailable;
fixture-based tool tests do not qualify real partition performance.
